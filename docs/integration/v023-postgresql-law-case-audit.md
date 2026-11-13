# v0.2.3 PostgreSQL 法规与处罚案例数据库专项检查报告

日期：2026-11-13，Asia/Shanghai。角色：Agent C。状态：**数据库增量结构已应用；BACKEND_API_PARTIAL，待独立 QA 与业务数据准备**。不是两个完整业务库上线验收结论。

## A. 数据库身份与原结构

实际目标为本地共享容器 market-regulation-db-1，数据库 market_regulation，PostgreSQL 16.15。正式应用私密 runtime 的解析连接实际也指向同一数据库，账号 market_app，端口 5432；连接身份通过真实连接查询核对，没有记录 DSN 或密码。用户本轮明确允许按正式方案直接修改该库；不把本地结构升级等同于外部生产部署。

原业务 Schema 为 document_review 与 public，共 15 张表。先执行只读事务，通过 information_schema、pg_catalog 获取真实字段、约束、索引，不以代码模型代替目录核验。原目录共 176 个字段、28 个约束、23 个索引；逐字段类型、NULL、主外键、唯一约束、索引定义详见 [原结构目录](v023-pg-library-original-catalog.md)。

| 既有职责 | 实际表或位置 |
|---|---|
| 解析结果与原始正文 | document_review.documents；parse_id 主键，document_id 为源内容标识，source_location JSON 保存 owner/原件映射 |
| 页面与版面 | document_review.pages、blocks、tables、cells、images、findings |
| 文档版本 | public.mr_document_versions；doc_id、doc_version_id、source_hash、metadata |
| 切分与版本成员 | public.mr_chunks、mr_kb_documents；外键关联 doc_version_id |
| 知识库与发布 | public.mr_kb_versions、mr_active、mr_active_chunk_map、mr_release_history |
| 兼容检索投影 | public.law_chunks；不是完整法规主表 |
| 上传与任务 | 原件元数据/字节位于现有受控文件存储；解析任务仍在既有 SQLite。PG 没有独立上传/任务主表，本轮未迁移任务 |

任务书“SQLite 仅用于隔离 QA”与现行任务存储职责不同。本轮不将 PG 业务迁入 SQLite，也不擅自迁移现有 SQLite 解析任务；若后续改变任务存储需单独设计。

## B. 真实数据及满足程度

升级前后逐表数量和内容摘要均一致：原有 15 张表未增删改数据。

| 指标 | 真实数量/结果 |
|---|---|
| 解析记录 | 48；是解析结果数量，不等同于 48 个独立已核验法规/案例 |
| 有原件关联 / owner | 各 47，完整率各 97.92%；各缺 1 条，不猜测补齐 |
| raw_text 为空 | 5 / 48，10.42%；original_result 空对象 0 |
| 明确 original_result.document_type=law/case | 0；其余 48 为类型未明确，不能直接认定普通文档或法规 |
| 相同 document_id 出现多条解析的分组 | 9；可能是合法重复解析，不作为重复主键或坏数据删除 |
| 文档版本 / KB 文档成员 | 0 / 0 |
| law/case/普通版本 | 均无版本记录；不能据此断言原始 48 条均无相关正文 |
| 版本 Chunk / 兼容 law_chunks | 0 / 0；法规和案例 Chunk 均为 0 |
| 有章节/条款的正式法规 | 0；不以普通段序号冒充条款 |
| 案件名称/违法事实/处罚依据/处罚结果结构化案例 | 升级前缺少正式结构，升级后结构记录 0 |
| 当前 ACTIVE / KB 版本数量 | 无 / 0；ACTIVE 成员和映射均 0 |
| 悬空 Chunk / 悬空版本成员 | 0 / 0，但分母为 0，不记为 100% 完整 |

法规文号、类别、机关、发布日期、实施/废止日期及可靠效力状态原先仅可能放入自由 JSON，未形成完整业务约束。正式版本为空，相关空值率/重复率为不适用，不能写成“全完整”。未输出正文、当事人、源文件名或原路径抽样。

| 检查项目 | 升级后实际情况 | 结论 |
|---|---|---|
| 法规基本信息 | 新结构可保存所需字段；无已确认业务记录 | PARTIAL |
| 法规版本管理 | 复用 doc_id/doc_version_id 与 KB 成员；无版本数据 | PARTIAL |
| 法规章节管理 | 新增章节及版本约束；无业务数据 | PARTIAL |
| 法规条款管理 | 新增真实条款编号/顺序/章节关系；无业务数据 | PARTIAL |
| 条款正文保存 | 引用原始解析正文的字符范围；不复制整篇正文；历史范围未确认 | PARTIAL |
| 法规原文溯源 | parse_id/source_file_id/source_hash 一致性约束；历史 1 条缺映射 | PARTIAL |
| 案例基本信息 | 复用目录并补充案例字段，字段允许未知为空 | PARTIAL |
| 案例违法事实 | 有可空字段及字段来源，未自动抽取回填 | PARTIAL |
| 案例处罚依据 | 新增多对多版本/条款引用，默认 pending | PARTIAL |
| 案例处罚结果 | 数值罚款及决定字段可存储，暂无已核验数据 | PARTIAL |
| 案例原文溯源 | 引用原解析正文；原文不等同人工核验字段 | PARTIAL |
| 案例与法规关联 | 双端版本、条款与类型外键已建立，真实关系 0 | PARTIAL |
| ACTIVE 版本隔离 | PG 隔离测试验证过滤正确；当前真实库无 ACTIVE，接口合法空态 | PARTIAL |

