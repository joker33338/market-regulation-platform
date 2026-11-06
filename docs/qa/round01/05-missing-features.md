# 功能覆盖与代码完整性审查（阶段一）

基线 `f2a5c925f0305a2e7df21f750b20bed63db40de3`；2026-11-06。依据：本轮用户 MinerU 集成与补充任务、`docs/ocr-integration/02-集成架构与模块说明.md`、`docs/Docker本地部署.md`、已核实的官方 Tasks 契约及当前源码。旧文档明确目前是 CLI、解析与入库有意分离；因此未接入 HTTP 并非旧业务回归。

## 全链路覆盖

| 环节 | 实现状态 | 可运行证据/边界 |
| --- | --- | --- |
| 本地业务文件上传 | 尚未开发的新需求 | 无 FastAPI app/route；GAP-003 |
| 类型识别 | 已实现且可运行（受支持类型） | DocumentParser 后缀检查与原有测试 PASS；Excel 未支持，GAP-008 待确认 |
| 解析引擎选择 | 已实现但测试失败 | 本地 native/OCR/structure 已实现；中文网格路径 OCR-001 FAIL |
| MinerU 提交/上传/查询/下载 | 代码缺失，新需求 | GAP-001/002；参考 Mock PASS 不代表产品实现 |
| Markdown/JSON 标准化 | 部分实现 | 本地 schemas/normalizer/export 原有测试 PASS；无 MinerU 输出适配 GAP-005 |
| 清洗/法律 Chunking | 已实现且可运行 | legal_cleaner/legal_structure/chunking 合成测试 PASS；普通材料 GAP-008 |
| 去重/增量 | 已实现且可运行 | service 和 SQLite 重复/缓存测试 PASS；远程提交幂等 GAP-002 |
| Embedding | 已实现且可运行 | LocalEmbeddings 真实离线 1024 维 PASS |
| PostgreSQL 入库 | 已实现，环境阻塞 | SQL/psycopg2/事务存在；无隔离测试库，不能凭 SQLite 宣称 PostgreSQL PASS |
| 知识库检索 | 已实现且可运行（SQLite） | query.ask/retrieval.store 合成测试 PASS；真实 PostgreSQL 检索 BLOCKED |
| 失败追踪/恢复 | 部分实现 | KB 版本失败状态存在；MinerU task/file 持久化不存在 GAP-004 |
| 生产 GPU 部署 | 尚未开发的新需求 | GAP-006；当前 Docker 构建上下文另有 GAP-007 |

## 缺失项

### GAP-001 — MinerU 客户端（MINERU-FEAT-001）

- 依据/名称：用户要求 Tasks 提交、逐文件上传、查询和结果；官方契约。
- 状态/证据/位置：代码缺失，新需求；搜索 `qa_core/`、`scripts/` 无 MinerU；当前入口 `document_parsing/document_router.py::DocumentParser` 只处理本地。
- 缺逻辑/影响：HTTP 客户端、返回 ID 绑定、鉴权和传输边界缺失，远程主链路无法开始。
- 优先级/阻塞：P1，阻塞远程核心链路。
- 建议：Fix 选择真实模块边界，注入 HTTP transport，锁定服务补丁版与 OpenAPI。
- 验收/测试：将 `test_mineru_contract.py` 的提交、多文件、响应错误、ID 关联场景运行于真实客户端；当前产品 gate BLOCKED。
- DB/兼容性：客户端本身无需 DB；新增能力保留本地入口，不使用已删除 Jobs API。

### GAP-002 — 模式配置、超时与恢复（MINERU-FEAT-002）

