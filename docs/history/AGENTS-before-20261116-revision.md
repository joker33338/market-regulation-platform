> 版本范围说明：本文中的 v0.2.4 内容仅为用户规划，尚未实现；本次按用户明确授权随 v0.2.3 提交，不启动 v0.2.4。文档编写任务的“仅只读”边界不撤销当前会话已明确授权的 v0.2.3 开发、测试与正式交付；后续操作仍需核对当次授权。

# market-regulation-platform 项目技术规范与 Agent 开发指南

> 市场监管智能文档解析与法律知识库管理平台。默认简体中文，新代码注释使用简体中文。
> 本文包含长期规则、2026-11-13 核查快照及 v0.2.4 目标方案。方案不等于实现，源码不等于运行启用，历史 PASS 不等于当前验收。

## 1. 授权、版本与长期规则

唯一长期正式源码目录：`F:\刘凯工作\market-regulation-platform`。仓库：`https://github.com/joker33338/market-regulation-platform`。不重新搭建项目，优先复用代码、模型、Schema 和权限，不为模块化大规模重构。其他 worktree 只读核对，通过 Git 集成，不覆盖未提交成果。仍由单一 Agent 统一负责开发、集成及自测，不自行分派，不把自测称为独立 QA。

先完成 v0.2.3：功能及测试收口 → 获准 GitHub 提交/发布 → 同步唯一正式源码目录 → 本地化部署及全链路生产切换 → 用户试用 → 收集反馈确定 v0.2.4 最终需求 → 再开发。本文不能作为提前启动 v0.2.4 的授权。

本轮仅只读检查、离线模型验证及本文编写。禁止修改业务/前端源码、Schema、runtime、正式数据，禁止创建数据库/账号、安装依赖、下载/替换模型、真实 OCR 任务、MinerU 云调用、重启 Docker、构建镜像、Git 提交、Push、合并 main。

长期必须遵守：

- 不破坏 v0.2.3 已交付能力，不覆盖未提交修改，不擅自切换/重置分支，不在 main 未经批准开发。
- 不强推、不 `reset --hard`、不 `clean` 用户文件、不删历史代码/分支、不默默移动标签。冲突先分析，不直接 ours/theirs 覆盖。
- 不擅改正式配置、创建正式数据库、迁移正式数据、启用正式 MySQL 审核账号/写入、重启共享容器。正式建库、审核启用及迁移须明确授权，不能从一般部署任务推断。
- 不修改、覆盖或删除原始证据；业务软删除不代表物理删除原件。保留历史解析、审核和发布记录。
- 不用 Mock、Demo 向量或合成资料冒充正式业务。模型不得绕过认证、来源权限、人工审核和 ACTIVE 门禁；不得把未经核验 OCR 标成人工通过。
- 不未经批准提交、Push、合并 main、打正式标签或部署；授权仅在明确范围内有效，不从旧文档恢复一次性授权。
- Git 不包含 Token、密码、DSN、runtime、真实上传、数据库、模型、日志及私密配置。`MARKET_REGULATION_TEST_CORPUS` 通过环境及 `pathlib.Path` 只读访问；跟踪报告仅匿名统计，不写原始语料路径、名称、正文。
- 部署前核对活动任务、挂载、数据库和模型，备份状态；不中断任务、不删卷、不清历史数据。保留 v0.2.2 回滚依据，同时检查 runtime 兼容性，不删除新增审核历史来回滚。
- 发布先完成功能/验证，再按授权提交和推送分支、集成 main、建立标签；核对完整 SHA 后构建。最终本地 HEAD、远程 main、标签及镜像 OCI 应一致。真实云调用不能作为健康检查。

## 2. 真实核查快照与状态

后续执行必须重新核对，不能把本节当永久运行事实。

| 项目 | 2026-11-13 结果 |
|---|---|
| 分支 | `codex/backend-improvements-v023` |
| 检查起点 HEAD | `e56dc9f40dbe7e6ca6ca09d83d7ec747fdb235e3` |
| 收尾观测 HEAD | `42cb8766da63fa9edc09299159f56437f49a92ba`；检查期间其他操作新增提交，本任务未提交。已只读检查增量，见下文 |
| 初始工作区 | 跟踪文件无修改；已有未跟踪 `tests/v023_real_service.py`，本轮不改、不执行 |
| 本地 main | `076d4f968aa2c71133c551007b5d082da96a5929`；本地有 v0.2.2 标签，未见 v0.2.3；未查询远程，不能断言 GitHub 当前状态 |
| 最近提交 | HEAD 修复法规投影来源账号只读权限；此前涉及审核后法规投影、前端自测状态、统一构建及前后端集成 |
| Docker | app/PostgreSQL/MySQL/Redis 均 healthy；app 镜像短 ID `cb478ff8a778`。健康不等于业务全链路验收 |
| 运行身份边界 | 后续联调报告记载后端 `d28cc81f413fb25b0446ceb67451c36e2bfe7a0e`、前端 `477d8c858f67ff8d20177a4bf722f45cabab9d64`，镜像短 ID 与本轮一致；本轮未成功读取 OCI revision，不能称运行源码等于 HEAD |
| 版本结论 | README/CHANGELOG 已描述 v0.2.3；本轮未验证最终发布报告、远程 refs 及全链路，不宣称正式发布完成 |