没有以建表成功宣称业务数据 PASS。上述“结构可用”已实际测试，所需真实数据仍不齐备。

## C. 增量升级与恢复

执行脚本：[up](../../scripts/sql/20261113_business_library_up.sql)、[down](../../scripts/sql/20261113_business_library_down.sql)。已获用户明确修改授权，在隔离测试及备份恢复成功后应用于 market_regulation。

新增独立 business_library Schema，6 张表：records、chapters、articles、article_chunks、case_profiles、case_law_references；17 个索引、11 个外键（包括主键/唯一索引）。原 public/document_review 表不新增字段，不改变主键、版本与 ACTIVE，不创建第二套全文表。

records 通过既有 doc_version_id 和 parse_id 复用版本与正文；触发器验证 owner_id、source_file_id 和 source_hash。articles 的 raw_start/raw_end 为零基、左闭右开字符范围，不是字节偏移；必须经可靠定位确定，不能自动套用 Chunk 顺序。范围超正文长度拒绝，Chunk 链接必须属于同一文档版本。全文经既有 raw_text 读取，原件字节未改。

case_profiles.penalty_amount 为 numeric(20,2)，可 NULL；其他未确定字段允许 NULL。field_sources 保存字段证据，不会自动变为人工核验。目录/引用 verification_status 默认为 pending，verified 必须有实际 verified_by、verified_at；自动提取不能写作已人工核验。关系支持一个案例引用多个法规版本/条款，不产生法律适用结论。

没有执行历史回填，没有把 48 条解析结果自动认定为法律法规或处罚案例；新增 records 数量为 0。没有新建数据库引擎，没有迁移 MySQL 审核事件，没有修改原 OCR、正式文件、授权预算或 Token。

升级前 pg_dump 自定义格式备份已保存于 Git 忽略目录，67,334,481 字节；SHA-256 为 ee4ed90aa035ca0bb16b06ba924281721f9d142f4d6f7a47b94703ded0ebcfa6。在 network=none 的全新临时 PG 容器完成真实 pg_restore --exit-on-error，恢复后 48 条解析、ACTIVE=0。备份含业务数据，只在本机保留，不入 Git。

回退：当前新表为空，down 在事务内按依赖顺序移除本次新增对象；先检查 records 为空，有记录立即拒绝，不 CASCADE、不删除核验数据。隔离 PG 已验证空库 down/up 往返及有数据拒绝回退。正式目标未实际执行 down；有业务数据后应优先前向修复，备份恢复只能在停写协调及另行批准后使用，不能直接覆盖现有库。

权限发现：market_app 实际具有 superuser/createdb/createrole。这是当前账号的真实情况，不符合长期最小权限要求。本轮未改变运行账号，避免影响既有 OCR/知识库链路。[只读授权模板](../../scripts/sql/business_library_reader_grants.sql) 提供独立 NOLOGIN 权限角色；尚未在目标执行，需为完整运行所需权限另行评估独立登录账号后安全替换，不能直接撤销共享账号权限。

## D. 后端与前端契约

新代码复用既有 HTTPBearer、Principal 与 ReviewReader 的只读重复读事务，所有查询真实 PG，不读 MySQL 业务正文，不使用 SQLite 证明 PG 正确性。管理员全局，普通用户本人，审核人员仅可读授权 owner；范围外统一 404。

| 方法与路径 | 用途 |
|---|---|
| GET /api/library/laws | 法规列表、名称 query、分页、kb_version |
| GET /api/library/laws/{doc_version_id} | 版本详情、原解析正文、原件授权入口 |
| GET /api/library/laws/{doc_version_id}/chapters | 真实章节及顺序分页 |
| GET /api/library/laws/{doc_version_id}/articles | 真实条款列表、章节关联和顺序分页 |
| GET /api/library/laws/{doc_version_id}/articles/{article_id} | 条款正文范围、页码、Chunk 关联及原件入口 |
| GET /api/library/cases | 案例列表、名称 query、违法行为 violation、分页、kb_version |
| GET /api/library/cases/{doc_version_id} | 原解析正文和可空结构化字段，罚款精确十进制字符串 |
| GET /api/library/cases/{doc_version_id}/references | 处罚依据引用、法规版本/条款、来源方式及核验状态；目标同样执行 owner/版本过滤 |

