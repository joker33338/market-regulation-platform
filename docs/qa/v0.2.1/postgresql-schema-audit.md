# v0.2.1 PostgreSQL Schema 使用一致性审计

审计日期：2026-11-10。主要连接快照：北京时间 16:55:44，随后补查视图、任务关联及 QA 留存表。**最终审计结论：PARTIAL。**

已对真实数据库执行只读 SELECT，核对 DBX、Windows 私有配置连接、Docker 活动应用的实际进程配置和现有 Database 封装。当前确认：审核数据位于 `document_review`，正式法规知识库目标为 `public`，两套 `mvp_test_*` 是同库测试数据域；本次没有发现这些已核连接选错 Schema 或已有跨 Schema 外键。不能签发完整 PASS：知识库调用仍依赖隐式 search_path，实际离线源连接未验证，正式 public 知识库尚无数据，数据库审核队列覆盖也不完整。

本轮仅生成报告和忽略目录中的审计证据。没有修改业务代码、配置、连接字符串、search_path、权限、表／视图结构、原始资料或 QA 报告；没有运行写入测试、初始化、发布、回滚、数据库迁移、镜像切换或 MinerU 调用。文中的写入 SQL 均为源码审阅对象，没有在本次审计执行。

## 1. Git 身份与最新 QA 结论

| 项目 | 实读身份 |
| --- | --- |
| Fix 分支 | `codex/fix-v0.2.1` |
| 审计开始时 Fix HEAD | `c8e624b066a795161901b55bd472ec730b1889ea`，工作区干净 |
| 当前业务源码提交 | `bf66e10753757c2e1f92383755817dd8c31ab336` |
| 最新 QA 分支及报告提交 | `codex/qa-v0.2.1`，`28aece1ececdd02768cb327951b55e7be631e8fb` |
| 最新失败回归／问题交接 | `80b9f827ffbb9ccad955a38a7af85e29cf99fd8c` |
| QA 本轮测试环境起点 | `7ceef1a002b837726d5febcd91aa108335553ca7` |

已检查 git status、分支、完整 HEAD 及 worktree list；Fix 与 QA 是独立工作区，未切换分支或修改 QA 工作区。审阅的是上述 v0.2.1，未用 main／历史 v0.2.0 代替。

最新 QA 报告 `release-closure-qa-report.md` 和 version-gate.json 的结论为 **FAIL**，并有集成 BLOCKED：276 个唯一方法中 268 PASS、1 FAIL、7 SKIP；候选镜像既有 158 PASS 为重叠覆盖，不相加。真实 auto 的本地优先、获准合成文件云回退、两候选保留与幂等已通过；候选真实 HTTP／PG 和容器 restart 也有通过记录。旧任务恢复 GET403，Windows 整机恢复未测。此前六项 PG 生命周期 PASS 属于其记录的旧源码范围，不能冒充本轮又执行。

唯一新增确认安全阻断 **QRC-001（P1）**：`MinerUService._local` 的最终 normalized 缓存恢复绕过当前资源限制，四个子场景进入记录型 sink。QA 明确没有违规写入真实业务库。该问题不是 Schema 解析缺陷；本次按严格只读任务记录、未修复，也不通过本报告改变 QA 的 FAIL。质量分级以最新 QA 使用的用户确认策略为背景，本次不重新裁定 OCR 阈值、不修改历史真值或报告。

## 2. 当前连接与关系解析

| 实测入口 | 数据库／用户 | current_schema | search_path | effective_schemas |
| --- | --- | --- | --- | --- |
| DBX 工具连接 PostgreSQL_d432 | market_regulation / market_app | public | `"$user", public` | pg_catalog、public |
| Windows `local/parsing-runtime.json` 的现有解析连接 | 同上 | public | 同上 | 同上 |
| Docker 活动 uvicorn 进程的解析连接 | 同上 | public | 同上 | 同上 |
| Database 封装，显式复用上述已批准本机连接，只读事务 | 同上 | public | 同上 | 同上 |

Windows 配置端点为 `127.0.0.1:15432`；容器配置为 `db:5432`。数据库名、用户、数据库 OID 16384、目标关系 OID 一致，结合现有 Docker 映射确认是同一个数据库。不是三个数据库，也没有改绑连接。

用户此前观察到的“默认 Schema=document_review”保留为特定界面／会话的历史现象；**本次 DBX 工具后端实测为 public**，不推断用户所有手工 SQL 页签都与该工具连接共用会话状态。未用 SET 验证其他路径，未修改手工连接配置。