已读版本材料：`README.md`、`CHANGELOG.md`、`docs/v0.2.3-release-guide.md`、`docs/release/v0.2.3/enablement-readiness.md`、`docs/integration/v023-local-deployment-20261113.md`；完成态报告模板为 `docs/v0.2.3-release-report.template.md`。旧准备报告记载 MySQL 未启用，后续联调报告记载复用已初始化台账且知识库写能力关闭；它们是不同时间点，不能混用。本轮未读取私密 runtime 或验证正式审核写入状态。

收尾增量：`42cb876` 修改 `qa_core/storage/law_intake.py`、`tests/test_business_library_pg.py`，纳入此前未跟踪的 `tests/v023_real_service.py`。新增 `receive_case` 将已标记 case 的待复核原文接收到未索引版本、业务记录及空 case_profiles，返回 INTAKE_NOT_INDEXED/published=false；不抽取处罚字段、不分类、不发布。下文入库现状应同时包含此案例接收基础，仍不代表五类自动入库完成。本轮未执行新增测试；另出现未跟踪 `scripts/backup_local_deployment.py`，本任务未修改、未执行。数据库及容器观测为各自采样时点，不保证并行工作后仍完全相同。

### 2.1 技术栈、代码入口与实现范围

“已实现”指检查到源码能力，除注明实测外不代表本轮运行验收。

| 范围 | 代码证据、状态与差距 |
|---|---|
| 后端 | Python/FastAPI，业务包是 `qa_core/`，包名不表示仅供 QA；API 在 `qa_core/api/`，部署工厂 `deploy/release/application.py` |
| 前端 | `frontend/package.json`：Vue 3、TypeScript、Vite、Element Plus、Pinia，版本 0.2.3 |
| OCR 路由 | **部分实现**：`qa_core/document_parsing/document_router.py` 的 DocumentParser 按页选择原生/ocr/structure；`dual_engine.py` 已有质量反馈及授权云回退。不能写成所有文件无条件走 PaddleOCR |
| OCR 适配 | `native.py`、`paddle_ocr.py`、`paddle_structure.py`、`runtime.py`（位于 document_parsing）已有原生/PaddleOCR/PP-StructureV3、表格和原始结果保留 |
| MinerU | `mineru_client.py/mineru_official.py/mineru_service.py/mineru_config.py/mineru_artifacts.py/mineru_repository.py`；官方 v4 与自托管 Tasks 契约区分，mock 只用于隔离测试 |
| 版面 | **部分实现**：多栏启发式、bbox、引擎顺序、表格 HTML/单元格存在；独立重建器、栏/父块层级与复杂跨页恢复未完整实现 |
| 分类 | **目标尚未实现**：预览显式选择 law/case；未发现规则+BGE 五类自动分类器。法规特征提取不是业务分类 |
| 切分 | **部分实现**：`qa_core/indexing/legal_structure.py/chunking.py/legal_cleaner.py/preview.py`；法规编章节条款项与 source_spans、案例标题段落预览存在，五类分流及可靠字段抽取未完成 |
| 质量 | **部分实现**：`document_parsing/quality.py`、`quality/ingestion.py`、`indexing/preview.py` 有风险、长度、重复、来源和覆盖检查；缺独立六维评估、业务校准、统一四态 |
| 入库 | **部分实现**：`api/ingestion.py`、`indexing/service.py`、`storage/law_intake.py/library_projection.py/database.py`、`governance/kb_versions.py` 有法规候选、审核后构建、投影及显式发布；无五类自动入库闭环 |
| 检索 | `qa_core/retrieval/models.py/store.py`：Dense、关键词 LIKE、余弦及 RRF 混合检索，遵循已发布版本范围 |
| 审核 | `qa_core/storage/mysql_review_ledger.py/review_ledger.sql`；身份权限后续核对 `api/principals.py/review_rbac.py/review_writes.py/accounts.py` |
| 部署/依赖 | `compose.yaml` 基础服务；`compose.local.yaml` 冻结镜像、已有网络、只读 runtime/models，不建库。`requirements.txt`、`requirements-review.txt`；runtime 显式校验 PaddleOCR 3.3.2、PaddleX 3.3.10、PaddlePaddle 3.2.2，不自行升级 |

