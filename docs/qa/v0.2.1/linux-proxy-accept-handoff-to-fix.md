# Linux 官方测试代理兼容性缺陷交接

问题编号：Q021-005，P2。范围仅限测试辅助代理，不修改业务授权或官方客户端。

业务源码冻结为 `67709c4989781594dd6c4723666fdb2c21caaa7b`；部署配置为 `111f74d98157e386783f74c4242ca06b9df981db`。现有代理实现来自 QA 提交 `ae075246a86fd48924aaa53ebf01cf7a25f67736`。

实际安装的 httpcore 在 CONNECT 中固定发送 `Host` 与 `Accept: */*`。代理仅允许 Host、Proxy-Connection，故在连接源站之前拒绝合法请求。无密钥、无源站 HTTP 探针使用与正式入口相同的 `httpx.AsyncHTTPTransport(proxy=..., verify=ssl.create_default_context(), trust_env=False, retries=0)`，实际收到 `ProxyError: 403 Forbidden`，未进入 TLS 升级，未发送源站 HTTP。探针在 TLS 完成或源站请求头写入前主动中断，避免探测变成额外官方请求。

最小复现：`python -m unittest tests.test_v021_linux_egress_policy -v`。实际 10 方法：9 PASS、1 ERROR；失败方法为 `test_standard_httpcore_accept_header_is_accepted`，当前抛出请求头不允许异常。

允许修复：只添加固定 `Accept: */*` 的兼容性；不同值、重复头、任意授权头仍拒绝。固定三个精确官方域、443、可信 DNS 固定地址、双栈内核限制、权限和所有预算不得放宽。不新增通配域，不新增客户端任意目的地。

修复后重跑这 10 项纯测试，并使用无密钥、源站写入前终止的标准 httpx 握手确认 TLS。首样本的 1 次 POST 预算预留已持久化，但源站 HTTP 实发为 0；保守保留终态与预留，不重发、不重置账本、不换批次。其余两个已批准且未占位 SHA 的新任务，须通过单独入口子集校验与主协调器复核后继续。真实样本、名称、完整路径和 Token 均不进入本报告。