DBX SELECT 时 transaction_read_only=off，但本轮只执行 SELECT；Python 审计连接为独立 REPEATABLE READ、READ ONLY 事务，结束 rollback/close。后者仅是审计连接的只读保护，不代表正常应用写入连接也为 readonly。未发现适用于当前库／角色的持久 search_path 专项设置；`"$user", public` 在当前用户 Schema 不存在时有效落到 public。

| SQL 名称 | DBX、Windows、Docker 的实际解析 |
| --- | --- |
| `documents` | NULL；不会隐式找到 document_review.documents |
| `document_review.documents` | document_review.documents，OID 17377 |
| `document_review.pages` | document_review.pages，OID 17385 |
| `mr_chunks` / `public.mr_chunks` | 同一 public.mr_chunks，OID 16748 |
| `mr_kb_versions` / `public.mr_kb_versions` | 同一 public.mr_kb_versions，OID 16733 |
| 其余未限定的 law_chunks、mr_active、mr_active_chunk_map、mr_document_versions、mr_kb_documents、mr_release_history | 当前均落到 public |
| 默认源表 national_laws_regulations / national_laws_regulations_detail | 在当前 market_regulation 连接下均不存在 |

八个知识库表名分别在 public 和两套测试 Schema 中存在三份。PostgreSQL 按 search_path 优先选择，不会因同名自动报“歧义”；当前路径不包含测试 Schema，所以没有选到测试表。若未来把某套 mvp_test_* 放到路径前部，这些未限定 SQL 的语义会改变；本轮没有人为改变路径来制造或掩盖这个风险。

## 3. 实际 Schema、表、视图和数据域

共观察到 **31 张基础表、4 个视图**，均在同一个 market_regulation 库内。

| Schema | 基础表 | 视图 |
| --- | --- | --- |
| document_review | blocks、cells、documents、findings、images、pages、tables | v_document_summary、v_page_text、v_review_queue、v_table_cells |
| public | law_chunks、mr_active、mr_active_chunk_map、mr_chunks、mr_document_versions、mr_kb_documents、mr_kb_versions、mr_release_history | 本次范围内无 |
| mvp_test_b8cbf9119d9940c7bc5f3c1acc8d436c | 与 public 同名的上述 8 张知识库测试表 | 无 |
| mvp_test_f1e8deef0ead499b8548b3db265c4aef | 与 public 同名的上述 8 张知识库测试表 | 无 |

18 个已查外键的源、目标 Schema 全部相同，未发现从测试 Schema 指到 public 或 document_review 的外键。vector 扩展安装在 public；三套知识库的 law_chunks.embedding、mr_chunks.embedding 均为 vector(1024)。这验证结构维度，不代表已经用真实 BGE 给正式数据完成向量化。

只读数量快照：

| 数据域 | 观察值 |
| --- | --- |
| document_review.documents | 25 |
| pages / blocks / tables / cells | 166 / 2864 / 24 / 1345 |
| images / findings | 33 / 43 |
| 上述六类子记录找不到同域 documents 父记录 | 各 0 |
| public 的 8 张知识库表 | **每张均 0 行** |
| public ACTIVE | 无；现有封装 active_version() 返回 None |
| 第一套 mvp_test_* | law_chunks=1、mr_chunks=1、kb_versions=2、kb_documents=2、document_versions=1、active=1、active_map=1、history=3；状态 ACTIVE=1、ARCHIVED=1 |
| 第二套 mvp_test_* | 上述八表均 1 行；版本状态 ACTIVE=1 |

测试 Schema 中的 ACTIVE 是各自测试投影，**不能当成 public 已发布**。public 的孤立 Chunk、文档版本、ACTIVE／映射版本不一致等只读统计均 0，但分母为空，不将它们解释为已有正式版本完成一致性验收。

## 4. 文件级 SQL 调用清单

以下结合连接来源、封装、动态 SQL 和事务分析。`KB-path` 表示 Database 连接当前 search_path：本次本机连接解析为 public；已批准 QA 生命周期连接显式设置时解析为自有 mvp_test_*。