用户反馈的表格/复杂 PDF 误路由及统一显示 paddle_ocr 尚需真实样本复现：分别检查特征、开关、引擎可用性、执行日志与前端展示，不能把“已有路由代码”当问题已解决。本轮不运行真实 OCR。

## 3. 数据库真实结构与目标边界

本轮对当前 PostgreSQL `market_regulation` 用只读事务查询表、列、约束和索引元数据，未读业务正文、未写数据：

- `document_review`：documents、pages、blocks、tables、cells、images、findings 及摘要/审核视图；`storage/parsing_results.py` 保存原始结果、页面、块、表格、来源。
- `public`：mr_kb_versions、mr_document_versions、mr_chunks、mr_kb_documents、mr_active、mr_active_chunk_map、mr_release_history，以及兼容投影 law_chunks。主要定义在 `storage/database.py` 的 VERSION_SCHEMA；`storage/postgres_schema.sql` 仅为部分历史结构，不能据此推断全部 Schema。
- `mr_chunks.doc_version_id` 关联文档版本；mr_kb_documents 关联 KB 版本和文档。版本表用 `doc_id`，目标 `document_id` 须映射；解析结果的 document_id 当前通常是文件 SHA256，不能混淆文件、业务文档和版本身份。
- `business_library`：records、chapters、articles、article_chunks、case_profiles、case_law_references。records 以 doc_version_id 为主键，关联解析记录及来源；真实 `kind` CHECK 仅支持 **law/case**，verification_status 仅 pending/verified/rejected。
- law_chunks 与 mr_chunks 的 embedding 均为 `vector(1024)`。law_chunks 有 HNSW vector_cosine_ops；mr_chunks 本轮仅见主键、input_hash、doc_version_id B-tree 索引。不要假设所有向量字段已有 ANN 索引，按真实查询和数据规模评估。
- 增量 SQL 在 `scripts/sql/20261113_business_library_*`，含 up/down 和来源权限修订。读取不是授权执行，不能通过 initialize() 或测试启动修改生产 Schema。

MySQL 独立保存追加式审核：review_meta、review_heads、review_events；owner/request 幂等、对象版本、来源指纹和审核锁已有实现，运行账号禁止 root，事件不应 UPDATE/DELETE。基础 Compose 的 MySQL 数据库名不能代替独立审核库。本轮仅检查实现与 DDL，未连接 MySQL 验证当前表、账号授权及启用状态。

**SQLite 兼容差异**：目标仅用于隔离 QA，不承载正式业务；但当前 `mineru_repository.py` 的 TaskRepository 仍用 SQLite 持久化解析任务，发布指南也保留该用途。禁止直接删除/迁移任务库来满足文字目标。后续若彻底限定 QA，必须盘点恢复、取消、幂等、活动任务、挂载及回滚，单独设计并获准迁移；完成前保留此例外。

目标继续在同一 PostgreSQL 复用文档/版本/Chunk，法规、案例等元数据逻辑分离，不为两个入口新建两套物理数据库。先核对真实 Schema、外键、索引、账号与 Schema 身份，再做最小迁移。目标 penalty_case 与旧 case 需明确兼容映射、API 版本及迁移测试；enforcement_doc/other/unknown、待补充/复核先是逻辑设计，不能直接写入旧约束，也不能把业务流程状态混作 verification_status。

## 4. BGE-M3 本地资产及复用规范

目录 `models/bge-m3`。本轮结果：

| 检查项 | 结果与限制 |
|---|---|
| config | XLMRobertaModel / xlm-roberta；hidden_size=1024；24 层；16 头；intermediate_size=4096；max_position_embeddings=8194；vocab_size=250002；torch_dtype=float32 |
| 权重 | pytorch_model.bin 2,271,145,830 字节；sparse_linear.pt 3,516 字节；colbert_linear.pt 2,100,674 字节 |
| Tokenizer | tokenizer.json、tokenizer_config.json、special_tokens_map.json、sentencepiece.bpe.model、tokenizer.model、modules.json、1_Pooling/config.json 存在 |
| 完整性 | 只读计算既有 models/model_manifest.json 中 22 项大小/SHA256，均一致，未改清单；证明与本地清单一致，不独立证明权威上游来源 |
| 项目适配 | LocalEmbeddings 用 SentenceTransformer 离线 CPU 加载 BGE-M3，归一化 Dense，检查维度/非零/有限值，超 token 拒绝；本次 max_tokens=2048，不等于 config 最大位置数 |
| 真实推理 | 已有 .venv、torch 2.7.1+cpu；两句合成中文法律/执法文本输出两个 1024 维向量，范数约 1、数值有限；未写数据库 |
| 资源/速度 | 冷启动含加载约 19.12 秒；相同两句再次推理约 0.086 秒；末次 RSS 2,910,920,704 字节，观测 user CPU 约 5.33 秒。RSS 不是峰值，此数据不是长文/并发基准 |
| FlagEmbedding | 环境未安装，requirements 未列入；本轮不装依赖，该加载路径未验证 |
| Sparse/ColBERT | 投影文件存在，当前适配器不输出，两类真实推理未验证，不能报可用 |
| GPU/FP16 | 当前 torch CUDA 不可用，未测显存、GPU 推理或 FP16；不能推断宿主无 GPU |
| 业务效果 | 两句冒烟不证明分类准确率、语义检索质量或当前容器已加载模型 |

