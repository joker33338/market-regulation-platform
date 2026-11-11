# v0.2.1 安全与 Schema 风险修复交接

日期：2026-11-11。Fix 结论：**READY_FOR_QA**。这是源码修复交付，不是 QA_PASS；不修改独立 QA 的 version-gate.json 或正式报告。

## 1. 版本与范围

| 项目 | 身份 |
| --- | --- |
| Fix 分支 | `codex/fix-v0.2.1` |
| 修复前 HEAD | `c8e624b066a795161901b55bd472ec730b1889ea` |
| 修复前业务源码 | `bf66e10753757c2e1f92383755817dd8c31ab336` |
| 最新已读 QA 报告 | `28aece1ececdd02768cb327951b55e7be631e8fb` |
| QRC-001 正式失败测试／交接 | `80b9f827ffbb9ccad955a38a7af85e29cf99fd8c` |
| QRC-001 修复 | `b2df03cd3f5942c98b2f7389580dbfea549c7314` |
| SCA-001 修复 | `7b69d68aa322452733365d55dd3c36a61f5b3452` |
| SCA-002 修复／最终业务源码 | `c91547d393ca6b049e216c0051e25271d06d7359` |

本报告与前轮只读审计报告另作文档提交，最终交接 HEAD 从 `git log -1 --format=%H -- docs/qa/v0.2.1/schema-and-security-fix-handoff.md` 取得并在会话交付；不将未来文档 SHA 预写成已知值。文档提交不改变上述业务源码。

最新 QA 仍为 276 个唯一方法、268 PASS／1 FAIL／7 SKIP；唯一确认阻断 QRC-001，真实 auto 与候选既有 PG／容器恢复已有各自证据。未把历史通过结果重算为本轮通过，未改识别质量标准。基线依据为 [只读 Schema 审计](postgresql-schema-audit.md)，该报告保留其原日期及当时事实，不覆盖成修复后的测量。

## 2. 已确认缺陷 QRC-001

根因：`MinerUService._local` 命中 `local_result_path` 时只恢复 normalized.json 并核对 document_id；绕过 DocumentParser 和 DualEngineRouter 的当前输入限制，旧 success 缓存可以直接进入 sink。

先直接运行 QA 已提交的 `test_release_qa_acceptance.py`，在修复前复现 **1 方法、4 个失败子场景**：local/auto/remote 的 100 像素文件与测试上限 50；以及默认上限 20,000,000 对 4500×4500 图。均 completed、sink=1、cloud=0。没有真实数据库调用。

最小修复：

- config.py 的 `validate_input_safety` 读取当前原文件：文件大小、图片头部像素、PDF 页数／可读取性、DOCX 解压体积；不加载 OCR、不缩放或改原件。
- `_local` 最终缓存读取之前调用该检查，并检查当前 service 的文件大小限额。类型化拒绝返回具体错误码及 413，文件／任务失败，不进入 sink。
- 恢复内容继续校验 SHA；拒绝未知结果版本、文件类型不符、空 pages、重复／非法页号及失败页面。损坏 JSON 也失败，不自动重建或覆盖历史缓存。
- 旧 local-candidate 和云回退前的输入检查复用同一 helper，避免另留一份仅图片限制的实现。既有鉴权、调用计数及候选保留不变。
- 合法最终缓存继续复用原字节；重复运行已完成任务不重做 OCR／云调用、不再调用 sink。资源预算不会被清零，也不会为校验缓存新增远端请求。

修后原 QA 四个子场景均 failed、image_pixel_limit、sink=0、cloud=0，原文件和 normalized 字节保持一致。此为 Fix 执行 QA 原测试的结果，独立 QA 仍须重新绑定新源码验收。新增 `test_final_cache_recovery.py` 覆盖正常恢复、JSON／SHA／版本／空页错误及当前文件／PDF 页数限制。

## 3. 预防性修复 SCA-001

当前未发现已有业务跨 Schema 污染；这是针对确定的隐式 search_path 依赖进行防护，不把风险改写成已发生事故。

方案集中在 Database 封装，保持现有 SQL、事务及 SQLite 行为，不全面重写 storage/retrieval/indexing：

