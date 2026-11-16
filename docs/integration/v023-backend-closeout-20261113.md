# v0.2.3 后端收尾交接（2026-11-16 更新）

本批优先完成后端，前端UI优化未开始。统一源码位于原始维护目录的codex/backend-improvements-v023分支。测试为Agent C自测，不是独立QA，不表示正式发布已完成。

## 本批修改

- 本地解析首次持久化前恢复用户上传文件名；重试继续复用原缓存，不改历史OCR结果。
- 未启用双引擎时，任务也返回真实逐页selected_engine、requires_review和质量原因；不把native_pdf冒称PaddleOCR。
- 资料接收取消读取原始结果时的行锁，避免最小权限连接被迫申请UPDATE；原始结果仍只读。
- 冻结镜像显式PYTHONPATH并清理基础镜像中继承的旧代码目录，再复制统一源码；保留模型依赖和非root运行。
- 正式命名OpenAPI见frontend-openapi-v0.2.3.json：54路径，版本0.2.3；原draft快照保留。

## 数据与运行配置

已按用户专门授权升级PG来源校验函数，创建market_api_v023与market_kb_writer_v023。二者均非超级用户，不能创建角色/数据库、修改/删除原始解析、修改/删除发布历史或在public建表。API仅追加原始解析，知识库账号仅有已有入库/发布投影需要的权限。21张业务表摘要未变；新私密runtime仅已准备，尚未激活。现有MySQL库和账号未新增或重配。

现有PG业务数据为117条法规目录和20条案例目录，全部待核验、未索引；没有ACTIVE。案例字段未知部分为NULL，未把文件名/目录推断当作法律事实。原件和历史SQLite不迁移。

备份脚本在本机ignored目录生成PG定制格式、MySQL审核库、SQLite一致性副本及状态/runtime归档；私密配置不纳入Git，不在报告中输出。PG和MySQL备份均已在断网临时容器恢复；SQLite完整性为ok，归档校验和一致。恢复得到141条解析、117条法规、20条案例及0条ACTIVE。

## 前端接入边界

认证仍为HTTPBearer；账号密码登录返回短期会话，权限每请求重新读取。ADMIN具有全部业务权限；USER本人数据，REVIEWER明确授权owner范围。跨范围对象不可见，删除额外使用显式删除门禁。前端通过真实运行契约的方法/能力判断功能，源码或离线契约更新不代表8180已更新。

文档软删除、审核动作、入库/发布、账号、任务日志及法规/案例读取接口均沿用既有契约；本次不改变前端请求字段。不引入公开注册、不自动审核或发布。没有ACTIVE时法规/案例已发布列表与检索为空是合法状态，待核验资料在审核/接收范围查询。

人工修订正文正式导出、含表格和案例的正式知识库构建仍受原门禁限制；不把原文接收等同于正式业务字段核验或检索质量验收。

## 自测结果

冻结源码：`84b94cab52f64325b6c62f7d0433f0c624e8b363`。各阶段方法数不重复累加：

| 阶段 | 通过方法 | 范围 |
|---|---:|---|
| 镜像内通用pytest | 322 | 51个条件跳过项由下面专用环境全部补执行 |
| 真实隔离PG目录 | 24 | 包含仅SELECT原始结果的接收写账号，不能UPDATE原始记录 |
| 真实隔离PG软删除 | 6 | 实际引用、非ACTIVE引用与不可用边界 |
| 真实隔离PG/MySQL工作流 | 1 | 审核身份、构建、发布、检索与回滚 |
| 历史PG和双引擎策略补测 | 15 | 独立PG；云端输入为显式测试适配器，不发送外网请求 |
| Windows保护补测 | 5 | 既有Python和PowerShell；不安装依赖 |
| 合计 | 373 | 原373个方法全部有通过证据，无未补执行的条件跳过项 |

通用、双引擎补测及Windows另有144、12、10项subtest通过，不将它们重复计为测试方法。运行中核验86个镜像业务文件与冻结Git对象一致；Linux业务模块从/app/qa_core加载，未挂载宿主业务源码。

真实HTTP链路另行执行，不计入上述方法数：合成PDF上传 → SQLite任务 → native_pdf解析 → PG保存 → 独立MySQL审核 → 本地BGE-M3构建（本轮13.75秒）→ 显式发布 → 法规目录 → 关键词及混合检索 → 第二版本发布 → 回滚。上传文件名和引擎字段正确，原件字节及原始ReviewDetail正文/结果回滚后保持一致。