| 文件 | 函数／入口 | SQL 操作及关系 | 目标 Schema | 实际可能解析 Schema／风险 |
| --- | --- | --- | --- | --- |
| qa_core/document_parsing/mineru_api.py | create_app、worker、submit/results 等 | 根据 PARSING_RESULT_PG_DSN 注入 sink；路由不直接运行 PG SQL | document_review | 任务状态走独立 SQLite；不是通过默认 documents 表持久化 |
| qa_core/document_parsing/mineru_service.py | _local、_download | 标准化／检查点后调用 result_sink.save | document_review | 由显式限定的 sink 决定；QRC-001 是调用前安全复验遗漏，非 Schema 选择问题 |
| qa_core/storage/parsing_results.py | PostgresResultSink.save | INSERT document_review.documents/pages/blocks/tables/cells；按 parse_id SELECT/ON CONFLICT | document_review | 固定该域，不受 mvp_test_* 排在 search_path 前部影响；不写 public |
| qa_core/document_parsing/mineru_repository.py | connect/create/get/save/resumable | SQLite parse_tasks | 无 PG Schema | 本地任务仓库，不能把 task_id 与 PostgreSQL parse_id 等同 |
| scripts/preview_offline_ingestion.py | load_result、main | SELECT original_result FROM document_review.documents WHERE parse_id=%s | document_review | READ ONLY 连接、rollback/close；后续切分只写忽略目录预览，不入 RAG |
| scripts/verify_upload_database.py | main | 显式 document_review.documents/pages/blocks 聚合读取；前段会调用上传 API | document_review | 查询名明确；整个脚本不是只读，本轮未运行 |
| scripts/verify_mineru_cloud.py | verify | 按 --database 显式调用 sink | document_review | 云验证与知识库发布无直接关联，本轮未运行 |
| scripts/configure_parsing_local.py | main | SELECT to_regclass('document_review...') | document_review | 初始化本地私有配置的工具，不创建该 Schema；本轮只读源码 |
| deploy/local/prepare.py | runtime_values、main | parse_dsn 重绑本机容器端点；SELECT to_regclass 检查既有审核表 | document_review | 保留连接 options，无 Schema 钉扎；本轮未执行准备／改写配置 |
| qa_core/storage/database.py | __init__、execute、one、all、transaction | psycopg2 单连接；命名参数转换；BEGIN/COMMIT/ROLLBACK；只读检索事务 | KB-path | 不设置或校验固定 Schema，SQL 表名基本未限定；P1 依赖 |
| 同上 | initialize；VERSION_SCHEMA | CREATE EXTENSION vector；CREATE TABLE/INDEX law_chunks、7 张 mr_* | 创建路径中的首个有效 Schema | 只在显式 init-db 使用；与读写关系查找都依赖连接路径，本轮未执行 |
| 同上 | active_version、version、list_versions | SELECT mr_active、mr_kb_versions | KB-path | 当前 public；测试路径可选测试版本 |
| 同上 | create_version、attach_revision | INSERT mr_kb_versions、mr_kb_documents；读取 active/base | KB-path | 当前 public；没有独立 Schema 参数／关系 OID 守卫 |
| 同上 | revision_exists、cached_vector、save_revision | SELECT/INSERT mr_document_versions、mr_chunks；INSERT/UPSERT mr_kb_documents；CAST(... AS vector) | KB-path；vector 类型来自扩展域 | 默认当前正确；错误路径可复用另一域的版本／向量缓存 |
| 同上 | finish_version、fail_version | JOIN mr_chunks/mr_kb_documents；UPDATE mr_kb_versions | KB-path | 同一连接执行，不等于保证所有同名表都来自同域 |
| 同上 | publish | LOCK law_chunks；DELETE/INSERT law_chunks、mr_active_chunk_map；UPDATE mr_kb_versions；UPSERT mr_active；INSERT mr_release_history | KB-path | 未限定的发布 DML/LOCK 风险最集中；本轮只审 SQL，不切 ACTIVE |
| qa_core/storage/postgres_schema.sql | 显式 init-db 读取 | law_chunks DDL、vector(1024) 和索引 | 创建路径 Schema | 无 schema 前缀；不是 FastAPI 自动迁移脚本 |
| qa_core/indexing/service.py | ingest_documents | 调 Database 生命周期，执行 BGE 后保存 revision，最终 STAGED | 随 Database | 参数 namespace 是文档身份命名域，**不是 PostgreSQL Schema** |
| qa_core/retrieval/models.py | create_embeddings、embed_documents | 无数据库 SQL；返回并校验向量 | 无 | 不会自行选择 public 或测试 Schema |
| qa_core/retrieval/store.py | retrieve、vector_search、keyword_search；JOINS | SELECT law_chunks JOIN mr_active_chunk_map/mr_chunks/mr_kb_documents；读取 ACTIVE／模型签名 | KB-path | 只读一致性事务；表与 vector 类型都依赖连接路径 |
| qa_core/governance/kb_versions.py | publish、rollback | 转调 Database.publish | KB-path | 无独立连接、无第二个 Schema 路由 |
| scripts/ingest_legal_documents.py | open_database、main | PG_DSN 显式 --postgres；init/ingest --write/publish/rollback 分开 | 正式预期 public | 默认预览不打开目标数据库；目标未硬编码 schema；本轮未执行写分支 |
| scripts/rebuild_kb_version.py | main 转发 | 复用上项 ingest | 同上 | 不新增数据库或隐藏迁移 |
| qa_core/indexing/source_adapters.py | source_sql、load_pg_documents | 动态 FROM detail JOIN main；标识符正则校验；SOURCE_PG_DSN、服务端只读游标 | 明确源库的目标 Schema 待确认 | 表名不含 schema，接口当前还不接受 schema.table；若传目标 market_regulation，默认两源表不存在 |
| query.py | ask | PG_DSN 或明确 SQLite；调用 retrieve | KB-path | 不自动读取旧 .env；当前活动工作台没有 PG_DSN |
| scripts/ingest_parser_result.py | main | 经 reviewed_legal_document 后 ingest | **仅显式 SQLite** | 不能将此 CLI 说成已实现 document_review→PostgreSQL 审核发布闭环 |
| qa_core/document_parsing/bridge.py、qa_core/indexing/ocr_review.py | to_legal_document、read_review | 无 SQL；复核人、结果状态、表格限制、sidecar 摘要检查 | 无 | 复核记录在结果 metadata／sidecar；未更新 PG findings.review_status |
| tests/test_parsing_postgres.py、test_round01_postgres_acceptance.py | sink 集成用例 | 显式 document_review.*，原子回滚与幂等验证 | 由专门批准连接中的 document_review | 不写 mvp_test_*；在业务库运行会有意保留合成审核记录，需专门执行入口 |
| tests/test_postgres_integration.py | test_isolated_schema_build_publish_query_rollback | 新建随机 mvp_test_*；SET search_path；调用未限定生命周期 SQL；finally 清理 | 自有测试 Schema | 默认测试名不是权限隔离；legacy 入口带 DROP，本轮严禁运行 |
| tests/run_preserved_postgres_validation.py | PreserveSchema | qa_round01 身份守卫；复用 vector；抑制清理 DROP | 原专用 QA 库 | 与当前同业务库的批准适配器不同，不能混为本轮实际入口 |
| QA tests/run_offline_business_postgres.py | ScopedLifecycleDatabase、own_bindings、synthetic_save | 身份、授权范围、冻结 SHA、逐关系 OID 检查；业务域快照；限定测试 Schema 操作 | 自有 mvp_test_*；明确合成 document_review | 真实六项执行的关键保护层，详见第 7 节；未在本轮重跑 |
| tests/run_v021_final_acceptance.py、QA 同名最新入口、scripts/run_fix_regressions.ps1 | 回归环境准备 | 清空写入测试 DSN；不直接执行业务 PG SQL | 默认不运行 PG 用例 | 最新回归 7 SKIP 不与此前六项真实执行混算 |