1. 新增仅关键字参数 `kb_schema='public'`。正式调用默认 public；QA 必须显式传入 `mvp_test_<32位小写hex>`。构造前校验名称，拒绝任意 Schema／SQL 片段，不从 search_path 自动推断或接受回退。
2. 每次发送涉及八张知识库表的现有 SQL 前，使用原连接原生 cursor 查询当前 Schema、命名空间 OID、目标限定关系 OID、当前可见关系 OID、关系类型及 FK 目标域。
3. 所有八表必须存在于目标 Schema，OID 必须与当前可见关系完全相同；拒绝缺表、public 回退、临时同名表／视图遮蔽、跨域关系或 FK。QA Schema 还必须由当前角色拥有。
4. 检查可见 vector 与 public.vector 的类型 OID 一致。保留既有 public.vector 和 vector(1024) SQL，不改变维度、列或扩展位置。
5. 不缓存一次启动结论。active_version、构建／修订、finish、发布、回滚、检索等八表 SQL 都经发送前检查；publish 还在获取发布锁前显式校验。
6. BEGIN／COMMIT／ROLLBACK 和事务隔离设置不在其前插入探测 SELECT，防止破坏事务首语句要求或阻止失败事务回滚。
7. initialize 先检查创建目标：只允许已有空目标 Schema 或完整八表域；部分表缺失直接拒绝，不能自动补成看似健康。新空 Schema 的显式初始化是例外，在自己的初始化事务中逐步建表，完成后核验全部八表；不会创建 Schema 或改 search_path。QA 域要求已有 public.vector；public 的原显式 init-db 扩展初始化路径保留。本轮没有执行这些 DDL。

动态标识符校验后，元数据 SQL 仍用参数和 PostgreSQL format('%I.%I',...)，未拼接用户 Schema 输入。保护范围是项目既有八表 SQL，并非可对外暴露的任意 SQL 防火墙。

**QA 显式选择示例（仅调用方式，非本轮执行记录）：**

```python
database = Database(pg_dsn=approved_test_dsn, kb_schema=owned_test_schema)
# 由独立 QA 的授权入口创建／选择自己的 Schema，并配置其专用连接路径。
# 正式代码不会代为 SET search_path，也不会静默把目标改为 public。
```

Fix 的 `test_postgres_integration.py` 只调整夹具配置：先生成同一随机 Schema，再把它显式传给 Database；原生命周期断言全部保留。QA 自己的同名测试也需审阅并同步这项参数变更；旧全量 runner 的同名测试严格比对可能因此拒绝混测，不能删断言或关闭比对来解决。既有批准 ScopedLifecycleDatabase 构造器转发 kwargs，可继续叠加其 OID 守卫。

无需表迁移、数据移动或 ACTIVE 切换。真实 PostgreSQL 语法、类型、权限和跨域集成留待 QA；本轮仅 Mock 元数据及真实 SQLite 生命周期自检，没有用 Mock 宣称 PG 通过。

## 4. 预防性修复 SCA-002

- 根 compose.yaml 仅移除普通 app 的 MVP_TEST_PG_DSN 自动注入；保留业务 PG_DSN、数据服务、网络、卷及运行方式。
- 当前 compose.local.yaml 本来不注入测试 DSN，保持不变；local entrypoint 继续清除三种测试 DSN，并新增清除 OFFLINE_APPROVED_PG_DSN。不会全局清理用户机器配置。
- Windows `start_parsing_app.ps1` 拒绝 JSON 中的四种测试写入 DSN，并在普通启动进程中清除继承的这些变量。QA 专用脚本没有被更改，仍可显式构造批准环境。
- 实际 Windows PowerShell 5.1 调用暴露了 UTF-8 无 BOM 错误提示的解析兼容性问题。仅将该启动脚本的相关错误提示改为 ASCII，保留端口检查及后台启动方式；测试确认会在启动前返回 QA_TEST_DSN_NOT_ALLOWED。

没有改密钥、数据库角色权限、SOURCE_PG_DSN 值或持久卷，没有执行准备／启动／重建命令。正常 API 配置文件若混入测试 DSN，现在明确拒绝；需使用 QA 自己的专用入口，而非放宽普通 API 启动保护。