冻结候选断网真实模型烟测：PaddleOCR识别100字符（6.33秒）；PP-StructureV3识别95字符及1张表格（8.82秒）。网络隔离和审计钩子阻止了4次模型库联网尝试，没有云端资料外传。此为合成单页功能烟测，不代表复杂真实文档识别质量或大规模性能评估。

测试环境问题已分别保留：首次OCR隔离容器遗漏可写日志挂载、测试模块路径检查、脚本误用不存在的document字段，以及PG初始化阶段就绪判定；修正测试启动后完整执行通过，不把这些失败隐藏为成功。业务修复只有已复现的上传文件名/引擎与原始结果只读锁问题。

## 冻结候选身份

| 项目 | 值 |
|---|---|
| 后端源码与OCI revision | `84b94cab52f64325b6c62f7d0433f0c624e8b363` |
| 前端revision标签 | `84b94cab52f64325b6c62f7d0433f0c624e8b363`，既有前端源码，未开始UI优化 |
| 镜像标签 | `market-regulation-workbench:candidate-v023-backend-84b94cab` |
| 镜像ID | `sha256:3f95bb090413764a433385427c44b01e1fa8e4654f7b7671eb984a4b0471cf3e` |
| 部署状态 | 短生命周期隔离验证完成；未替换8180 |

报告提交可能仅增加文档；不能将后续HEAD冒充此候选OCI。后续业务变更必须冻结新候选并重新验证受影响范围。

## 当前8180身份（2026-11-16重新只读核对）

| 项目 | 值 |
|---|---|
| 运行容器 | `market-regulation-app-1` |
| 容器ID | `d6b567be5b42c6f41121fca14ffc37ac2adb88ab95d0d72ba1cc84c1ea1fbeab` |
| 镜像标签 | `market-regulation-workbench:candidate-v023-joint-d28cc81f-f477d8c85` |
| 镜像ID | `sha256:cb478ff8a778a79c841db7a70d690c3735ca39da7c3b755676449e8cafde9367` |
| 后端源码与OCI revision | `d28cc81f413fb25b0446ceb67451c36e2bfe7a0e` |
| 前端revision | `477d8c858f67ff8d20177a4bf722f45cabab9d64` |
| 健康 | healthy |

本机Docker Desktop起初未运行，按联调任务恢复启动后，原服务随已有重启策略恢复；没有重建或替换容器，镜像/容器ID不变。v0.2.2回滚镜像保留。

## 证据与复现

本机ignored `local/release-v023/` 保留：validation-backend-final下all/library/delete/workflow/http/extra-1116-v2日志、windows-extra-1116.log、native-pipeline-final-v2.log、native-pipeline/result.json、backup-restore-result.json、backend-status-20261116.json。配置、凭据、原始资料和运行日志不进Git。

373项复现选择器：先用专用隔离环境执行tests，再单独执行BusinessLibraryPGTests、DocumentDeletePGTests、FrontendWorkflowPGTests；补执行test_parsing_postgres、test_postgres_integration、test_round01_postgres_acceptance及绑定tests.dual_engine_adapter:run_scenario的DualEngineAcceptance。Windows补执行test_v021_agent_launcher和两项Windows保护用例。必须显式提供各测试环境变量，并满足qa_round01和独立实例保护检查；不得用正式连接替代。

真实HTTP探针为tests/check_v023_real_pipeline.py，须V023_REAL_PIPELINE=1，且仅允许已准备的18186隔离服务；启动辅助为tests/v023_real_service.py。它们使用合成账号、测试MySQL及本地模型，不接受正式runtime。

## 放行边界与剩余工作

本批后端自测收尾完成，未发现当前已执行范围的剩余可复现缺陷；不签发独立QA_PASS或正式RELEASED。整体版本仍为BACKEND_API_PARTIAL：前端UI优化/实际业务浏览器回归、最终正式源码发布及正式镜像切换尚未完成。

云端MinerU真实调用、复杂真实资料质量基准和生产负载未执行；不得将本地模型功能烟测等同全量质量验收。人工修订导出、含表格/案例正式构建仍受已列明的门禁限制，不用待核验资料补出伪造的ACTIVE。

最小权限PG连接于11月16日再次只读验证通过，新runtime尚未激活。正式业务数量仍为141条解析、117条法规、20条案例、0条ACTIVE。本批不启用新runtime、不切换8180、不Push、不合并main、不打正式标签。后续先处理前端，再统一最终版本与部署。
