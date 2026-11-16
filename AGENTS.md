# market-regulation-platform Agent 开发规则

> 长期正式源码目录：`F:\刘凯工作\market-regulation-platform`
> 仓库：`https://github.com/joker33338/market-regulation-platform`
> 默认简体中文交流，新代码注释使用简体中文。更新日期：2026-11-16。

## 1. 文档职责与入口

本文保存长期规则与执行边界。运行状态必须按当次任务核查；方案不等于实现，源码不等于运行启用，历史 PASS 不等于当前验收。

- [已确认的 v0.2.4 范围与验收方案](docs/plans/v0.2.4-confirmed-scope.md)：2026-11-16 访谈确认的 18 项决策、前置条件及实施顺序；属于规划，不自动授权开发。
- [OCR 专项开工任务与分支检查](docs/handoffs/2026-11-16-ocr-agent-start.md)：可交给 Agent 的任务文本；只有用户明确下达后，其授权才对该任务有效。
- [修订前 AGENTS.md 完整归档](docs/history/AGENTS-before-20261116-revision.md)：保存原有 2026-11-13 核查、模型验证、详细架构、旧任务授权及冲突记录。它是历史证据，不是当前执行指令或当前运行事实。
- [v0.2.3 发布指南](docs/v0.2.3-release-guide.md)、[发布报告模板](docs/v0.2.3-release-report.template.md)、[历史就绪记录](docs/release/v0.2.3/enablement-readiness.md)。模板和准备报告不能代替完成态发布证据。

## 2. 授权与版本边界

1. 以当前任务的明确授权为准；已授权范围内持续完成核查、方案修订、最小实现、隔离测试及文档更新，不重复询问。新增范围和需要单独授权的操作集中说明。
2. 历史文档中的“本轮”“已获准提交”等一次性表述不恢复授权，也不把旧任务的只读限制永久套用于后续已授权开发。任务提示词草案本身不是授权。
3. 默认顺序仍是：完成 v0.2.3 收口与获准发布、本地切换、用户试用，再确定并开发 v0.2.4。用户明确授权的 OCR 专项核查或最小修复不等于启动其余 v0.2.4 功能；先判断其属于既有能力修复还是新增范围。
4. 不未经批准提交、Push、合并 main、建立正式标签、构建或部署生产镜像；不从一般部署任务推断正式建库、数据迁移、审核写入启用的授权。
5. 删除文件、生产部署、数据库写入等高风险操作须明确授权。隔离数据库测试也须确认专用环境与授权，不能从正式连接可用推断测试许可。
6. 不自行安装或升级依赖、下载或替换模型、修改正式配置、重启共享容器。真实 OCR、MinerU 或其他外部模型调用须核对当次范围和样本授权；API Key 不代表文件外传授权。

## 3. 工作区、Git 与协作

- 复用现有代码、模型、Schema 和权限，不重新搭建项目，不为模块化大规模重构。
- 单一 Agent 统一负责开发、集成和自测，不自行分派，不把自测称为独立 QA。
- 开始时检查 git status、分支、完整 HEAD、近期 log、本地 main 和标签。涉及集成或发布判断时实际查询远程 refs；查询失败写明，缓存 ref 不代表远程现状。
- 不覆盖未提交成果，不擅自切换或重置分支，不在 main 未经批准开发。其他 worktree 只读核对，通过 Git 集成，不复制覆盖成果。
- 不强推、不 reset --hard、不 clean 用户文件、不删历史代码或分支、不默默移动标签。冲突先分析，不能直接用 ours/theirs 覆盖。
- Git 不包含 Token、密码、DSN、runtime、真实上传、数据库、模型、日志或私密配置。读取私密配置最小化输出，不打印凭据。
- `MARKET_REGULATION_TEST_CORPUS` 通过环境变量及 `pathlib.Path` 只读访问。跟踪报告仅保存匿名统计，不写原始语料路径、名称或正文。

## 4. 技术入口与复用边界

下列路径用于定位实现，具体能力和启用状态须重新核对：