## 5. 文档解析与人工审核链路

实际调用为：上传与任务 SQLite → DocumentParser／双引擎 → normalized 检查点 → PostgresResultSink → document_review。数据库 `parse_id=stable_hash('parsing-result-v1', owner, task.id, file.id)`；document_id 是原文件摘要，source_location 保存 owner_id、local_task_id 和 source_file_id。**source_file_id 可能不同于任务内部 file.id，不能用 source_file_id 代替 file.id 重算 parse_id 后宣称关联错误。**

sink 每次新建 PG 连接，文档、页、块、表、格在同一连接事务内写入，异常由连接上下文回滚，finally close；不是复用有旧 search_path 的连接池。冲突时比较原 report_sha256，不覆盖历史成功结果。源码 SQL 固定限定 document_review，因此与 public 的 Chunk 表没有混用。

只读关联核验：25/25 document_id 与 original_result.document_id 相同；六类子记录的孤立父文档数均 0，166 页的负／零页码和可比较的来源页号不一致均 0。24/25 文档具有上述三个任务关联字段，1 条不完整记录的历史来源未在本轮确认，不能直接回填或宣称是新 sink 的失败。

在当前活动 state 的 3 个 SQLite 任务库中只读找到 5 个任务；能够与 4 条 PG 文档定位匹配的 parse_id 全部正确，0 个不匹配。其中 3 条的 source_file_id 与 file.id 不同，属于合法字段差异。另 21 条未在该活动 state 找到对应任务，包括历史／QA 场景的可能来源；其关联完整性不能借这 4 条的成功外推，亦不能据此认定资料丢失。