SentenceTransformers 是现有加载框架，不代表另部署 Sentence-BERT 模型。优先复用此 BGE-M3，不默认引入 Sentence-BERT、相近 Embedding 或 MacBERT。若需 FlagEmbedding Sparse/ColBERT，先在获准隔离环境验证同一资产与依赖，不能替换正式模型来试验。

BGE-M3 用于向量化、语义检索、法规/案例相似度、分类辅助、相似案例召回、重复文档辅助识别、Chunk 匹配；不承担 OCR、多栏恢复、复杂表格、确定性条款切分、可靠处罚字段抽取或法律适用结论。分类不达标才评估 MacBERT 微调；结构化抽取不达标才评估 PP-UIE。

记录模型版本/资产哈希、维度、预处理、token 预算、归一化与索引配置，不混用不兼容向量。变更须新版本、质量对比及必要索引重建。FP16 仅可先测试，不在未比较效果前替换 FP32。配置存在不等于权重可加载，文件存在不等于所有输出头有效。

## 5. v0.2.4 目标架构与统一契约

以下均为目标，不要求为同名逻辑模块新建平行实现，应扩展现有职责边界。

```text
上传 → 文件预检查 → 原生提取/页面特征分析 → OCRRouter
 → 原生结果 / PaddleOCR / PP-StructureV3 / 获准 MinerU
 → LayoutReconstructor → DocumentClassifier → SegmentationRouter
 → 业务切分器 → QualityEvaluator → IngestionRouter
 → PostgreSQL 对应集合待审核数据 → 人工审核 → 发布门禁 → ACTIVE
```

失败、未知、冲突分流，不强行完成主链。初次质量反馈用于受预算约束的 OCR 重试；最终六维评估独立执行，不循环互调绕开预算。

每阶段保留 owner、source_file_id、SHA256、输入/输出身份、document_id/doc_version_id（尚未生成则显式说明）、状态、实际引擎、模型/解析器/规则版本、耗时、失败原因、重试及关联任务。选中与实际执行引擎分开；版本缺失标 unavailable，不用模型版本冒充解析器版本。保留原文、规范化文本、原始结果和中间产物，不只存最终文本。

坐标注明 PDF point/图像 pixel/逻辑文档、尺寸、缩放和旋转映射；DOCX/TXT 逻辑页不伪装物理页，缺 bbox 说明原因，禁止编造。

| 模块 | 输入 → 输出 | 边界与复用 |
|---|---|---|
| OCRRouter | 文件/页特征、能力、质量反馈、授权预算 → 解析计划、每页执行与结果 | 扩展 DocumentParser/DualEngineRouter；不决定业务集合 |
| LayoutReconstructor | 页块/bbox/表格/原始顺序 → 版面树、阅读顺序、来源与异常 | 复用解析适配，不改写原文 |
| DocumentClassifier | 原文/标题结构、规则、参考向量 → 类别候选、证据、差异、复核状态 | 不写数据库，不授予发布权限 |
| SegmentationRouter | 分类与解析结构 → 策略、版本及切分产物 | 不判断发布权限，未知/冲突仅保留候选 |
| LawSegmenter | 法规结构 → 名称、编章节、条款项及映射 | 复用 legal_structure/chunking，禁止改写条文 |
| PenaltyCaseSegmenter | 案例原文 → 业务段落、字段候选与来源 | 复用 case 预览；关键词命中不代表事实抽取 |
| EnforcementSegmenter | 真实文书子类型/正文 → 段落及业务结构 | 独立执法文书流程 |
| GeneralSegmenter | 标题/段落/表格/块 → 通用 Chunk 和映射 | 表格独立保留 |
| QualityEvaluator | 解析/分类/切分/元数据/溯源 → 六维指标、四态、复核/重解析建议 | 复用现有检查，不改业务数据、不自行重试 |
| IngestionRouter | 分类/质量/切分、身份权限 → 逻辑集合、存储计划和待审核数据 | 编排既有存储事务，不绕过发布门禁 |
| ProvenanceManager | 文件/产物/版本/页块/Chunk → 可校验来源链 | 整合 source_location/source_spans，不复制原证据 |

