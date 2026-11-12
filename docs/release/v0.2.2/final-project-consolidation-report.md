# v0.2.2 最终项目整理报告

日期：2026-11-12。发布结论仅覆盖源码统一、GitHub归档及本地Docker运行验证，不扩展历史QA范围。

## A. 本地源码

唯一长期维护目录：`F:\刘凯工作\market-regulation-platform`，main。后端验收SHA `4fc4cf124a120762593064676ea5f8dbe2394119`；前端业务SHA `63bbcc07a6b6d12a6be56fa7b0e81731c3917a45`；前端交接SHA `a6939742903f45fdaf13a858d45014ef04b7df71`；QA最终报告提交 `8ae8c238ff66e6d37a367a3c5b1efe3e899e1d4b`。

正式镜像构建源码为main提交 `30c4663ceb93cbba302b322f1ecee0d06d80bfb4`。其后收尾提交仅含报告、既有隔离验证脚本及文档入口，不改变业务和部署执行内容，不为报告重复构建镜像。最终Git提交以正式v0.2.2标签及GitHub main为准，不能在报告内嵌入自身SHA。

合并/挑选记录均保留来源，参见Git图及 local-consolidation-report.md。没有盲选ours/theirs，也没有把QA旧业务分支覆盖主线。30项定向测试通过；Vue类型检查及最终构建通过；新正式镜像无网络/无状态隔离检查通过，覆盖Vue页面、缺失资源、认证及22路径OpenAPI。未重跑真实OCR、云调用或QA隔离写入闭环。

更新清单：后端API模块、最终frontend源码与锁文件、QA报告及安全执行器、正式静态入口/镜像构建/更新回滚脚本、维护指南与README/CHANGELOG。删除文件清单为空。旧README已在本地ignored目录备份，替换后的公开README不含私密配置；必要历史报告未改写。模型、数据库、上传、环境、账本、历史镜像与工作树均保留。

## B. GitHub

仓库：https://github.com/joker33338/market-regulation-platform 。已先执行无强制分支推送，再将本地主线非快进合并/QA来源挑选后的main从5dd44b9更新到30c4663；仓库允许直接推送，未绕过分支保护、未强制推送。此次未创建PR，合并提交保留清晰记录。

| 本地分支 | 完整SHA | 推送结果 |
|---|---|---|
| codex/backend-api-v0.2.2 | 2b3c7930fe08c80e8b969750a033ca844afc5def | 已推送 |
| feat/backend-api-v0.2.2 | 20bfeef57e101f08a2f37bd4a73b6ed4237dcba5 | 已推送 |
| feat/frontend-api-v0.2.2 | a6939742903f45fdaf13a858d45014ef04b7df71 | 已推送 |
| codex/qa-v0.2.1 | 8ae8c238ff66e6d37a367a3c5b1efe3e899e1d4b | 已推送 |
| codex/fix-v0.2.1 | 3129479ef763f2d35758a68f514b7053aacdaec4 | 远程已一致 |
| codex/frontend-api-integration | 5dd44b97710db0d3bdb84bcec6e1624dd70205dc | 已推送 |
| codex/maint-v0.2.1-original | 5dd44b97710db0d3bdb84bcec6e1624dd70205dc | 远程已一致 |
| codex/agent-orchestrator | 4e5f4a79ae5bd9d97316916c854ce6504e447dcc | 已推送 |
| archive/v0.2.1-fix-source-6864e46 | 6864e462dd5af3bfbbb2c7540cb4f677463e8b7d | 已推送 |
| archive/v0.2.1-qa-source-a8e2ef8 | a8e2ef86f37136cdc67ce69616bd435abd48e2ec | 已推送 |
| feat/frontend-v0.2.1 | f4a0af8673066a54b3f3f229b4389ccc734e34a4 | 远程已一致 |
| fix/round1 | 8badb995592771ff099cf52570621ba29ad37533 | 远程已一致 |

正式标签v0.2.2在执行前不存在；归档报告提交后创建注释标签并推送，不移动历史标签。最终发布完成以执行末尾的远程main/标签比对为证据。未提交的Fix初稿和QA额外响应文档未冒充验收源码，未代为推送；主目录与已交接的前端工作树干净。未发现新增数据库、原始文档、模型权重、私钥或真实环境文件进入待推送对象文件清单。

## C. Docker

| 项目 | 核实值 |
|---|---|
| 正式标签 | market-regulation-workbench:v0.2.2 |
| 不可变源码标签 | market-regulation-workbench:sha-30c4663ceb93cbba302b322f1ecee0d06d80bfb4 |
| 镜像ID | sha256:e2a94f67ffacef9e780e06bc1484cb5e7dde4b287fa5ef340a666f5e573e52a3 |
| OCI revision | 30c4663ceb93cbba302b322f1ecee0d06d80bfb4 |
| 前端revision标签 | 63bbcc07a6b6d12a6be56fa7b0e81731c3917a45 |
| 容器 | market-regulation-app-1 |
| 容器ID | b23198928dda0e75ff7ad40d3ce8170da825cb81922526a1db65e8b5815621c1 |
| 状态 | running / healthy |
| 端口 | 127.0.0.1:8180 -> 8180/tcp |
| QA冻结回滚标签 | market-regulation-workbench:candidate-v022-4fc4cf124a12 |
| 回滚镜像ID | sha256:8f169cd82cc1bf55807eb48a9f75e0b5206ac4cb10ca27c38fe206a85e93d7a4 |

正式镜像复用已验收依赖，Docker不再依赖Vite服务。根路径及/dashboard、/documents、/parsing、/review、/knowledge/ingestion、/knowledge/search、/system均200且为Vue入口；29个最终JS/CSS资源均200。认证读取OpenAPI、info、documents、tasks、review、versions、stats、health八组200，OpenAPI22路径，匿名documents401。PostgreSQL只读查询成功。

更新前活动任务为0；SQLite更新前后均3个completed，document_review.documents均36条。/state、/app/reports、/private/runtime.json、/models仍挂载原路径，未搬迁、清理或重建任何数据库、上传及模型。更新前镜像和切换记录保留。容器ID更换是本次受控更新预期。

旧market-regulation-frontend-1已停止但不删除，8181不再作为正式入口；所有历史镜像及数据服务保留，无prune、无卷删除。正式启动/停止/更新/回滚使用scripts/release-docker.ps1和compose.local.yaml；历史构建脚本只作历史用途，见guide.md。

## D. 最终目录

- 原始market-regulation-platform/main为唯一长期源码维护目录。
- backend-api、frontend和历史archive/orchestrator工作树保留分支与回滚参考，可归档但不直接删除。
- fix仍承载实际runtime及state挂载，且有未提交初稿，暂时不能删除。
- qa保留历史证据、隔离状态及未跟踪响应，暂时不能删除。
- market-regulation-frontend-backup-20261111不是Git仓库；未经逐项证明无用，不删除。

## E. 最终状态

| 项目 | 结论 |
|---|---|
| LOCAL_CONSOLIDATION | PASS |
| GITHUB_BRANCH_SYNC | PASS |
| GITHUB_MAIN_INTEGRATION | PASS |
| DOCKER_FINALIZATION | PASS |
| OVERALL_RELEASE | PASS |

PASS依据本次源码集成、分支推送、定向构建测试和运行只读证据，最终远程标签核对在提交本报告后完成。历史QA范围和未承诺功能不扩展；本次不声称重测浏览器写按钮、真实云服务或整机恢复。