七张审核表的写入覆盖：

| 表 | 本版本 sink 是否写入 | 观察／限制 |
| --- | --- | --- |
| documents、pages、blocks、tables、cells | 是，显式同 Schema | 已审事务和关联；审核结果留存不等于正式知识库发布 |
| images | 否 | 当前已有 33 行，但来源未归属本 sink；图像信息可能保留在 original_result／工件，不能把文件工件存在等同于该表写入 |
| findings | 否 | 质量信息保存在 documents.quality／original_result；没有把 findings 数组同步到独立表的 SQL |

四个视图的依赖 OID 和 pg_views.definition 都指向正确 document_review 基础表：summary 引用七表；page_text 引用 documents/pages；table_cells 引用 documents/cells；review_queue 是 **findings INNER JOIN documents**。未发现这两业务域的自定义触发器或重写规则帮 sink 自动补 images/findings。

因此审核覆盖需要单列：18 条 requires_review=true 的文档中，17 条没有 findings，17 条不会出现在 v_review_queue；该视图只覆盖 1 个有 findings 的文档。**这不是表写到了错误 Schema，也不等于正文丢失；但只查询此视图不能得到全部待复核文档。** 现有代码未实现 PG 中完整的人工审核状态更新 API，也未用数据库 findings.review_status 自动驱动正式 PG 入库。若将其作为产品完整审核入口，须先确认并补齐需求，不能因 view 存在即宣布闭环完成。

## 6. 法规离线入库、BGE 与版本发布链路

当前已实现的 PostgreSQL 目标链路是人工选择输入 → clean/split → BGE-M3 → mr_document_versions/mr_chunks → mr_kb_documents/mr_kb_versions(STAGED)；显式 publish 后才更新 law_chunks、active_map、mr_active、release_history。metadata 中的来源与 Parent-Child 信息和向量同 Chunk 保存。真实 1024 维非 demo 的 PG 门禁存在，测试夹具的合成向量不代表正式 BGE 文本质量。

| public 目标表 | 作用 | 关联与访问方式 |
| --- | --- | --- |
| mr_document_versions | 文档修订、source_hash 与元数据 | Chunk 的 doc_version_id 外键目标 |
| mr_chunks | Chunk 文本、metadata、input_hash、embedding | doc_version_id；同输入向量缓存；vector(1024) |
| mr_kb_versions | BUILDING/STAGED/ACTIVE 等版本状态和模型签名 | 与 mr_kb_documents 关联，发布前校验 base_version |
| mr_kb_documents | 版本到文档修订映射及来源 | kb_version、doc_version_id 外键 |
| law_chunks | 当前供兼容检索的投影 | publish 从目标版本 Chunk 重建，拒绝覆盖未接管旧行 |
| mr_active_chunk_map | 兼容键到 Chunk／版本映射 | Chunk 外键；用于检索 JOIN |
| mr_active | 当前 ACTIVE 指针 | 发布事务内 UPSERT，代码校验对应版本 |
| mr_release_history | 发布／回滚审计 | 同发布事务插入 |

上述表名在 Database 与 retrieval 的源码中均未限定为 public。当前连接下解析正确；只读事务只能保证事务一致性，不能防止同一个 search_path 中有部分关系来自不同 Schema。现有外键能保护其声明范围，mr_active 的版本选择及其他逻辑关系仍须由同域解析和发布代码保证。

publish 使用单连接事务、pg_advisory_xact_lock、law_chunks 表锁及兼容键保护；正常情况下发布投影、ACTIVE、history 一起提交。没有看到调用中途切换连接或 search_path 的正式代码。检索在 REPEATABLE READ READ ONLY 事务内读取 ACTIVE、模型签名和投影。但是代码不锁定 Schema，错误配置下仍可能读到测试 ACTIVE；本轮未执行发布或模拟错误路径。