## 5. SCA-003 影响分析，未扩展业务

当前 `v_review_queue` 是 finding 级视图，定义为 findings INNER JOIN documents。前轮审计 18 条 requires_review 中 17 条缺 findings 而不在视图；本轮未重查计数，不能当成新的数据库测量。

检查 Fix 的 parsing_upload.html／mineru_api.py：当前上传页从按用户鉴权的任务及结果 API 展示 requires_review，并不查询 v_review_queue。只读检查独立 frontend 工作区的对应上传页／后端也未发现该视图查询；不把它作为已合并的当前业务源码。故尚无证据表明当前上传页面因该视图漏行而隐藏所处理任务的复核提示。

现有接口以 task_id 查询，没有跨历史文档、按用户分页列出所有待审 documents 的全局队列 API；关闭原页面或缺历史任务上下文时，工作人员发现所有待审材料的能力不足。不能据上传页有提示就声称完整审核闭环已经实现。

最小后续方案是经鉴权、按 source_location.owner_id 过滤，从 documents.requires_review 查询文档级待审清单；需要时 LEFT JOIN findings，而不是仅从 findings 起查。finding 级视图可保留原义，不必先改 DDL。是否增加该接口／页面属于明确业务需求，需单独确认。

如果要同步 findings/images 或写审核状态，需先确定唯一键、复核状态、幂等、版本和历史兼容；原 documents JSON 与已有 finding 不覆盖，不为填满视图伪造 finding，不自动批准。此轮未修改视图、sink 写入映射、历史记录或审核权限。

## 6. SCA-004 来源适配分析，未连接外部库

source_sql 现有正则只允许简单标识符，能阻止表名 SQL 注入，但不接受 schema.table；动态 main/detail JOIN 仍依赖来源连接的 search_path。load_pg_documents 独立连接、readonly=True、服务端游标，finally rollback/close，不写来源或目标表。

兼容方案：未来新增可选 source_schema 参数；省略时保留既有行为但在读前核验来源 OID，显式参数使用经验证／正确引用的 schema 与表名。不要把未经解析的 schema.table 字符串直接拼接，也不要用知识库的 public 默认来猜外部源域。

适配器必需字段：main 的 id/title；detail 的 auto_id、law_record_id、art_title、article_number、article_text。还需核对两者关联、条号／正文格式及排序可用性；读取前用 information_schema/pg_catalog 和只读小样本确认。当前目标库没有默认来源两表，外部端点、Schema、字段类型与内容约定仍 **NOT_VERIFIED**。

此轮未连接外部来源库、未修改 SOURCE_PG_DSN、未创建来源表、未把 public 知识库表当源表。需要连接外部库时须有该目标的明确授权；本次没有需要额外授权才能完成的既定修复动作。

## 7. 修改文件与实际自检

| 文件 | 修改 |
| --- | --- |
| qa_core/document_parsing/config.py | 复用当前输入硬限额 helper |
| qa_core/document_parsing/dual_engine.py | 旧候选与回退前复用 helper |
| qa_core/document_parsing/mineru_service.py | 最终缓存安全／有效性检查，阻断 sink |
| qa_core/storage/database.py | 目标 Schema 参数、逐语句关系／类型／所有权守卫、初始化与发布前检查 |
| compose.yaml | 删除普通 app 的测试 DSN 默认值 |
| deploy/local/entrypoint.py | 清除额外测试入口 DSN |
| scripts/start_parsing_app.ps1 | 拒绝测试配置、清除继承值、Windows 提示编码兼容 |
| tests/test_final_cache_recovery.py | 合法／无效缓存与当前限制回归 |
| tests/test_schema_identity.py | 10 个无真实连接的 Schema 边界方法 |
| tests/test_local_workbench_config.py | 既有 2 项加 3 项配置兼容方法 |
| tests/test_postgres_integration.py | 仅显式绑定 QA 夹具 Schema，未执行 PG 测试，未改断言 |

私有证据目录：Fix `local/schema-security-fix/`。