模型适配层只管理加载、推理、能力、资源和错误，不耦合业务规则。IngestionRouter 引用分类与切分策略，切分由 SegmentationRouter 执行，质量由 QualityEvaluator 判定，避免重复实现。

## 6. 七项核心建设方向

### 6.1 OCR 智能路由

当前已检测文字层、隐藏 OCR 层、文本数量、图像覆盖、多栏、矢量网格/文本表格、图片网格。增强失败保留原生候选。PP-Structure 按 block_order（缺失用返回顺序）处理，保留 HTML/单元格/raw JSON。runtime 当前关闭若干方向分类/矫正选项，不能从模型存在推断启用。

| 文件/页面特征 | 目标优先路径 |
|---|---|
| 原生文字 PDF | 原生提取，复杂布局另评估 |
| 简单扫描 PDF、普通图片 | PaddleOCR |
| 表格密集文档、图片表格 | PP-StructureV3 |
| 复杂表格、图文混排 | PP-StructureV3 或 MinerU，真实能力比较后选择 |
| 多栏复杂 PDF、复杂扫描 PDF | 评估 MinerU；授权不足保留本地候选并复核，禁止自动外传 |
| 初次质量不合格 | 根据失败原因、能力和预算选择其他引擎 |

补齐特征：有效文字层、图像占比、文本密度、分辨率、表格数量/密度、多栏、块分布、图文混排、倾斜/旋转、初次质量、失败类型。决策记录特征值/不可用原因、规则版本、理由、每页实际引擎、原始结果、日志、耗时、重试；不能所有文件无条件走 PaddleOCR。

本地已有页级选择，但当前云回退按文件产生/选择候选，不能称已实现混合 PDF 云端页级拼接。OfficialMinerUClient 使用 `/v4/file-urls/batch` 及结果查询，`supports_cancel=False`，现 create 请求未传页范围。官方 v4 与自托管 Tasks 不混用；未来先核对页范围、文件/页数/大小限制、输出坐标与表格、配额、超时和取消能力，不猜测服务支持。

衍生分页文件须保留父 SHA、原页码和坐标映射，不修改原件、不当新证据；授权覆盖实际传输内容，不能拆页规避授权。现有双引擎默认关闭云，max_fallbacks 限 0/1，另有调用/文件/页数/间隔限制；owner+文件 SHA、到期和敏感授权必须保留。API Key/页面勾选不是外传授权。增加失败分类、幂等、总预算和终止原因，不无限回退，安全拒绝不得借其他引擎绕开。

### 6.2 多栏 LayoutReconstructor

获取文字块及 bbox，划分栏区域，识别跨栏标题、空间关系及标题层级，恢复区域内/间顺序；不能简单按全局 x 或 y 排序。区分标题、正文、表格、页眉页脚；排除正文索引的块仍保留原始内容。

保留 `page_number/bbox/block_id/block_type/reading_order/column_id/parent_block_id/source_file_id/parser_engine/parser_version`。旧 kind 等字段通过显式映射兼容。跨页段落/表格续接保留多页来源与关联依据，不能跨栏强拼；不确定进入复核。每条结果可返回原始页面定位。

### 6.3 DocumentClassifier 五类分类

| 标识 | 含义/目标集合 |
|---|---|
| law | 法律、行政法规、部门规章、规范性文件 → 法律法规库 |
| penalty_case | 行政处罚决定书、典型处罚案例 → 行政处罚案例库 |
| enforcement_doc | 立案审批、询问笔录、证据登记保存等 → 执法文书集合 |
| other | 普通业务文件 → 普通文档集合 |
| unknown | 无法可靠判断 → 待分类区 |

不只看文件名。三层：标题/文号/固定格式/关键字段/正文结构规则 → BGE-M3 对标注参考样本和类别描述相似度辅助 → 冲突处理。规则与模型一致增加证据可信程度；冲突、多类接近、信息不足进入复核/待分类，不强制分类。

处罚相关文书不等于案例：询问笔录、先行登记保存证据通知书不能因包含“处罚”归 penalty_case，处罚决定书可以进入案例流程。保留规则命中、样本/描述版本、候选相似度及差异、原分类、人工最终决定。