public 目前八表均空，无法用正式生产数据验证实际版本／向量关联，亦不能说“文件上传后已完成 public 入库”。预览不会写这些表；解析库有结果、QA 测试 Schema 有 Chunk，与正式 public 构建／发布是三件不同的事。已实现的 parser-result CLI 只接受显式 SQLite，不能虚构其已从 PG 审核表自动构建正式 PG 版本。

## 7. QA 测试隔离审计

原 `test_postgres_integration.py` 使用 UUID 生成 schema，建立新连接、CREATE SCHEMA、SET search_path 到“自有 schema, public”，显式 initialize 后测试构建、发布、检索、回滚。正常 finally SET public、DROP 自有 schema 并关闭。它没有把每个 SQL 改为完整限定名，而是依赖连接路径；public 用于找到已有 vector 扩展。该 legacy 入口本轮没有执行。

其 finally 还需注意：恢复的是 public，不是任意调用前路径；但连接专用且随后关闭，未发现连接池复用。若 SET 或清理 DROP 抛异常，后续 close 可能被跳过，是异常资源管理的候选改进；不据此认定已发生 Schema 污染。

**实际批准的同业务库六项入口**是 QA 的 `run_offline_business_postgres.py`：

1. 必须显式启用授权执行参数，并匹配原批准 scope、连接参数、实际库／用户／端点以及冻结源码 `8ecff886...`；不能直接拿它冒充 bf66 当前源码再次验收。
2. 核对既有 public.vector，拒绝自动安装；只允许生成、首次不存在且格式为 mvp_test_ 加 32 个十六进制字符的 Schema。
3. ScopedLifecycleDatabase 要求 current_schema 为其 owned Schema；initialize 完成后和后续操作前，检查八个未限定表的 to_regclass OID 均属于同一 owned Schema，防止缺表时回退到 public。
4. 拒绝明确引用 public/document_review 的生命周期 SQL 和非预期 destructive DDL；本 Schema 的测试投影 DELETE 是原发布用例的一部分，并非清业务表；清理 DROP 被转换为无副作用 SELECT，留存证据。
5. 解析 sink 用例是另一条明确批准路径，有意向 document_review 留下随机合成记录；检查 owner、文件来源、连接及 parse_id 冲突，失败应回滚，不是“误写审核域”。
6. 对原 public/document_review 关系和已有行摘要做前后核对，保留注册的新合成行、测试 Schema 及真实 ACTIVE 不变的证据。不是只凭测试通过就推断无影响。

两套留存 Schema 的结构及 FK 目标符合这一隔离方式；本轮只读看到的测试数据与历史报告相容，但没有重跑 lifecycle 或重新验证历史每次操作。

风险边界：当前 market_app 是 **superuser，且可创建数据库／角色**，对四个 Schema 都有 USAGE/CREATE。测试隔离是独立连接、Schema 选择与应用守卫，不是数据库权限禁止写 public。变量名字带 TEST、或有 mvp_test_* 前缀，本身不足以证明隔离；应继续通过批准适配器执行，不能将通用测试 DSN 全局设置为业务连接后直接 discover。

## 8. 配置、部署及进程差异

| 配置／入口 | 本次确认 | Schema 影响 |
| --- | --- | --- |
| .env.example | PG_DSN、PARSING_RESULT_PG_DSN 分开；无统一 Schema 参数 | 不能从示例推断实际连接路径 |
| Fix／原工程 .env | 本次未发现这两个 .env 文件；Settings 不自动加载旧 .env | 未观察到旧 .env 暗中覆盖 |
| 现有 Windows runtime JSON | 解析 DSN 明确本机 market_regulation；无 options/search_path、无 PGOPTIONS | 本次同配置新连接为 public |
| Docker runtime JSON | 同库转换为 db:5432，保留其他 DSN 属性；无 options/search_path | sink 显式 document_review |
| Docker 实际 uvicorn exec 环境 | 直接从运行进程读取，只输出变量是否存在；只有解析 DSN，PG_DSN/SOURCE/三种 TEST DSN 均未启用；无 PGOPTIONS | 不是仅凭 docker inspect 静态 Env 推断 entrypoint 之后的环境 |
| deploy/local/entrypoint.py | 移除旧 PG_DSN、SOURCE 和测试 DSN；从只读文件加载解析配置 | 当前有效的隔离措施；未设置统一 search_path |
| scripts/start_parsing_app.ps1 | 将指定 JSON 项导入新进程；不统一钉扎 Schema | 其他启动进程是否继承自定义 PGOPTIONS 不能由本次 Codex 环境一概代表 |
| scripts/start_agent_workspace.ps1 | 清空 PG_DSN/SOURCE_PG_DSN/MVP_TEST_PG_DSN；其余具体 QA 入口另清空写入变量 | 不等于全机器环境永久修改，本轮未执行启动脚本 |
| 根 compose.yaml 旧 app 声明 | PG_DSN 和 MVP_TEST_PG_DSN 都可指向业务库；CMD 为休眠基础容器 | 当前不是活动工作台入口；未来直接用该声明运行通用测试有风险 |
| compose.local.yaml | 活动 app 使用只读 runtime、只读模型、持久 state；数据库网络外部复用 | 当前没有通过该文件启用测试 DSN 或全局 PGOPTIONS |
| 原私有 Docker 配置中的 SOURCE_PG_DSN | 观察到另一个外部源端点／库配置，但活动进程未启用；本轮未连接 | 超出本次明确的 market_regulation 实测范围，来源 Schema 仍未核验；报告不披露外部地址或凭据 |

