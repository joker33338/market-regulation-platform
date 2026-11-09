# 独立入口与官方测试网络配置交接

业务源码：`67709c4989781594dd6c4723666fdb2c21caaa7b`。
初始部署：`111f74d98157e386783f74c4242ca06b9df981db`；本地自检：`0683a17b6bae2b00fbe8fe31e931475122a1e731`。
CONNECT兼容修复：`6ae4e19aa67853e0e54ce85faf105a6822706c12`；最终冻结配置：`04ea352cb60a43f429f09415fad455be74067787`。
日常候选镜像重建脚本：`adcd4e633e19ce5898865a7310f7b027555aeb5c`（包含 `8500134e09fd169b9e32693686e06d18a9ea2275`）。
部署范围为独立Compose与工具，不改变业务代码，不修改原始项目工作树。

正式QA配置合同：`7844c2b5e037e230b2f9e2021e37f9990b2a61ad`。
代理合同与helper：`ae075246a86fd48924aaa53ebf01cf7a25f67736`；固定Accept红测交接：`d85cbec43988cfea6154a3f4e55961642445d9fc`。

配置入口：`compose.qa-localhost.yaml`；日常脚本：`scripts/qa-localhost.ps1`；中文说明：`deploy/qa-gateway/README.md`。
固定Docker Desktop分组 `market-regulation-qa-localhost`，host入口仅127.0.0.1:8180；profile默认关闭，普通start不启用外传。
本地配置与随机Token、任务SQLite均位于忽略的local目录；不在报告给真实资料路径、名称或凭据。

独立QA已实证本地HTTP/认证/匿名Mock/幂等、容器restart/recreate、内核规则与cap0、网络拒绝计数；
nft2追加固定自HTTP与其他lo/DNS拒绝也已独立通过。具体独立报告运输由QA给出，不用Fix记录替代。
代理10项合同全通过；新nft3由独立QA读回内核并进行标准httpx无密钥、源站写入前中止的TLS检查，再继续真实批准子集。

镜像角色与身份：

| 角色 | 标签 | 已构建ID |
| --- | --- | --- |
| app、ingress | v0.2.1-nft2 | sha256:5ee2e281796686b781e585593c0d8552c92efe25f1782545eacc2fe05368199c |
| gateway、client | v0.2.1-nft3 | sha256:b18606a0402b488fd31e277c5d15fed51ac7453637deeda06c4c42e1f366db9e |
| 历史不覆盖 | v0.2.1-nft1 | sha256:659fde72ae49637504598da25fac118340f9eddeb4bed2bf9538a5ed0ee94996 |

镜像仓库名均为 `market-regulation-qa-gateway`。基础b401与原业务镜像不改变。
闭包只6个官方小包，基础151包不升级；包SHA256与签名索引证据可逐项复验。
init先nft/-150/双栈DROP与root0444proof，再setpriv非root、五cap全零、NNP，服务进程不能改规则。
proof不是独立安全测试替代；docker exec读取Key的runner也必须经相同setpriv清零，不依赖默认root exec或仅Eff=0。

账本首文件占位保留，禁止重发、清账或新批次绕限。只有两个未占位SHA可由QA按主协调器批准子集继续。
原manifest只读、同批次canonical专用ledger目录唯一可写，不能整个private目录RW或生成第二份默认账本。
云测试完成后停止client、确认无活动任务，再恢复本地app/ingress，实际验证host200；不能只看ps输出成功。
Windows真实重启未测，策略不变；真实Paddle与双引擎不因网络验收自动变PASS。

默认rebuild命令已实际执行：从agent-local复用已有Python，无需用户另填环境路径；
只产candidate标签，固定nft1/nft2/nft3映射与ID不变，不中断当前任务。脚本原始stderr兼容中断已修并复跑，判定取实际退出码。
