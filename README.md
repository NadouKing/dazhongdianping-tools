# dazhongdianping-tools

面向脚本、AI 和 Python 应用的大众点评只读工具。使用 **Python 3.14、asyncio、原生 CDP**，复用一个专用 Chrome 用户目录里的登录状态；提供 Python 库和 `dp` CLI。

当前支持商家搜索、精确门店详情、会话检查及人工登录。详情包括网页实际展示的地址、评分、人均价格、评价数量、营业提示和可见评论。它是第三方网页工具，不是大众点评官方 API。

## 安装和使用

需要 [uv](https://docs.astral.sh/uv/) 和已安装的 Google Chrome。uv 根据 `.python-version` 准备标准 CPython 3.14；不需要 Node、Go 或 Playwright。

```powershell
git clone https://github.com/NadouKing/dazhongdianping-tools.git
cd dazhongdianping-tools
uv sync --locked
uv run dp login
uv run dp search "咖啡" --city 广州 --limit 5
uv run dp detail <商家ID>
uv run dp session
```

首次 `login` 打开可见的专用浏览器，等待你扫码或完成网页验证。普通查询默认无界面，退出时正常关闭自己启动的浏览器，不影响日常 Chrome。

默认 profile 位于系统本地应用数据目录下的 `dazhongdianping-tools/browser-profile`。指定已有**专用**目录或 Chrome 路径：

```powershell
$env:DP_PROFILE_DIR = "D:\local-state\dianping-profile"
$env:DP_CHROME_PATH = "C:\Program Files\Google\Chrome\Application\chrome.exe"
uv run dp search "咖啡" --city 广州
```

命令行也支持 `dp --profile-dir <专用目录> --chrome-path <程序路径> search ...`，全局选项放在子命令前。不要将日常 Chrome 的用户目录用于自动化。浏览器不能同时占用同一个 profile；如提示 `profile_busy`，先正常结束使用该目录的命令或登录窗口。

## Python 接口

只克隆本仓就能安装和使用，不需要 Trip、小红书工具或其他仓库。也可在现有 Python 3.14 环境中安装 `uv build` 生成的 wheel，再使用 `dp` 或本节的 Python 接口。两种入口调用同一个客户端，CLI 是日常独立使用的正式入口。

```python
import asyncio
from dazhongdianping_tools import DianpingClient, DianpingError


async def main():
    async with DianpingClient(headless=True, timeout=30) as client:
        session = await client.check_session()
        print(session["data"])
        places = await client.search("咖啡", city="广州", limit=5)
        if places["data"]["items"]:
            shop_id = places["data"]["items"][0]["id"]
            detail = await client.detail(shop_id, limit=10)
            print(detail["data"])


asyncio.run(main())
```

构造函数支持 `profile_dir=None`、`chrome_path=None`、`headless=True`、`timeout=30.0` 及 `min_interval=2.0`。浏览器首次调用才启动；同一 client 复用浏览器并串行执行查询，默认相邻导航至少间隔两秒。`close()` 可重复调用。

本包成功结果为 JSON 可序列化字典：

```json
{
  "schemaVersion": 1,
  "status": "ok",
  "source": "dianping",
  "fetchedAt": "2026-10-18T12:46:42Z",
  "method": "cdp-dom",
  "elapsedMs": 3484,
  "data": {}
}
```

| 方法 | `data` |
| --- | --- |
| `search(keyword, *, city='广州', limit=20)` | `items`、`count`、`hasMore`；商家含 `id/name/url/address/category/rating/averagePrice/reviewCount` |
| `detail(item_id, *, limit=10)` | `id/name/url/address/rating/averagePrice/reviewCount/openingHours/businessStatus/reviews/reviewsStatus` |
| `check_session()` | `state`（`ready/login_required/verification_required`）、`authenticated` |
| `login(*, wait=180)` | 等待人工登录，要求 `headless=False`，成功返回会话状态 |

字段保留网页原始文本，例如 `¥22/人`、`84条`。缺失字段为 `null`，不猜测。搜索只读当前加载页面，`limit` 为 1–100，`hasMore=null` 表示没有验证后续页。城市名称只内置常用城市，也接受点评的数字城市 ID。

与其他工具采用相似的异步调用、结果外壳和错误码，便于处理生命周期和失败；平台参数与数据仍由本仓维护。`city`、商家详情的 `limit`、原始价格/营业提示及评论可见性不强行转成其他平台的合同。

`openingHours` 可能是“次日07:30开始营业”一类相对营业提示，不保证是完整营业表；结合 `fetchedAt` 使用。“休息中”不能直接解释成永久停业。

`reviewsStatus=not_visible_on_page` 表示当前页面未读到评论内容，**不是商家没有评价**。`reviewCount` 可以非零；不会用评价总数冒充已读样本数。`ready` 表示搜索页可正常访问；`authenticated` 只检查本机浏览器是否具有已知登录 Cookie 名称，不导出 Cookie，也不证明账号所有能力可用。

## 错误与边界

库抛出 `DianpingError`，提供稳定的 `code` 和安全的 `message`。CLI 将错误写为 JSON 并以非零状态退出：

```json
{"schemaVersion":1,"status":"error","source":"dianping","error":{"code":"login_required","message":"点评需要重新登录，请运行 dp login。"}}
```

常见代码：`login_required`、`verification_required`、`profile_busy`、`browser_not_found`、`navigation_timeout`、`parser_unavailable`、`shop_identity_mismatch`、`invalid_shop_id`。遇验证交给人工完成；不提供验证码绕过、发帖、点赞、点评、下单或支付能力。

读取路径是 CDP 导航后在页面执行少量 JavaScript 提取 DOM 字段。早期页面内 `fetch` 有返回 403 的实测，因此当前没有宣称稳定的纯 HTTP 接口。运行时不读取整页 HTML 再交给 Python 解析，但仍需等待浏览器加载页面；不能只根据语言或库名断言性能更快。

## 集成、开发与验证

[`lazy-trip`](https://github.com/NadouKing/lazy-trip) 是一个可选调用方。它直接 import 本包，在自己的 `research` 模块转成出行证据，负责预算、候选、地图与路线适配。本工具不读取 Trip 配置、不依赖小红书，也不要求调用方使用相同业务模型。

其他脚本、AI 或应用都可独立使用库或 CLI。Trip 用户可执行一次 `uv sync --locked`，将工具装进主应用同一个环境；共享环境是部署选择，不改变依赖方向。

```powershell
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv build
uv run python scripts/smoke_installed_wheel.py dist/dazhongdianping_tools-0.1.0-py3-none-any.whl
```

离线测试不访问平台账号。真实测试必须显式提供专用目录，见 `scripts/live_acceptance.py --help`。已保存一次 [2026-10-18 真实只读验收](docs/evidence/live-2026-10-18.json)：5 个搜索结果、一个精确门店详情；这只是该次样本，不是全平台可靠性承诺。

wheel 烟测自动创建干净环境，只安装本包和声明依赖，从源码目录之外验证库、CLI 和打包的 JavaScript，并确认没有安装集成应用或其他平台工具；CI 同样执行。详见 [部署说明](docs/deployment.md)、[架构](docs/architecture.md)、[开发约定](AGENTS.md)。

## 参考与许可

每次改动按[开发与PR交付](docs/development-delivery.md)建分支、验证并提交草稿PR，审查见[处理规则](docs/review.md)。本轮保持运行能力不变，其他项目的候选能力见[维护检查](docs/upstream-review-2026-10-18.md)。

平台读取经验参考 [dp-mcp](https://github.com/qianwj/dp-mcp)；本项目独立实现 Python 传输和生命周期，不需要 Node/Playwright 运行时。

MIT License。Chrome、平台网页和账号权限各自遵循原提供方条款。