BGE 相似度不是概率，须以人工标注验证集评估/校准，不直接当置信度。按来源/文件分参考集与测试集，防同文件 Chunk 泄漏。不默认新增模型，效果不足才评估 MacBERT。

### 6.4 SegmentationRouter 与业务切分

LawSegmenter：法规名称、编章、章节标题、条号、款、项、条文正文，关联原文件/版本/页/Chunk。现有清洗去空白/拼行不能描述为逐字一致，必须单独保留 original_text 和原文偏移，搜索文本不代替证据原文。

PenaltyCaseSegmenter：案件名称、基本信息、违法事实、调查认定、违法行为、处罚依据、处罚决定、处罚结果。没有实际内容标“未提供”，不能靠关键词或常识伪造事实、金额、结果、依据；机关认定与当事人陈述分开，不作法律适用结论。

EnforcementSegmenter 按真实子类型组织；GeneralSegmenter 按标题、段落、表格、块组织。案例引用法条不切成法规文档，未知类型不能强套法规切分。

所有切分器保留 `source_file_id/document_id/doc_version_id/chunk_id/page_number/bbox/original_text/segmentation_strategy/segmentation_version`，跨页来源用列表。字符与模型 token 双预算，保护文号、日期、金额完整性，表格单独保留，不能摊平冒充法条。预览覆盖检查不代替正式原文一致性验收。

### 6.5 独立 QualityEvaluator（重点）

与 OCRRouter 和 IngestionRouter 独立：读取不可变产物，输出各维指标、依据、规则版本、失败原因、重解析及人工复核建议，不自行改文本/业务数据。

| 维度 | 至少评估 |
|---|---|
| OCR | 有效结果、空白页比例、完整性、异常字符、真实引擎置信度（若提供）、块数量、原件对应 |
| 版面 | 多栏顺序、块位置、表格结构、标题正文、页码连续性、异常重叠 |
| 切分 | 条号连续性及例外、章节层级、案例结构、Chunk 长度、段落完整性、跨页关联 |
| 分类 | 规则结果、BGE 辅助、一致性、候选差异、未知类型 |
| 元数据 | 名称、类型、来源、版本、适用文号/案件信息、业务字段完整性 |
| 溯源 | SHA256、source_file_id、doc_version_id、chunk_id、页码/bbox、原文准确对应 |

目标四态语义（细则/阈值需真实样本确认）：

- passed：适用必需检查通过，可进入下一阶段，不等于人工批准/可发布。
- needs_review：有产物但分类、元数据、版面或质量待复核。
- failed：关键检查明确不满足，如来源哈希不一致/必要正文缺失，阻断正常入库/发布。
- unavailable：缺依赖、引擎不提供或证据不可得；必需指标不可用不得当 passed。非适用另标适用性和原因。

区分真实指标、推导指标、不可用指标；无标准答案的完整性只能报告风险信号。条号跳号考虑修订/删除条款/附件，不自动判错。不把 OCR 置信度、BGE 相似度和切分完整度混成总分，不设统一 80/90 阈值。已有 0.8/12/0.02 为回退启发式参数，不是法律质量验收门槛。按业务类型校准，记录样本、方法、漏拦截/误拦截及规则升级影响，结论可重放解释。

### 6.6 IngestionRouter 自动入库（重点）

负责目标逻辑集合、切分策略引用、元数据、存储计划和待审核/待补充状态，调用现有权限/事务服务。

| 分类/质量 | 行为 |
|---|---|
| 明确且合格 | 对应业务集合待审核区 |
| 明确但元数据缺失 | 待补充区，保留原文/缺失项 |
| 冲突或 unknown | 待分类区，不强制分库 |
| 解析/关键溯源不合格 | 解析复核区，阻断正常发布 |

同时命中时先安全/来源/解析失败，再分类冲突，再元数据缺失；保留所有原因，不能后一步覆盖失败。必需指标 unavailable 进入复核。

自动保存待审核与正式发布分离、分别验收。保持 `api/ingestion.py` 的人工审核、审核版本/来源指纹、原件 SHA、角色、写 DSN 能力门禁及显式发布。现有含表格/尚无确认导出协议的人工修订仍受阻断，不为自动化绕开。模型只能建议，不能调用发布或更新 ACTIVE。

向量失败保留解析/切分候选，独立记录可重试状态；不能为满足 mr_chunks.embedding NOT NULL 填零/伪造向量。候选持久化与索引构建分阶段设计，成功后事务提交相关版本/Chunk/元数据，再经审核与发布门禁。

混合文件保留一个原始父身份，多业务子记录有版本、页/块范围、父子关系；不重复上传/复制证据，不可靠边界进入待分类。owner 与权限继承到子记录，拆分不能越权。

