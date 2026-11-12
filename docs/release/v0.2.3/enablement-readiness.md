> 历史draft-1记录保留。最新principal/RBAC设计与验收请见 [身份设计](identity-rbac-design.md) 和 [RBAC QA交接](rbac-qa-handoff.md)；旧writers建议不再适用。

# v0.2.3 MySQL审核正式启用准备报告

日期：2026-11-12。任务负责人Agent C。**候选状态READY_FOR_QA；正式初始化等待用户授权，未启用、未发布。**

用户最新决定：不授权创建market_review，不开放正式审核写入，不注入正式账号，不改runtime，不重启/替换8180。本任务严格按此边界完成候选与隔离验证。

## 1. 基线与版本

本地main与GitHub main均为 `076d4f968aa2c71133c551007b5d082da96a5929`；开发分支codex/backend-improvements-v023基于该main，构建时HEAD `4395c2eab60472e04e8dd2a26ce7ebc7679b9c4b`，共同祖先与main一致、5个开发提交，无历史重置或覆盖。远程暂无此开发分支，本任务未推送。

补充验证脚本提交 `5d45cf4e159b94681a55e66a2f5407dc89863c24`，只含测试，不改候选业务源码；后续本报告提交同样不改变镜像执行内容。

候选前端业务仍为 `63bbcc07a6b6d12a6be56fa7b0e81731c3917a45`，源码与该冻结版本一致，没有混入前端未提交文案产物。候选OpenAPI为0.2.3-dev、29路径；正式仍0.2.2-api-candidate、22路径，不能混作同一被测版本。

## 2. MySQL、正式初始化及权限

现有容器market-regulation-mysql-1，MySQL 8.4.13；网络market-regulation_default，容器内主机mysql、端口3306，宿主机仅127.0.0.1:13306。连接只读SELECT成功。

正式数据库market_review当前不存在；本任务未创建正式库/账号。管理员环境变量REVIEW_MYSQL_ADMIN_JSON在执行环境中未设置；未自动导出管理员密码作为替代。正式writers未获批准，建议保持空列表，详见owner-access-review.md。

隔离测试库沿用上批随机market_review_test_前缀新库，专用非root账号，仅具备review_meta SELECT、review_heads SELECT/INSERT/UPDATE、review_events SELECT/INSERT。候选实测UPDATE和DELETE事件均拒绝；不会对真实数据做破坏性权限探测。

正式初始化工具scripts/provision_review_mysql.py已核查；4项无真实DDL的工具安全测试通过：拒绝业务库名称、拒绝已有数据库、拒绝覆盖已有配置、仅生成最小权限账号及追加式事件授权。尚未实际对正式库执行工具，不把模拟工具测试写成正式初始化成功。

## 3. Runtime核查

正式私密runtime未配置REVIEW_MYSQL_CONFIG_JSON，保持原状；实际挂载仍是原有runtime/state/reports/models。隔离配置只保存在ignored local内，git check-ignore核实，两份配置均未暂存或提交。

候选一次性容器内已验证 /opt/workbench/entrypoint.py 的configuration函数可安全加载可选配置，部署工厂deploy.release.application:create_app可连接隔离MySQL，详情review_ledger可用、测试writer具备能力、真实批准事件可提交。使用合成Token及合成PG详情，未挂正式runtime或PG凭据，不能外推为正式账号与正式PG联合写入验收。

正式API账号不得root；正式配置的host应为mysql、port3306，不能错误填写宿主机127.0.0.1:13306。私密JSON只能在批准后由本机管理员注入，不能进镜像、聊天、Git或公开报告。

## 4. 候选镜像及实际验证

| 项目 | 实测身份 |
|---|---|
| 源码SHA / OCI revision | 4395c2eab60472e04e8dd2a26ce7ebc7679b9c4b |
| 镜像标签 | market-regulation-workbench:candidate-v023-4395c2eab604 |
| 镜像ID | sha256:d502cb6d82be9f8037cb22c6ab9e8ff67ae10bbb6bfadaa302545a569b2ac811 |
| 基础镜像ID | sha256:8f169cd82cc1bf55807eb48a9f75e0b5206ac4cb10ca27c38fe206a85e93d7a4 |
| 前端revision | 63bbcc07a6b6d12a6be56fa7b0e81731c3917a45 |
| 运行方式 | --rm短生命周期验证，无发布端口，不形成第二套长期后端 |

