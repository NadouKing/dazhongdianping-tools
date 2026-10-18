"""Read-only Dianping library API with explicit session and parsing states."""

import asyncio
import json
import re
import time
from datetime import UTC, datetime
from importlib.resources import files
from urllib.parse import quote, urlsplit

from .browser import ChromeBrowser
from .errors import DianpingError

CITIES = {
    "上海": 1,
    "北京": 2,
    "杭州": 3,
    "广州": 4,
    "南京": 5,
    "苏州": 6,
    "深圳": 7,
    "成都": 8,
    "重庆": 9,
    "天津": 10,
    "武汉": 16,
    "西安": 17,
    "长沙": 20,
    "青岛": 21,
    "济南": 22,
}
LOGIN_HOSTS = {
    "account.dianping.com",
    "account.meituan.com",
    "login.dianping.com",
    "mlogin.dianping.com",
    "passport.meituan.com",
}
GATE_PATTERN = re.compile(
    r"验证中心|完成验证|访问受限|请求过于频繁|访问过于频繁|安全验证|Access Denied|403 Forbidden",
    re.IGNORECASE,
)


def city_id(city: str | int) -> int:
    value = str(city).strip().removesuffix("市")
    if value.isascii() and value.isdigit() and 0 < int(value) < 10000:
        return int(value)
    if value not in CITIES:
        raise DianpingError("unsupported_city", "城市名称尚未收录，请传点评城市数字 ID。")
    return CITIES[value]


def page_status(url: str, title: str = "", body: str = "") -> str:
    try:
        host = urlsplit(url).hostname or ""
    except ValueError:
        return "unavailable"
    if host == "verify.meituan.com" or GATE_PATTERN.search(title + " " + body):
        return "verification_required"
    if host in LOGIN_HOSTS:
        return "login_required"
    if host != "www.dianping.com":
        return "unavailable"
    return "ready"


def validate_limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100:
        raise DianpingError("invalid_limit", "limit 必须是 1 至 100 的整数。")
    return value


def envelope(started: float, data, *, method="cdp-dom") -> dict:
    return {
        "schemaVersion": 1,
        "status": "ok",
        "source": "dianping",
        "fetchedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "method": method,
        "elapsedMs": round((time.monotonic() - started) * 1000),
        "data": data,
    }