| 执行／日志 | 实际结果 |
| --- | --- |
| qrc-before.log：QA 原方法，修复前 | 1 方法、四子场景失败，sink 各 1，无真实数据库／云端 |
| qrc-after.log：同 QA 原方法 | 1 方法四子场景全部通过，sink/cloud 各 0；0.368 秒 |
| focused.log：初轮受影响自检 | 63 PASS；4.785 秒 |
| final-focused.log：新增所有权／更严格缓存检查后 | 64 方法中 63 PASS、1 FAIL；3.653 秒。失败确认为 Windows 启动脚本解析问题，原始日志保留 |
| launcher-after.log：提示兼容修复后 | 相关 4 方法 PASS；0.388 秒 |
| launcher-final.log：再补 Docker 继承环境隔离 | 配置 5 方法 PASS；0.353 秒，其中 4 项重叠、1 项新增 |

按增量结果覆盖 65 个不同的 Fix 自检方法；不把多次重叠运行相加，不宣称一次完整 65 项运行或独立 QA 签发。QA 原回归另列，原 276 项未重跑。测试中正常缓存和所有无效缓存的原文件／原结果字节不变，合法命中不解析、不外传；SQLite 构建、发布、回滚和检索使用临时文件，未对业务数据执行操作。

轻量复现命令（已有环境；日志放忽略目录）：

```powershell
# 原 QA 文件直接从独立 QA 工作区读取；业务 PYTHONPATH 明确绑定本次 Fix。
& $Python -B $QaQrcTest -v
& $Python -B -m unittest tests.test_final_cache_recovery tests.test_schema_identity `
  tests.test_release_safety tests.test_dual_engine_policy tests.test_mvp tests.test_local_workbench_config -v
```

## 8. 独立 QA 建议清单、未测范围与风险

1. 原 QRC-001 四子场景；新上传 S00019 SAFE_REJECT；合法最终缓存重试不重复 OCR／云调用／写库、不改变已保存 report 摘要；无效 JSON／SHA／页号／版本以及文件／PDF 页数／DOCX 体积限制。
2. PG 正常 public；完整自有 mvp_test_*；非法名称、非当前角色拥有的测试域；路径错误、缺一表回退到 public、同名临时关系、跨域 OID／FK、vector 类型遮蔽均 fail-closed。
3. 显式新空自有 Schema 初始化与完整已有域初始化；已有部分域必须在 DDL 前拒绝。初始化事务失败须回滚，不修改 public；禁止在业务库故意制造缺表或删除／替换表来测试。
4. 既有批准隔离环境中的构建、向量缓存、STAGED、发布、检索、回滚与事务失败恢复；SQLite 原有行为。检查每次业务 SQL 前都重新核验，连接路径变动后下一语句拒绝。
5. 解析 sink 仍固定 document_review，不受 kb_schema 参数影响；三种 DSN 变量分离，正常 Compose/API 启动没有测试写连接，独立 QA 显式入口仍可用。
6. Windows 启动有效配置的兼容性，以及拒绝／清理测试变量。本轮仅测试拒绝分支与 Mock 启动清理，没有实际启动进程。

**未执行**：真实 PostgreSQL 读写集成、业务 DDL／数据变更／ACTIVE 切换、外部来源查询、真实 OCR/BGE/云调用、全量 276 回归、镜像构建或服务切换、Windows 重启。现有 bf66 候选镜像及旧活动实例不含本轮修复，不能拿它们替代新源码验收。

剩余风险：逐语句检查增加元数据查询开销，未做吞吐承诺；不为有超管权限的并发恶意 DDL 提供绝对隔离保证，连接仍须由同一调用者管理。现有 app 用户权限未更改。PG 真环境语法／类型／权限和初始化边界必须由 QA 实测；SCA-003 的完整审核产品入口及 SCA-004 的外部源契约仍是待确认范围。

本轮完成已授权的代码、轻量自检和本地提交；不需要用户为这些步骤追加授权。任何后续生产迁移、权限调整、视图变更、外部库连接或实际部署都不在本次执行范围。交付通过本 Git 文件及完整 SHA，不声称已自动通知协调器或其他会话。