### 6.7 外部大模型评估

默认本地规则+BGE-M3+已有 OCR/版面能力。只有真实样本证明 OCR/版面、分类、复杂抽取不能满足目标，或确需生成式任务，才评估新增模型。必须比较实际样本准确率、错误类型、资源、耗时、成本、隐私及合规，说明现有能力为何不足。

未经明确授权不得把敏感法律材料发送外部模型 API；MinerU 外传同样受文件授权。现有 HTTPEmbedding 代码/API Key 不代表授权或必要性。

## 7. 安全、事务、幂等与溯源

1. 原始证据不可变，SHA256 贯穿所有阶段，每阶段验证父产物身份。
2. 幂等考虑 owner、原始 SHA、解析/模型/规则版本、业务子范围及参数；同源同版本不重复入库，不跨 owner 复用权限。重解析新版本，不覆盖历史。
3. Chunk 对应正确 doc_version_id，KB 不混模型签名/未经审核内容。人工改分类保留原结果、操作者、时间、理由和版本，必要时重切分/评估。
4. PostgreSQL 文档、元数据、Chunk/版本成员在对应阶段事务一致；并发、重试、崩溃有幂等/冲突检测，外部推理不置于长事务。
5. MySQL 审核与 PostgreSQL 发布不是天然单库原子事务；复用审核源指纹/版本锁，提交时复核；失败/结果不确定可恢复，不宣称跨库自动原子性。
6. owner 默认隔离；ADMIN/REVIEWER 按现有 principal/RBAC 明确授权，查询、下载、子记录、审核、发布均校验，不因自动分类扩大权限。
7. 未授权不得审核/发布；待审核、预览、测试、unknown 不成为 ACTIVE。无 ACTIVE 保留合法空态，不补造业务数据。
8. 路由/分类/切分/评估升级记录版本，保留失败候选、日志、重试和审核记录，公开报告脱敏。

## 8. QA 规范与验收

真实测试集须获准、人工标注、版本冻结，原件只读；标注类别、页阅读顺序、表格、条款/字段及来源，争议人工裁决。按来源/文件分组，不能同源不同页凑独立样本。隔离环境和合成身份仅验证安全机制，不冒充真实业务效果。

| 测试组 | 覆盖与指标 |
|---|---|
| OCR 路由 | 原生/简单扫描/表格密集/图片表格/多栏/图文混排 PDF、JPG/PNG、缺依赖/超时/空结果/云拒绝；路由准确性、错误引擎比例、回退成功率、耗时、OCR 质量、每页真实引擎 |
| 多栏/表格 | 阅读顺序、分栏、表格结构/合并单元格、标题正文、页眉页脚、跨页段落、bbox 返回原页 |
| 分类 | 法规、处罚决定书、执法文书、普通、混合、未知；Precision、Recall、Macro F1、混淆矩阵、错误自动分类率、复核率 |
| 切分 | 法规章节/条款/编号/原文一致；案例事实/行为/依据/结果和来源；缺字段未提供；执法/普通不强套法规 |
| 质量 | 不合格拦截、合格流转、冲突、溯源失败阻断、异常可解释；重点错误自动通过率，兼记误拦截和人工工作量 |
| 入库 | law/case 不串库，enforcement_doc 不归 penalty_case，unknown 不强制业务入库；owner、版本、重复重试、事务失败、来源、向量失败保留及 ACTIVE 门禁 |
| 回归 | v0.2.3 登录/角色、审核追加/幂等/锁、软删除/原件、任务日志、切分预览、检索/目录、构建/发布/回滚、本地运行 |

阈值根据真实基线和风险确定，报告分母、样本数、版本、机器、运行方式和未覆盖项。自动审核辅助只做排序/提示/减少重复工作，不取代法律内容人工审核，不能为降复核率牺牲质量。

### 8.1 现有测试命令与边界

后端主要 unittest，不能虚构 pytest 或 npm test。以下对应现有模块，后续先核对依赖和隔离再执行；本轮未运行这些回归：

```powershell
.venv/Scripts/python.exe -B -m unittest tests.test_mvp tests.test_document_parsing tests.test_dual_engine_policy tests.test_ingestion_api
.venv/Scripts/python.exe -B -m unittest tests.test_principal_rbac tests.test_release_safety tests.test_schema_identity
# 先满足专用隔离配置，不能填正式 DSN：
.venv/Scripts/python.exe -B -m unittest tests.test_business_library_pg tests.test_mysql_review
# frontend 目录、已有依赖下：
npm run typecheck
npm run build
```