- 依据/名称：用户明确要求 MINERU_MODE mock/remote、上传失败处理、可恢复查询。
- 状态/位置/证据：代码缺失，新需求；`config/settings.py` 无相关配置；参考 driver 有界轮询/断传 Mock 已执行，但生产实现不存在。
- 缺逻辑/影响：缺少配置错误检查、任务恢复与有界重试策略；请求超时后可能失去任务关联（风险，非已发生事故）。
- 优先级/阻塞：P1，是。
- 建议：持久化 task_id、按 GET 当前快照决定上传动作、创建结果不确定时不盲目重提，mock 禁网。
- 验收/测试：参考超时/恢复/PUT 失败场景接真实客户端；新增 mock/remote 切换、remote 缺 URL、签名过期刷新、进程重启续查测试，均 BLOCKED 待实现。
- DB/兼容性：需复用 GAP-004 持久化；配置为新增项，保持原本地配置可运行。

### GAP-003 — FastAPI 上传与授权（MINERU-FEAT-003）

- 依据：新用户需求明确要求上传→任务 ID→状态/结果、用户隔离。
- 状态/证据/位置：尚未开发的新需求；现有 `scripts/ingest_legal_documents.py` 为 CLI，文档明确没有 HTTP 服务。
- 缺逻辑/影响：无业务上传、身份验证/所有权、任务查询或返回结果路由；阻塞 HTTP 链路。
- 优先级：P1，阻塞核心新链路。
- 建议：Fix 提供实际路由/授权设计后接入客户端；不能凭空选择既有接口名称。
- 验收/测试：实际 app 的上传、查状态、结果、未授权/跨用户拒绝、重复请求、故障响应测试；当前 BLOCKED，无虚构 API 测试。
- DB：关联用户/原始文件/任务需要评估；接口兼容性：新增 API，CLI/本地解析保持兼容。

### GAP-004 — 远程元数据与状态持久化（MINERU-FEAT-004）

- 依据：用户要求原始文件、本地/远程 task/file ID、哈希、状态和恢复可追溯。
- 状态/证据/位置：功能缺失，新需求；`storage/database.py::VERSION_SCHEMA` 只有 KB 版本/文档/chunk/关联/发布记录；`indexing/service.py` 仅追踪 KB 构建。
- 缺逻辑/影响：没有远程 ID→原始文件→产物的持久关联，不能验证重启恢复与任务重试幂等。
- 优先级/阻塞：P1，是。
- 建议：先交复用/迁移影响方案，保持现有 KB 发布事务边界；候选字段不等于强制新增表。
- 验收/测试：隔离 PostgreSQL 的部分失败、回滚、重复请求、重启恢复、版本/文件关联测试；环境与实现双重 BLOCKED。
- DB/兼容性：可能需要 migration，必须先评估；旧记录与 query.ask 返回字段保持兼容。

### GAP-005 — MinerU 结果到知识库的审核与标准化（MINERU-FEAT-005 的结果集成部分）

- 依据：新链路要求下载→Markdown/JSON→清洗→切分→入库；原设计禁止静默摊平表格。
- 状态/证据/位置：部分实现；`document_parsing/schemas.py`、`normalizer.py`、`bridge.py::to_legal_document` 可用，但 bridge 显式要求复核并拒绝表格，CLI `input_documents` 仍走 load_file，未消费远程产物。
- 缺逻辑/影响：下载安全、按 file_id 关联、输出格式适配、审核后衔接缺失；不能把本地 bridge 独立存在视为整链路已经通。
- 优先级/阻塞：P1，是（远程到 KB）。
- 建议：重用现有结构/审核流程，明确支持格式和表格处理策略；保留本地原生/OCR回退，不静默更改数据语义。
- 验收/测试：安全下载 Mock 已执行；还需真实适配器的完整产物/格式校验、路径/ZIP 资源限制、中文表格、失败不入库、审核后到 SQLite 检索全链路和本地回退测试。
- DB/兼容性：结果位置/版本关联可能需 GAP-004 变更；不破坏旧 LegalDocument、chunk 元数据和检索引文。

### GAP-006 — 阿里云 MinerU Standard 交付（MINERU-FEAT-006）