class DianpingClient:
    """One reusable browser session. Calls are serialized within this instance.

    A dedicated profile is required. Unknown fields remain null, and absent webpage
    reviews mean ``not_visible_on_page``, never "the shop has no reviews".
    """

    def __init__(
        self,
        *,
        profile_dir=None,
        chrome_path=None,
        headless=True,
        timeout=30.0,
        min_interval=2.0,
    ):
        if not isinstance(timeout, (int, float)) or not 1 <= timeout <= 600:
            raise DianpingError("invalid_timeout", "timeout 必须在 1 至 600 秒之间。")
        if not isinstance(min_interval, (int, float)) or min_interval < 0:
            raise DianpingError("invalid_interval", "请求间隔不能为负数。")
        self.browser = ChromeBrowser(profile_dir, chrome_path, headless, float(timeout))
        self.timeout = float(timeout)
        self.min_interval = float(min_interval)
        self._serial = asyncio.Lock()
        self._last_navigation = 0.0
        self._session_id = None
        self._reader = files("dazhongdianping_tools").joinpath("page_reader.js").read_text("utf-8")

    async def __aenter__(self):
        # Browser startup is lazy so invalid arguments fail without touching a profile.
        return self

    async def __aexit__(self, *_):
        await self.close()

    async def _start(self):
        if self._session_id:
            return
        await self.browser.start()
        result = await self.browser.cdp.send("Target.createTarget", {"url": "about:blank"})
        attached = await self.browser.cdp.send(
            "Target.attachToTarget", {"targetId": result["targetId"], "flatten": True}
        )
        self._session_id = attached["sessionId"]
        await self.browser.cdp.send("Page.enable", session_id=self._session_id)

    async def _state(self, selector: str) -> dict | None:
        expression = (
            "({url:location.href,title:document.title,"
            "body:(document.body?.innerText||'').slice(0,4000),"
            "ready:document.readyState,found:!!document.querySelector("
            + json.dumps(selector)
            + ")})"
        )
        return await self.browser.cdp.evaluate(expression, self._session_id)

    async def _navigate(self, url: str, selector: str):
        await self._start()
        await asyncio.sleep(max(0, self.min_interval - (time.monotonic() - self._last_navigation)))
        self._last_navigation = time.monotonic()
        navigation = await self.browser.cdp.send("Page.navigate", {"url": url}, self._session_id)
        if navigation.get("errorText"):
            raise DianpingError("navigation_failed", "点评页面未能打开。")
        started = time.monotonic()
        wanted_path = urlsplit(url).path
        while time.monotonic() - started < self.timeout:
            try:
                state = await self._state(selector)
            except DianpingError as error:
                if error.code not in {"cdp_error", "page_evaluation_failed"}:
                    raise
                state = None  # A navigation can briefly destroy its previous JS context.
            if state and state.get("url") != "about:blank":
                status = page_status(
                    state.get("url", ""), state.get("title", ""), state.get("body", "")
                )
                if status in {"login_required", "verification_required"}:
                    raise DianpingError(
                        status,
                        "点评需要重新登录，请运行 dp login。"
                        if status == "login_required"
                        else "点评要求人工验证，请运行 dp login 并在浏览器中完成。",
                    )
                committed = urlsplit(state.get("url", "")).path == wanted_path
                if committed and status == "ready":
                    if state.get("found") and state.get("ready") != "loading":
                        return
                    if state.get("ready") == "complete" and time.monotonic() - started > 2:
                        # Empty/changed pages are interpreted by the parser, not silently lost.
                        return
            await asyncio.sleep(0.2)
        raise DianpingError("navigation_timeout", "等待点评页面加载超时。")

    async def _read(self, url: str, kind: str, limit: int):
        selector = (
            "#shop-all-list li, .shop-list li, .shop-list-empty, .search-empty"
            if kind == "search"
            else ".shopName, h1.shop-name, .addressText"
        )
        await self._navigate(url, selector)
        data = await self.browser.cdp.evaluate(
            f"{self._reader}({json.dumps(kind)}, {limit})", self._session_id
        )
        if kind == "search":
            if not isinstance(data, dict) or not isinstance(data.get("items"), list):
                raise DianpingError("parser_unavailable", "点评搜索页面结构未识别。")
            if not data["items"] and not data.get("emptyState"):
                raise DianpingError(
                    "parser_unavailable", "页面未提取到商家，也未显示明确的空结果提示。"
                )
            return {"items": data["items"], "count": len(data["items"]), "hasMore": None}
        if not isinstance(data, dict) or not data.get("name"):
            raise DianpingError("parser_unavailable", "点评页面未提取到商家名称。")
        if data.get("id") != url.rsplit("/", 1)[-1]:
            raise DianpingError("shop_identity_mismatch", "返回页面与请求门店不一致。")
        return data

    async def search(self, keyword: str, *, limit: int = 20, city: str | int = "广州") -> dict:
        if not isinstance(keyword, str) or not keyword.strip() or len(keyword) > 200:
            raise DianpingError("invalid_keyword", "关键词不能为空，且不能超过 200 个字符。")
        limit = validate_limit(limit)
        encoded_keyword = quote(keyword.strip(), safe="")
        url = f"https://www.dianping.com/search/keyword/{city_id(city)}/0_{encoded_keyword}"
        async with self._serial:
            started = time.monotonic()
            return envelope(started, await self._read(url, "search", limit))

    async def detail(self, item_id: str, *, limit: int = 10) -> dict:
        if not isinstance(item_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", item_id):
            raise DianpingError("invalid_shop_id", "商家 ID 格式不正确。")
        limit = validate_limit(limit)
        async with self._serial:
            started = time.monotonic()
            return envelope(
                started,
                await self._read(f"https://www.dianping.com/shop/{item_id}", "detail", limit),
            )

    async def check_session(self) -> dict:
        async with self._serial:
            started = time.monotonic()
            try:
                await self._navigate(
                    "https://www.dianping.com/search/keyword/4/0_%E5%92%96%E5%95%A1",
                    "#shop-all-list li, .shop-list li",
                )
                state = "ready"
            except DianpingError as error:
                if error.code not in {"login_required", "verification_required"}:
                    raise
                state = error.code
            authenticated = await self._authenticated() if state == "ready" else False
            return envelope(started, {"state": state, "authenticated": authenticated})

    async def _authenticated(self) -> bool:
        cookies = await self.browser.cdp.send(
            "Network.getCookies", {"urls": ["https://www.dianping.com/"]}, self._session_id
        )
        names = {cookie["name"] for cookie in cookies.get("cookies", [])}
        return bool(names & {"fspop", "fspassport", "dponewsssid"})

    async def login(self, *, wait: float = 180.0) -> dict:
        """Open a visible dedicated browser for a human login/verification."""
        if self.browser.headless:
            raise DianpingError("visible_browser_required", "登录需要可见浏览器。")
        if not 5 <= wait <= 600:
            raise DianpingError("invalid_timeout", "登录等待时间必须在 5 至 600 秒之间。")
        async with self._serial:
            started = time.monotonic()
            try:
                await self._navigate(
                    "https://www.dianping.com/search/keyword/4/0_%E5%92%96%E5%95%A1",
                    "#shop-all-list li, .shop-list li",
                )
            except DianpingError as error:
                if error.code not in {"login_required", "verification_required"}:
                    raise
            deadline = time.monotonic() + wait
            while time.monotonic() < deadline:
                state = await self._state("#shop-all-list li, .shop-list li")
                if state and page_status(state["url"], state["title"], state["body"]) == "ready":
                    if await self._authenticated():
                        return envelope(started, {"state": "ready", "authenticated": True})
                await asyncio.sleep(1)
            raise DianpingError("login_timeout", "等待人工登录超时，原有登录目录已保留。")

    async def close(self):
        async with self._serial:
            await self.browser.close()
            self._session_id = None