当前审计进程的 PG_DSN、SOURCE_PG_DSN 和三种测试 DSN 都未启用；因此未发现一个正在使用已确认参数的 Windows 正式离线 PG 写入进程。本轮只是通过已批准解析连接验证 Database 包装器的只读查询语义，不能将其说成未来所有 CLI 的实际环境都已验证。

未发现业务代码使用 SQLAlchemy 或 PostgreSQL 连接池。psycopg2 的解析 sink／源适配器每次独立连接并关闭，Database 维护调用者拥有的单连接，事务有 rollback；未发现正式源码临时 SET search_path 后返回连接池的路径。现有 SET search_path 均在 QA 生命周期脚本及保护适配器中。

活动镜像仍为 `market-regulation-workbench:local-4ecd995cb4be8ee4`，ID `sha256:04392161ca0e4acc37530679fbb11564e8341389a76aa475469d0bbeafa74af6`，revision `350f5ad3d8d0859e6dbbb2a879367e901913b556`。候选为 `market-regulation-workbench:candidate-v021-bf66e1075375`，ID `sha256:ff555f5d00330c199ae5933b97b6a9fc6fa125d9710109f7fcf2213e5ac5f342`。没有切换。Git 对比确认相关 storage、schema SQL、retrieval、source adapter、API 的 PG 调用与活动旧 revision 无差异；本轮其它离线切分／安全变更不能由此认定已经部署。

## 9. 风险、最小建议和验收边界

**未确认 P0 跨 Schema 实际误写。** 以下 P1 是确定存在的路径依赖或部署风险，不声称当前已发生数据污染；其余实测覆盖缺口单列，避免把“未证明”写成 Bug。

| 编号／级别 | 文件、函数、SQL／实测解析 | 最小建议（仅建议，未实施） | QA／迁移 |
| --- | --- | --- | --- |
| SCA-001 / P1 | storage/database.py：initialize、active_version、save_revision、publish 等，以及 retrieval/store.py 的 JOINS；未限定 SELECT/INSERT/UPDATE/DELETE/LOCK mr_*、law_chunks。当前为 public；三套同名关系存在，构造器无目标 Schema 校验 | 为 PG 引入明确、验证过的目标 Schema 身份，正式默认 public、测试显式自有 Schema；至少在操作前校验所有关系 OID 同域并拒绝错误绑定。后续统一关系限定名，保留 SQLite 兼容及已存在 public.vector 的类型解析；不能简单硬编码 public 而破坏 QA 隔离 | 需独立 QA：正常 public、完整测试域、缺表回退、错误路径 fail-closed、版本与投影同域。代码方案通常无需迁移；本轮不通过 SET 改配置 |
| SCA-002 / P1 | 根 compose.yaml 的 app 同时提供业务 PG_DSN 与 MVP_TEST_PG_DSN；默认 test_postgres_integration 仅按变量启用。角色有超管权限；当前 local entrypoint 已清除这些变量，所以该配置不是正在发生的误写 | 独立维护测试连接的显式 opt-in；避免常规应用默认提供写入测试 DSN，继续复用实际 QA 关系绑定守卫。数据库最小权限角色可另行设计，不能在本轮直接撤权或换连接 | 需启动配置及 QA 误运行保护回归。去掉错误默认启用不需表迁移；权限调整须单独授权、评估现有进程 |
| SCA-003 / P2，审核覆盖缺口 | parsing_results.py::save 不写 images/findings；现有 v_review_queue 仅 inner join findings。实测 18 条需复核中 17 条不在视图；Schema 均正确 | 明确该视图是“finding 级队列”还是产品完整待审入口。完整待审应至少从 documents.requires_review 查起；确认字段与需求后再决定复用现有表同步 findings/images，且保持原子性及原始 JSON。不伪造 finding、不改 view 来掩盖旧记录 | 若确认要补功能，需独立 QA 覆盖有／无 findings、复核状态与历史兼容。代码查询方案可不迁移；更改视图／权限则需单列数据库变更审批 |
| SCA-004 / P2，源配置核验不全 | source_adapters.py::source_sql/load_pg_documents 动态 JOIN 简单表名，未限定 Schema；SOURCE 外部配置未实测，目标库内两默认源表 NULL | 在后续批准源连接时记录真实库／Schema／表及只读权限；考虑增加分别校验的 schema/table 参数或在读前核验来源 OID，保留当前标识符防注入。不修改当前 DSN，也不擅自连外部服务器 | 需只读源映射 QA；通常无目标库迁移。若实际外部源核验超出既有许可，先明确范围 |
| 关联完整性待确认，非新定级 Bug | 1 条文档缺任务关联字段；21 条不在当前活动 state 中。25/25 原始 document_id 一致，已定位 4 条任务关联全部正确 | 保留历史数据；仅在能找到原任务／导入证据时追溯。不得按 source_file_id 代替 file.id 算 hash，更不得直接改 parse_id 或补造关联 | 不需要本轮回填；后续有证据再决定独立修复和 QA |