- 依据：用户部署与 A10 24GB 风险要求。
- 状态/证据/位置：尚未开发的新需求；`Dockerfile` CPU，`compose.yaml` 无 MinerU GPU。
- 缺逻辑/影响：固定镜像版本、GPU/健康检查/持久化/私网访问/兼容性检查未交付。
- 优先级/阻塞：P2，阻塞真实 Standard 验收，不阻塞 Mock。
- 建议/验收/测试：依据官方 Docker 交付配置并做静态检查，ECS 上测 health、tiers、版本和真实受批准样例；A10 需实测峰值显存及并发。当前 NOT_TESTED，不能宣称已部署。
- DB/兼容性：部署本身不要求业务 DB 变更；固定 4.1.x 具体补丁并记录与客户端兼容性。

### GAP-007 — Docker 构建资源目录缺失（DOC-002 / R01-003）

- 依据：现有 Docker 本地部署文档和 Dockerfile 的构建输入要求。
- 状态/证据/位置：代码资源缺失，旧打包链路缺陷；`Dockerfile` 中 COPY scenarios，`git ls-files scenarios` 为空，当前目录不存在；预检实际 FAIL。
- 缺逻辑/影响：隔离检出不能提供 COPY 输入；`scripts/smoke_local_model.py` 也引用该示例资源。尚未执行 Docker 构建，未声称运行时错误已验证。
- 优先级/阻塞：P1，阻塞可复现的现有镜像构建。
- 建议：明确是否需要示例；提供安全的合成资源或移除过期构建/演示引用，绝不复制真实资料补位。
- 验收/测试：`test_round01_integrity.py::test_DOC_002_docker_copy_sources_exist` PASS；审查其余脚本资源引用，并在隔离环境构建确认。
- DB/兼容性：不需要 DB 变更；需保持受支持演示/部署命令一致。

### GAP-008 — 普通材料/Excel/表格入库边界（待确认需求）

- 依据：用户要求检查而非无条件新增所有格式；旧架构声明法律切分与表格边界。
- 状态/证据/位置：部分实现/待确认需求；`document_router.py::SUPPORTED` 不含 Excel；`bridge.py` 拒绝表格；`indexing/legal_structure.py` 要求法条结构。
- 缺逻辑/影响：普通材料和 Excel 无通用切分/入库适配；本语料没有 Excel/Word，不能判定“原有能力退化”。
- 优先级/阻塞：P2 待确认，是否阻塞业务取决于正式支持范围；不阻塞受支持法律文本链路。
- 建议：Fix 先记录支持矩阵，由用户/需求确认后再安排泛文档/表格策略，不擅自扩大开发。
- 验收/测试：范围确认后补合成 Excel、普通材料和表格保真/父子关联用例；当前 NOT_TESTED。
- DB/兼容性：待设计评估；保留旧法律检索/引用契约。

## 其他完整性审查结论

- 实际执行 `test_business_modules_import_without_external_services`：所有 qa_core 模块可导入，未发现本次导入路径的缺失模块或循环导入；这不证明可选引擎全部运行成功。
- 生产源码 TODO/FIXME/NotImplementedError 搜索未命中；两处 pass 为 `native.py::pdf_page` 单元格 bbox 容错与解析 CLI 内存采样进程消失/权限异常容错，无证据认定业务占位。
- 原有 SQL/业务映射经 SQLite 原套件运行；未证明 PostgreSQL 类型/迁移兼容性，仍 BLOCKED。没有执行生产写入。
- 本地 DocumentResult 状态缺陷见 DOC-001；未发现“定义了 HTTP 路由但处理函数为空”，因 HTTP 路由本就未定义。
- MySQL/Redis Compose 服务尚未接入 KB，部署文档已明确独立服务；无明确接入需求，列为不在本轮范围，不要求 Fix 增加使用。

阶段统计：8 个 GAP，6 个明确新需求、1 个现有打包缺陷、1 个待确认范围；目前未补充 8 个、已补充 0 个。Bug 共 3 个，修复数 0，修复率 0%；无 Fix 提交，不做最终验收。各 GAP 当前验收均 BLOCKED 或 NOT_TESTED，任何参考 Mock PASS 不改变产品 GAP 状态。