| 范围 | 入口 |
|---|---|
| 后端与部署 | Python/FastAPI；`qa_core/api/`、`deploy/release/application.py`；qa_core 是业务包 |
| 前端 | Vue 3、TypeScript、Vite、Element Plus、Pinia；以 `frontend/package.json` 为准 |
| OCR/版面 | `qa_core/document_parsing/document_router.py`、`dual_engine.py`、`native.py`、`paddle_ocr.py`、`paddle_structure.py`、`runtime.py` |
| MinerU | document_parsing 下的 mineru_client/official/service/config/artifacts/repository 模块；官方 v4 和自托管 Tasks 契约不混用 |
| 切分/质量 | `qa_core/indexing/legal_structure.py`、`chunking.py`、`legal_cleaner.py`、`preview.py`；`document_parsing/quality.py`、`quality/ingestion.py` |
| 入库/版本 | `qa_core/api/ingestion.py`、`indexing/service.py`、`storage/law_intake.py`、`library_projection.py`、`database.py`、`governance/kb_versions.py` |
| 检索/审核 | `qa_core/retrieval/models.py`、`store.py`；`storage/mysql_review_ledger.py`、`review_ledger.sql`；API 的 principals/review_rbac/review_writes/accounts |

OCR 特别说明：2026-11-13 历史核查发现页级路由相关代码；2026-11-16 用户反馈智能分流尚未实现。当前运行有效性待核查，不能把源码存在当作已生效，也不能未经核查就认定所有实现缺失。分别检查特征、配置、引擎能力、实际调用链、运行版本和前端展示；未经真实端到端验证不得宣称智能分流完成。

模型与依赖：

- 优先复用 `models/bge-m3`，不默认新增 Sentence-BERT、相近 Embedding 或 MacBERT。BGE-M3 不承担 OCR、复杂表格恢复、确定性条款切分或可靠事实抽取。
- 历史 Dense 验证不证明 Sparse/ColBERT、FlagEmbedding、GPU/FP16 或当前容器可用。核对资产、维度、归一化、token 预算、模型签名及资源，不能仅凭文件存在宣称能力有效。
- 模型或向量配置变化须记录新版本、质量对比及必要重建计划；不混用不兼容向量，不填零或伪造向量。
- 历史 runtime 校验 PaddleOCR 3.3.2、PaddleX 3.3.10、PaddlePaddle 3.2.2；以实际依赖和 runtime 核查为准，不自动升级。
- 涉及 BGE-M3/FlagEmbedding、Dense+Sparse 或 PaddleOCR/MinerU 契约变更时核对当前官方文档，不把通用技能冒称专用能力。

## 5. 数据、安全与发布门禁

- 原始证据不可修改、覆盖或删除；软删除不等于物理删除。保留解析、修订、审核、发布历史，SHA256 与来源身份贯穿各阶段。
- 区分文件、业务文档和版本身份；历史解析 document_id 常为文件 SHA256，不能直接当业务主键。Chunk 必须对应正确 doc_version_id。
- 复用同一 PostgreSQL 的文档、版本、Chunk 与业务元数据，不因多个业务入口新建平行数据库。迁移前核对真实 Schema、约束、外键、索引、账号权限和身份。
- 历史 business_library.kind 仅支持 law/case，verification_status 为 pending/verified/rejected；目标 penalty_case 等类别和流程状态须显式兼容设计，不能直接写入旧约束。
- `storage/database.py` 的 VERSION_SCHEMA 与增量 SQL 均需核对；`postgres_schema.sql` 不代表全部结构。不要通过 initialize() 或测试启动修改正式 Schema。
- 历史 law_chunks、mr_chunks 向量为 1024 维，但索引覆盖不同，不能假设所有向量列已有 ANN 索引。
- MySQL 保存追加式审核；运行账号不得为 root，审核事件不得 UPDATE/DELETE。不能用基础 Compose 数据库名代替审核库身份。
- SQLite 解析任务持久化是既有例外。不得为满足“仅用于 QA”的目标直接删除或迁移任务库；另行核查活动任务、恢复、取消、幂等、挂载与回滚并取得迁移授权。
- owner 默认隔离；ADMIN/REVIEWER 按既有 principal/RBAC 授权，下载、查询、子记录、审核、发布均校验，拆分不能扩大权限。
- 保留人工审核、审核版本/来源指纹、原件 SHA、角色、写 DSN 能力和显式发布门禁。待审核、unknown、预览和测试内容不得成为 ACTIVE；无 ACTIVE 保留合法空态。
- 模型只能建议，不能发布或更新 ACTIVE。不得用 Mock、Demo 向量或合成资料冒充正式业务，不把未经核验的 OCR 标为人工通过。
- 人工修订创建新版本并记录位置、操作者和理由，保留原始解析结果；重新解析后旧修订仅作对照，确认后应用并重新审核。
- 人工可以解决业务疑问，不能豁免哈希不一致、越权或版本错配。适用的必需检查不可用不能当通过，非适用须说明理由。
- 局部解析失败保留成功产物，但必要正文不完整时阻断整份业务文档发布。含表格且缺少可靠修订/导出协议的内容继续受发布阻断。
- 幂等包含 owner、原始 SHA、解析/模型/规则版本、业务子范围和参数；同源同版本不重复入库，不跨 owner 复用权限。
- 推理不置于长事务；候选保存和索引构建分阶段，向量失败保留候选及重试状态。相关 PostgreSQL 记录在对应阶段事务一致。
- MySQL 审核和 PostgreSQL 发布不是天然单库原子事务；提交时复核版本锁与来源指纹，保留失败或结果不确定时的恢复路径。