详情含 document_id（稳定业务 doc_id）、doc_version_id、parse_id、source_file_id、kb_version、原件名称及 source_url。source_url 指向既有受保护 /source，仍需 Bearer；原件存在性及文件权限由既有入口核验，不承诺缺失历史文件一定可下载。text_status 固定 ocr_not_manually_verified，表示原始 OCR 文本，不把整篇 OCR 自动标成人工确认。原始字节与人工结构字段分开。

仅允许当前或历史已发布版本，须 ACTIVE/ARCHIVED 且有发布历史；默认无 ACTIVE 时列表 200 status=unpublished/list=[]/total=0，详情 404。已发布版本存在但新 Schema 未装时 503 library_schema_not_installed，不假装空数据。认证 401、范围外/对象不存在 404、非法分页等 422、连接/存储失败 503，错误不返回 SQL、DSN 或堆栈。

契约升级为 frontend-api-v0.2.3-draft-5，54 路径；[离线快照](frontend-openapi-v023-draft5.json) 从当前源码实际 FastAPI 对象导出，保留 draft-4 冻结快照。能力接口版本同步更新。没有创建业务写入、自动抽取核验或发布捷径；写入仍应走既有审批与发布流程。

## E. 测试与运行身份

最终去重成绩：**61 个方法通过，0 失败、0 跳过；另有 8 子用例**。其中本专项真实 PG 类 20 方法，覆盖新增查询、多版本、章节/条款/Chunk/来源、数值金额、pending 引用、类型/owner/ACTIVE 隔离、外键唯一约束、17 个索引、分页、原 PG 关键字检索、回退与只读权限；其余为原前端查询与原功能回归。使用合成正文/身份和全新空 qa_round01，未使用真实用户凭证。

运行基座使用旧不可变镜像 sha256:04d0751efdd07af419d516c9ed4bdb7c14c1bdf38bc660a1b188e37a1951ed4e，但本轮测试显式只读挂载新源码；这是源码隔离测试，不是旧镜像已包含新功能。当前未构建新的业务候选镜像，不能把旧 OCI f21e9861… 当成本轮源码。原开发分支业务源码完整 SHA 为 8fbe2eb8bd81c6b5bd0ff6b24110892ac63f2bed；backend-api 工作区对应提交为 b220298a8a98a424607ede9975d3575c8fc17c35，后续报告提交不改变业务代码。

8180 仍为 market-regulation-app-1，容器 b23198928dda0e75ff7ad40d3ce8170da825cb81922526a1db65e8b5815621c1；镜像 sha256:e2a94f67ffacef9e780e06bc1484cb5e7dde4b287fa5ef340a666f5e573e52a3，标签 market-regulation-workbench:sha-30c4663ceb93cbba302b322f1ecee0d06d80bfb4，源码/OCI 30c4663ceb93cbba302b322f1ecee0d06d80bfb4。本轮核对 StartedAt=2026-11-13T00:24:00.319144677Z、healthy；本轮没有重启或替换它，仍是 22 路径旧契约，未包含新 API。

原始证据仅在 backend-api 工作区 ignored local/pg-library-audit/，包括目录聚合、before/after-data-digests、backup-manifest、备份、迁移日志和隔离 pytest 输出。早期未去除导入测试类重复发现的 72/73 不作最终不同方法数；本报告只计最终 61。

## F. 结论及下一步

1. 法规库：原结构不完整；现在基础结构可用，但真实分类、法规版本、章节条款和可靠效力来源仍缺，不满足完整业务数据要求。
2. 案例库：原结构缺失；现在可存原文引用、结构字段与法规引用，真实已核验案例仍为 0，不满足完整业务数据要求。
3. 新增 6 张关联表已执行；复用原表，不重复建设文档/版本/全文主表。
4. 原表未增加字段；缺少的业务字段放在新增结构，允许 NULL。
5. 新增 article_chunks 明确条款与 Chunk 多对多，同版本校验；原 Chunk 主表和切分规则不改。
6. 前端可按 draft-5 开发两个只读入口和合法空态；当前 8180 尚无新接口，不能宣称已正式可连接或整版上线。
7. 数据准备阻塞项：明确 law/case 分类、缺失 owner/原件映射人工确认、可信法规事实、原文条款定位、案例字段及引用核验、审核门禁和正式候选发布。

交 QA 重新独立执行本专项真实 PG 用例，验证已升级目标目录只读状态，并对新镜像另行核对源码/OCI。后续仍须冻结候选、隔离测试、独立 QA 与用户部署授权后才能切换 8180；本轮不 Push、不 Merge、不打 Tag。

QA 最小复核任务：在全新空 qa_round01 执行 test_business_library_pg（LIBRARY_ISOLATED_PG=1，连接仅从本机私密测试配置提供），不得指向已升级目标库初始化夹具；复测原 frontend_api/mvp；校验 draft-5 为 54 路径；验证两类列表在无 ACTIVE 时返回合法空状态；确认上线前独立账号权限、实际原件下载与前端两页交互。原件下载实物闭环、新页面浏览器验收及新镜像验证本轮未执行，不能从源码测试推导 PASS。
