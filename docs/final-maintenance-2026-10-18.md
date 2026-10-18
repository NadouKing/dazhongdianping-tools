# 最后维护与验证问题对比

维护决定：2026-10-18 结束主动维护，最终补丁在本仓现有 PR 中交付。仓库尚未由工具归档，归档由所有者处理。lazy-trip 已移除此依赖；不再排期推荐菜、商圈筛选或评论翻页。

## 实际问题与最后修复

搜索页登录/可访问，不代表详情页通过验证。此前 `detail` 遇门禁会立即抛错，命令退出时关闭专用窗口，无法在原目标页完成交互。`login` 又只检查搜索页，因此可能循环。

现在可显式运行 `dp --visible --verification-wait 180 detail <商家ID>`。仅等待同一标签页的人工操作，不刷新、不重发导航；回到原目标且元素加载后，重新进行原子门禁/数据读取和门店身份核对。等待总时限包含状态探测；未放行返回 `verification_timeout`。默认零等待继续立即报错，无界面模式不允许人工等待。

这修复窗口生命周期和恢复读取，不能改变网站对账号、网络或设备的判断。反复异常的服务端原因未证实；有 Cookie、搜索成功或关闭某个自动化标记，都不是详情放行的证明。

## 同类项目实际实现

以下只做源码审阅，未安装运行，不将其 README 的成功描述当成本机实测。

| 项目、固定来源 | 实现 | 对当前问题的意义 |
| --- | --- | --- |
| [qianwj/dp-mcp browser.ts](https://github.com/qianwj/dp-mcp/blob/7886cc2996ad207e69b5277d83b6d28a422140e7/src/browser.ts)、[login.ts](https://github.com/qianwj/dp-mcp/blob/7886cc2996ad207e69b5277d83b6d28a422140e7/src/login.ts) | Playwright 持久 profile；独立可见登录，人工验证后 Ctrl+C；查询检测门禁并抛错 | 同样依赖人工和登录状态，没有保证解决详情反复验证；独立登录入口不能证明原详情页已解锁 |
| [shawnq-msft/mcp-dianping get_auth.py](https://github.com/shawnq-msft/mcp-dianping/blob/8b861cf279ac8218357f2b03e3c8c2f44256414f/get_auth.py)、[server.py](https://github.com/shawnq-msft/mcp-dianping/blob/8b861cf279ac8218357f2b03e3c8c2f44256414f/server.py) | 可见登录保存 storage state；服务无界面启动，每次查询新 context 导入状态 | 可借鉴显式认证步骤，不能证明解决网站风控；源码还有同步/异步调用混用，未直接复制运行层 |
| [goesByhc/cn-scraper-mcp Dianping 引擎](https://github.com/goesByhc/cn-scraper-mcp/blob/f878f78f844ea55b48bdc39166ce96a07c7b8939/src/cn_scraper_mcp/engines/dianping.py)、[auth_verify.py](https://github.com/goesByhc/cn-scraper-mcp/blob/f878f78f844ea55b48bdc39166ce96a07c7b8939/src/cn_scraper_mcp/auth_verify.py) | 已保存 Cookie 配合 HTTP/JSON-LD；检测部分验证码标记并返回错误，未实现点评远端认证探针 | Cookie 文件有效不等于服务端认可；没有证据表明换 HTTP 就消除门禁。缺字段默认值和固定城市等语义也不能直接照搬 |

此前[上游候选记录](upstream-review-2026-10-18.md)保留为历史调查，未来扩展清单不再执行。最终验证、失败与实际范围见[收尾验收](final-acceptance-2026-10-18.json)。原有登录目录保持本地，不随源码或证据分发。