## 6. 验证与证据

先检查脚本内容、依赖及副作用，再执行获准测试。不自行安装依赖；Windows 使用等价 PowerShell 或已有 Git Bash。缺依赖或配置的 SKIP 不算 PASS。

| 证据类型 | 可以证明的范围 |
|---|---|
| 修改前真实流程基线 | 当前质量、失败、耗时与人工成本，不证明未实现的新能力 |
| 人工指定引擎对比 | 指定引擎对样本的能力，不证明自动路由选对 |
| 单元/Mock 路由测试 | 分支、预算、授权和错误处理，不证明真实 OCR 质量 |
| 真实引擎/端到端测试 | 在指定版本、环境和样本上的实际引擎、产物与业务结果 |

- 真实样本须获准，原件只读、业务人员确认标注与争议；按来源文件分调试集和独立验收集，避免同源页/Chunk 泄漏。
- 最终测试前冻结阈值。统计人工操作时间须包含纠错、补录、重试和返工，另列系统等待时间、完成率及困难样本表现；未完成文件不得剔除，“转人工”不算业务完成。
- 关键安全/完整性/发布错误在验收中出现即不通过；有限样本零发现不等于普遍零风险。具体业务阈值在基线后确认，不凭空设置统一分数。
- 真实 OCR、数据库、模型、API、浏览器、Mock/单元、自测与独立 QA 分开报告。测试固定解析文本不能证明上游 OCR 有效；历史脚本存在不等于本轮已执行。
- 后端主要为 unittest，前端检查命令以 package.json 为准，不虚构 pytest 或 npm test。历史命令见归档和发布指南，执行前重新检查隔离条件。
- `tests.test_business_library_pg` 需 LIBRARY_ISOLATED_PG=1、LIBRARY_TEST_DSN；MySQL 测试需 REVIEW_MYSQL_TEST_CONFIG；其他数据库测试逐个检查开关。不得填正式 DSN。
- `scripts/smoke_local_model.py` 含建 SQLite、入库/发布测试版本的副作用；`scripts/verify_models.py` 会重写清单，不能用于仅只读核查。`scripts/run_fix_regressions.ps1` 会设置测试环境并写报告，执行前检查范围。

## 7. 交付与发布

- API 变更同步 Pydantic Schema、OpenAPI、前端契约及必要测试；关键路由、质量、溯源、幂等、事务、权限、发布逻辑须有有效验证。
- 报告分支、完整 HEAD、修改文件、数据库/API 变化、模型使用、测试 PASS/FAIL/SKIP/ERROR、未覆盖项、风险及发布状态。未执行如实写明，不写“0 FAIL”暗示通过。
- 若源码和运行镜像不同，分别说明验证范围；不根据源码测试宣称线上修复。
- 部署前核对活动任务、挂载、数据库、模型、镜像身份与备份，不中断任务、不删卷、不清历史数据。保留 v0.2.2 回滚依据并检查 runtime 兼容性，不通过删除新增审核历史回滚。
- 发布须先验证，再按授权提交推送、集成 main、建立标签，并核对完整 SHA 后构建。最终本地 HEAD、远程 main、标签及镜像 OCI revision 应一致；真实云调用不作为健康检查。
- 新流程先用于新文件；历史文件只在用户明确选择后生成新候选，显式审核发布后替换旧版本。实质错误按明确的撤回/纠正流程处理。
- 停用新自动流程后仍须可查看处理已保存候选，并用既有流程接收文件。数据库迁移与正式启用分别按实际范围授权。

## 8. Skills 使用

先分析目标、技术栈、阶段和风险，选择最小有效技能组合；用户要求和宿主安全规则优先。文档修改不强制 TDD；行为变更按适用性验证，测试失败优先 systematic-debugging。不得假称调用未安装技能或执行未验证可用的浏览器测试。

本项目前端为 Vue，不能因存在 React 技能就按 React 改造。Python、FastAPI、接口、PostgreSQL、安全、Docker、浏览器测试等按实际工作选择技能；已有授权不重复询问。执行结束说明实际使用的 Skills 与验证结果。