P0 的判定不能仅凭 market_app 权限大、测试 Schema 存在或未限定表名就成立；本轮没有执行错误配置或数据污染实验。反过来，当前路径正确也不能消除 SCA-001 的部署依赖。

## 10. 只读证据与后续授权

原始审计证据在 Fix 忽略目录 `local/schema-audit/`，未提交数据库内容或凭据：

- `dbx-metadata.json`：DBX 连接身份、表／视图清单、解析 OID、视图依赖、适用 search_path 设置、权限和扩展位置。
- `runtime-metadata.json`：Windows、Docker 运行进程配置的脱敏摘要、全部列／FK／向量类型、计数和 public 版本一致性聚合。只保留连接必要的非敏感身份，不包含密码、Token 或完整 DSN。
- `supplement.json`：视图定义、重复表名、页号、封装层只读结果和关联诊断。source_file_id 试算不能作为内部 file.id 的身份验证；以 coverage 的真实任务定位为准。
- `coverage.json`：从当前 SQLite 原任务定位的四条 parse_id、审核队列缺口、留存 QA 数量和同域 FK。
- `audit_readonly.py`、`audit_supplement.py`、`audit_coverage.py`：本地只读重现脚本，仅元数据／聚合 SELECT 和 SQLite mode=ro；没有业务初始化或写入用例。外部源连接未执行。

复核核心事实可用以下 SELECT，不必运行任何初始化或 QA 写入测试：

```sql
SELECT current_database(), current_user, current_schema(),
       current_setting('search_path'), current_schemas(true);

SELECT x.name, n.nspname AS resolved_schema, c.relname
FROM unnest(ARRAY['documents','mr_chunks','mr_kb_versions','mr_active','law_chunks']) x(name)
LEFT JOIN pg_class c ON c.oid = to_regclass(x.name)
LEFT JOIN pg_namespace n ON n.oid = c.relnamespace;

SELECT count(*) FILTER (WHERE d.requires_review) AS requires_review,
       count(*) FILTER (WHERE d.requires_review AND NOT EXISTS (
         SELECT 1 FROM document_review.v_review_queue q WHERE q.parse_id=d.parse_id
       )) AS not_in_finding_queue
FROM document_review.documents d;
```

本次只读审计及报告生成已获授权，没有剩余必须获批才能完成的本轮操作。尚未授权本轮直接修复代码／配置／权限、改视图或做迁移；这些属于下一步决定。对于已交接 QRC-001，本轮同样没有借审计顺带修复。

**最终结论：PARTIAL。** 已核实的三个连接上下文当前正确分离审核域、public 和测试域；没有发现当前错误 Schema 解析的实证。正式知识库空、源配置未核验、隐式关系解析依赖和数据库审核覆盖缺口，使完整业务链无法获得充分验证。该专项结论不改变 QA 对当前 v0.2.1 的整体 FAIL。