镜像构建只新增固定PyMySQL依赖，不修改既有OCR核心。候选41项测试全部通过，无失败/错误/跳过；业务模块实际导入/app/qa_core/__init__.py，挂载的是测试脚本而非QA旧业务源。测试目录与配置只读挂载，根文件系统只读、无capabilities，无正式state/runtime/models挂载；网络仅为连接现有隔离MySQL，云开关关闭，未执行云请求。

覆盖：四个审核动作、追加修订及正文空白保留、详情能力、缺省禁用、owner隔离、writer 403、幂等及冲突、并发版本锁、源变化冲突、审计分页、账号不可UPDATE/DELETE事件。MySQL客户端指向关闭的本地端口来验证故障：写接口503，详情仍200且能力false，其他只读API可用；未停止MySQL或干扰其他服务。

另有候选镜像私密runtime/部署工厂集成检查通过；以及宿主初始化工具安全测试4项通过。这些与41项统计分开记录，不冒称新增独立QA PASS。

PG源结果为合成模拟，断言审核不修改原始正文和复核信号；候选不持有正式PG/SQLite凭据。正式两次只读采样均为SQLite 5个completed、PG解析记录38条，容器身份和启动时间不变。本任务没有业务写入正式PG或SQLite，也未进行全库逐字节重放。

## 5. 当前正式8180及回滚依据

容器market-regulation-app-1，ID `b23198928dda0e75ff7ad40d3ce8170da825cb81922526a1db65e8b5815621c1`；镜像ID `sha256:e2a94f67ffacef9e780e06bc1484cb5e7dde4b287fa5ef340a666f5e573e52a3`；标签market-regulation-workbench:v0.2.2及sha-30c4663ceb93cbba302b322f1ecee0d06d80bfb4，OCI revision `30c4663ceb93cbba302b322f1ecee0d06d80bfb4`。入口127.0.0.1:8180，healthy，启动时间仍2026-11-12T00:54:43.04620371Z。

用户任务中的镜像名称以本表实测为准。本任务没有覆盖v0.2.2或其他QA回滚标签，没有切换8180。

正式切换前必须另行完成：

- [ ] 用户批准market_review创建和明确writer人员/owner名单。
- [ ] 管理员本机安全提供配置并执行正式初始化，核验账号及权限。
- [ ] 备份原私密runtime、记录挂载和镜像ID；私密配置与备份保持ignored且受限。
- [ ] 独立QA针对本表不可变候选ID验收，记录实际测试及剩余范围。
- [ ] 在获得批准后注入正式账号，核对mysql:3306与writer名单。
- [ ] 更新前重新检查活动任务、正式数据状态、源版本和前端契约，不复用本报告的历史瞬时计数。
- [ ] 用户最终授权部署后，使用原挂载受控切换并核验能力、服务、原始数据。

回滚方案：切换前保留原v0.2.2镜像ID与私密runtime备份；出现配置/连接/权限故障时先保持或恢复旧runtime（去除未受支持的新配置键），再用原镜像和相同state/models挂载回滚。旧v0.2.2 runtime加载器不接受新的MySQL配置键，因此不能只回滚镜像而继续使用修改后的runtime。不得删除已产生的MySQL审核历史、数据库或卷，不以清库作为回滚。

## 6. 交接状态

| 状态 | 当前结论 |
|---|---|
| READY_FOR_QA | 是，仅候选镜像与隔离验证材料 |
| QA_PASS | 未签发，Agent C自测不能代替独立QA |
| READY_FOR_RELEASE | 否，正式建库/名单/配置/QA/部署授权均未完成 |
| RELEASED | 否，8180仍v0.2.2 |

未解决：实际审核人员与凭证独占性未确认；平台没有独立个人账号/管理员角色映射；不允许擅自开启跨owner审核；正式数据库和配置均未初始化。详见owner-access-review.md及qa-handoff.md。待用户明确授权前不执行P1正式DDL或P3任何正式变更。
