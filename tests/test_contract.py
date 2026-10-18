import asyncio
from types import SimpleNamespace

import pytest

from dazhongdianping_tools import DianpingClient, DianpingError
from dazhongdianping_tools.client import city_id, page_status


@pytest.mark.parametrize("value,expected", [("广州", 4), ("广州市", 4), ("4", 4), (7, 7)])
def test_city_name_or_numeric_id(value, expected):
    assert city_id(value) == expected


@pytest.mark.parametrize("value", ["未知城市", "0", "10000", "-1"])
def test_unknown_city_is_explicit(value):
    with pytest.raises(DianpingError, match="城市") as error:
        city_id(value)
    assert error.value.code == "unsupported_city"


@pytest.mark.parametrize(
    "host",
    ["account.dianping.com", "account.meituan.com", "login.dianping.com", "mlogin.dianping.com"],
)
def test_modern_login_domains(host):
    assert page_status(f"https://{host}/account") == "login_required"


def test_verification_and_foreign_hosts_are_not_ready():
    assert page_status("https://verify.meituan.com/a") == "verification_required"
    assert page_status("https://www.dianping.com/a", "验证中心") == "verification_required"
    assert (
        page_status("https://www.dianping.com/a", body="Access Denied") == "verification_required"
    )
    assert page_status("https://dianping.com.evil.test/a") == "unavailable"


@pytest.mark.parametrize(
    "keyword,limit,code",
    [
        ("", 5, "invalid_keyword"),
        (" ", 5, "invalid_keyword"),
        ("咖啡", 0, "invalid_limit"),
        ("咖啡", True, "invalid_limit"),
        ("咖啡", 101, "invalid_limit"),
    ],
)
def test_invalid_search_does_not_start_browser(keyword, limit, code):
    async def run():
        async with DianpingClient() as client:
            with pytest.raises(DianpingError) as error:
                await client.search(keyword, limit=limit)
            assert error.value.code == code
            assert client.browser.process is None

    asyncio.run(run())


def test_invalid_shop_url_is_rejected_before_browser():
    async def run():
        async with DianpingClient() as client:
            with pytest.raises(DianpingError) as error:
                await client.detail("https://www.dianping.com/shop/id?token=private")
            assert error.value.code == "invalid_shop_id"
            assert "private" not in error.value.message

    asyncio.run(run())


class FakeCdp:
    def __init__(self, parsed):
        self.parsed = parsed

    async def evaluate(self, *_):
        return self.parsed


def client_with_parsed(parsed):
    client = DianpingClient(min_interval=0)
    client.browser = SimpleNamespace(cdp=FakeCdp(parsed))

    async def navigate(*_):
        return None

    client._navigate = navigate
    return client


def test_unknown_search_markup_is_not_reported_as_empty():
    async def run():
        client = client_with_parsed({"items": [], "emptyState": False})
        with pytest.raises(DianpingError) as error:
            await client.search("咖啡")
        assert error.value.code == "parser_unavailable"

    asyncio.run(run())


def test_explicit_empty_state_has_valid_empty_envelope():
    async def run():
        client = client_with_parsed({"items": [], "emptyState": True})
        result = await client.search("不存在的商户")
        assert result["schemaVersion"] == 1
        assert result["status"] == "ok"
        assert result["source"] == "dianping"
        assert result["method"] == "cdp-dom"
        assert result["data"] == {"items": [], "count": 0, "hasMore": None}
        assert result["fetchedAt"].endswith("Z")

    asyncio.run(run())


def test_precise_shop_identity_is_checked():
    async def run():
        client = client_with_parsed({"id": "wrong", "name": "同名另一分店"})
        with pytest.raises(DianpingError) as error:
            await client.detail("expected")
        assert error.value.code == "shop_identity_mismatch"

    asyncio.run(run())


def test_missing_reviews_means_not_visible_on_page():
    async def run():
        parsed = {
            "id": "shop123",
            "name": "示例商家",
            "reviews": [],
            "reviewsStatus": "not_visible_on_page",
            "reviewCount": "84条",
        }
        result = await client_with_parsed(parsed).detail("shop123")
        assert result["data"]["reviewsStatus"] == "not_visible_on_page"
        assert result["data"]["reviewCount"] == "84条"

    asyncio.run(run())


def test_session_reports_gates_instead_of_ready():
    async def run():
        client = DianpingClient()

        async def navigate(*_):
            raise DianpingError("login_required", "需要登录")

        client._navigate = navigate
        assert (await client.check_session())["data"] == {
            "state": "login_required",
            "authenticated": False,
        }

    asyncio.run(run())


def test_navigation_identifies_login_before_parsing():
    async def run():
        client = DianpingClient(min_interval=0)

        class NavigationCdp:
            async def send(self, *_):
                return {}

        client.browser = SimpleNamespace(cdp=NavigationCdp())

        async def start():
            pass

        async def state(*_):
            return {
                "url": "https://account.meituan.com/login",
                "title": "登录",
                "body": "",
                "ready": "complete",
            }

        client._start, client._state = start, state
        with pytest.raises(DianpingError) as error:
            await client._navigate("https://www.dianping.com/shop/id", "h1")
        assert error.value.code == "login_required"

    asyncio.run(run())
