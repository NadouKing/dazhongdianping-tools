# 其他点评项目检查：2026-10-18

本轮按用户决定保持点评运行代码和已验证CDP路径，仅补维护流程与候选调查。

| 项目与实际读取范围 | 可借鉴点 | 本轮判断 |
|---|---|---|
| [shawnq-msft/mcp-dianping](https://github.com/shawnq-msft/mcp-dianping)，README及server.py | 分类/商圈/排序；页面推荐菜、细分评分 | 可作为下次搜索精准度和餐饮信息扩展。代码的详情入口混用同步/异步调用，需要适配；本轮未在当前页面验证推荐菜选择器，不直接引入Playwright运行层 |
| [goesByhc/cn-scraper-mcp](https://github.com/goesByhc/cn-scraper-mcp/blob/master/src/cn_scraper_mcp/engines/dianping.py)，README及点评引擎 | JSON-LD结构化详情、独立review_all读取 | 值得研究公开结构化字段与评论页。但当前代码search URL固定城市ID1，city参数未用于URL；缺评分时默认0，不适合本仓未知值语义。README里的“可读评论”尚不是本机成功证据 |
| [qianwj/dp-mcp](https://github.com/qianwj/dp-mcp) | 已有商家DOM字段参考 | 保留此前验证的字段和原生Python CDP，不重复引入另一套浏览器栈 |

## 后续优先级
1. 把商圈、地区/类别与分店核对做好，减少类似“幸福里”检索召回其他区域分店的问题。
2. 当前页面存在时补推荐菜、特色标签、细分评分，同时记录来源与未知值。
3. 只有真实专用会话验证review_all页面可读后，才增加有界评论读取。认证、验证码、结构变化与真空结果必须分开。
4. JSON-LD或页面内HTTP可作为经过实测的补充路径；不因为仓库采用HTTP就替换当前可用CDP。

本轮未安装上述项目、未导出或复制现有账号凭证、未改点评运行能力，也未声称解决完整评论读取。文档和CI变更按 [PR流程](development-delivery.md)交付，历史平台验收仍是历史记录。