business_library_pg 需 LIBRARY_ISOLATED_PG=1、LIBRARY_TEST_DSN；mysql_review 需 REVIEW_MYSQL_TEST_CONFIG。缺配置 SKIP 不算 PASS。其他 PG 测试各有开关，逐个读，生产连接不代表测试授权。

`scripts/run_fix_regressions.ps1` 复用已有 Python/API 依赖，清空相关 PG 测试环境，调用 `tests/run_round01_validation.py --include-source-tests` 并写报告，后续获准再执行。`scripts/smoke_local_model.py` 会建 SQLite、入库/发布测试版本；`scripts/verify_models.py` 会重写清单，均不直接用于本轮只读核查。真实 OCR、MinerU、数据库、浏览器与 Mock/单元证据分别记录，历史脚本不等于本轮 PASS。

### 8.2 最终目标标准

| 模块 | 后续验收目标 |
|---|---|
| OCR 路由 | 特征和质量驱动，页级真实引擎/决策可追溯，回退有限 |
| 多栏/表格 | 阅读顺序有效恢复，结构及坐标保留，不确定可复核 |
| 分类/切分 | 五类区分、对应策略，原文及案例字段有来源 |
| 质量 | 六维真实指标、依据/四态/原因，真实校准可重复 |
| 入库 | 正确集合待审核，未知/冲突/失败分流，事务及幂等有效 |
| 溯源 | 原件、哈希、版本、页/坐标、Chunk 可对应，不伪造定位 |
| 审核/发布 | 辅助减负有实测；人工审核和 ACTIVE 门禁不可绕过；保存与发布分别验收 |
| 模型/部署 | BGE-M3/已有 OCR 复用、兼容及资源有证据，支持完整本地化运行 |

## 9. 开发协作、报告及实施顺序

开发前阅读本文和相关规则，检查 git status、分支、完整 HEAD、log、本地/远程 main 和标签（远程须实际查询，不把缓存 ref 当实时状态）；确认门禁、未提交修改、相关实现、真实 Schema、模型及镜像身份。读取私密配置最小化输出，不能打印凭据。

开发中增量复用、不覆盖成果、不擅改正式配置/数据/容器。关键路由、质量、来源、幂等、事务、权限和发布逻辑有自动化测试。API 变更同步 Pydantic Schema、OpenAPI、前端契约及测试，保留历史快照，不篡改历史报告为新结论。

开发后必须报告：分支、完整 HEAD、修改文件、新增模块、数据库/API 变更、模型使用、测试总数/PASS/FAIL/SKIP（必要时 ERROR 单列）、未覆盖项、风险、对现有版本影响和发布状态。未执行写“未执行”，不写 0 FAIL 暗示通过；Mock/单元、真实数据库、真实模型、API、浏览器、自测和独立 QA 分开。

建议顺序：

1. 完成 v0.2.3、获准发布/本地切换、试用后确定 v0.2.4。
2. 建真实样本基线，核对引擎能力、模型、Schema/权限，定义身份和统一产物契约。
3. 扩展 OCR 特征、决策日志/预算，修表格/复杂 PDF 路由，做版面重建及页级反馈。
4. 规则+BGE 分类、人工纠正、分业务切分与原文映射。
5. 汇总六维质量评估，校准业务标准、错误通过率及复核工作量。
6. 最小兼容 Schema/API 设计，获准后五类待审核入库、混合文档、事务/幂等/恢复；发布门禁独立回归。
7. 真实端到端、性能及安全验收后获准交付部署；只有证据不足才评估新模型。

## 10. 旧规则合并与冲突记录

原文件中中文、单 Agent、唯一目录、保护 Git 历史/未提交成果、正式建库/审核启用需明确授权、数据分工、保密、语料只读、部署备份/回滚、自测分层和不伪造审核等有效规则均保留。

| 旧规则/差异 | 本次处理依据 |
|---|---|
| 本轮仅 v0.2.3、不开展下版本 | 当前用户明确授权 v0.2.4 文档规划，允许检查/编写，不允许业务开发 |
| 旧文件曾提 main 推送/正式标签授权 | 属此前任务，当前明确禁止提交/Push/合并，不能视为永久许可 |
| SQLite 保留任务 vs 仅 QA 目标 | 保留真实例外与差距，未来单独评估/获准迁移，不隐瞒、不直接改库 |
| law/case vs 五类 | 显式兼容与迁移设计，不直接更改枚举或宣称支持 |
| 历史准备/部署状态不同 | 按时间、SHA、镜像和范围解释；不重写历史，不足标待验证 |

维护本文时同步更新真实现状、证据和缺口，快照注明日期/身份，不仅删除“规划”便宣称实现。**本轮仅完成技术规范和开发指导，不代表 v0.2.4 功能已经开发、测试或部署完成。**
