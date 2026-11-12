# v0.2.3 draft-4 后端接入包

日期：2026-11-12，Asia/Shanghai。状态：**BACKEND_API_PARTIAL，供前端适配，待新版本独立 QA**。本轮没有修改前端源码、正式数据库、正式 runtime 或 8180。

## 唯一候选与正式运行身份

| 身份 | 本轮候选 | 目前正式 8180 |
|---|---|---|
| 后端源码完整 SHA / OCI revision | f21e9861c2fddca9b0643cf4619e485332859f5a | 30c4663ceb93cbba302b322f1ecee0d06d80bfb4 |
| 镜像 ID | sha256:04d0751efdd07af419d516c9ed4bdb7c14c1bdf38bc660a1b188e37a1951ed4e | sha256:e2a94f67ffacef9e780e06bc1484cb5e7dde4b287fa5ef340a666f5e573e52a3 |
| 镜像标签 | market-regulation-workbench:candidate-v023-api-f21e9861-f7bc2ec | market-regulation-workbench:sha-30c4663ceb93cbba302b322f1ecee0d06d80bfb4 |
| 当前运行容器 | 只有短期测试容器，无长期候选服务 | market-regulation-app-1 |
| HTTP 身份 | frontend-api-v0.2.3-draft-4，46 路径 | 0.2.2-api-candidate，22 路径 |
| 前端 revision | 7bc2ec3e6dc342430570734d5339b0f9ed0db038 | 63bbcc07a6b6d12a6be56fa7b0e81731c3917a45 |

正式容器完整 ID 为 b23198928dda0e75ff7ad40d3ce8170da825cb81922526a1db65e8b5815621c1，启动时间保持 2026-11-12T00:54:43.04620371Z，复核 healthy。本地源码变化不会自动出现在 8180；不要向旧入口调用新写接口做试验。

候选由冻结 Git 对象构建，复用既有基础镜像，不安装新运行依赖、不覆盖旧标签。前端是当前冻结 7bc2ec 的全新构建，保留空态返回、提示折叠和审核布局更新，类型检查与 Vite 构建成功，仍有既有大 chunk 提示。

原软删除专项 QA_PASS：QA 提交 161b73826fabe1f78b819cced1507f895d078fb4，仅覆盖 cd3fd89441cf385cf631f0adc7ba096a9743900e / 镜像 80bedbd… 候选。本轮增加账号和全权限管理员并改变授权口径，不能继承该 PASS 为整版结论。

## 契约与认证

离线快照：[frontend-openapi-v023-draft4.json](frontend-openapi-v023-draft4.json)，从最终镜像实际 app.openapi() 导出；运行期 GET /api/openapi.json 需认证。保留 draft1–3 和 v0.2.2 冻结快照。info.version=0.2.3-dev，x-contract-version=frontend-api-v0.2.3-draft-4。

角色规范见 [账号与角色设计](v023-account-role-design.md)：ADMIN 全部业务权限；USER 本人数据；REVIEWER 明确审核范围。权限判断以服务端 Principal、实际方法、对象详情和门禁为准，不能拿 owner 当操作者，也不能从用户名推断角色。

除登录外，接口使用 Authorization: Bearer 会话凭证。失败统一为 `{"error":{"code":"机器错误码"}}`，不回显密码、Token、DSN、堆栈或机器路径。401 未认证/会话失效；403 无操作权限；404 对象不存在或范围外；409 证据链、版本/幂等/操作冲突；422 参数无效；429 限流/并发限制；503 配置或存储不可用。

## 登录与账号管理

| 方法与路径 | 请求 | 成功结果 |
|---|---|---|
| POST /api/auth/login | username、password；匿名可调用 | 200 access_token、token_type、expires_in、principal；Cache-Control:no-store |
| POST /api/auth/logout | Bearer，无正文 | 200 revoked:true；仅新会话支持服务端撤销 |
| GET /api/auth/me | Bearer | principal_id、owner_id、roles、review_owner_scopes、credential_status、permissions、data_scope |
| GET /api/auth/roles | Bearer | 三类角色定义、all_permissions 管理员口径及安全门禁 |
| GET /api/admin/accounts | ADMIN；page、page_size | 真实账号分页，不含密码或哈希 |
| POST /api/admin/accounts | ADMIN；username、password、roles；可选 owner_id、review_owner_scopes | 201 服务端生成的账号身份和业务 owner |
| PATCH /api/admin/accounts/{principal_id} | ADMIN；可选 roles、review_owner_scopes、credential_status、password | 修改后的公开账号字段；修改已有 owner/身份/用户名不开放 |
| GET /api/admin/account-events | ADMIN；分页 | 账号变更、操作者、目标、before/after；无密码及哈希 |

用户名为 3–64 位字母、数字及 `_.@-`，首位字母或数字，大小写不敏感；密码设置/重置 12–256 字符。没有公开注册，也没有默认账号密码。用户名冲突、保留身份/owner 冲突、最后一个有效管理员保护返回 409。

前端登录流程：提交账号密码 → 只保存返回的短期 Bearer → 重新 GET /api/auth/me → GET /api/openapi.json 与能力接口。密码不存浏览器、不入日志；Bearer 沿用内存/sessionStorage。401 显示重新登录，403 显示权限不足并刷新身份，不能直接解释成密码错误。

ADMIN 只需 ADMIN 角色，不必额外塞入 REVIEWER；旧 document_delete_owner_scopes 字段仅兼容保留，不能拿其空列表否定管理员权限。审核员空 review_owner_scopes 仍无审核写权，未配置通配全局授权。

## 文档、任务与监控

| 方法与路径 | 本轮新增或增强 |
|---|---|
| GET /api/system/capabilities | 当前身份权限、真实实现能力、登录/写入配置是否指定、支持参数；configured 不等于数据库健康 |
| GET /api/documents、任务查询 | ADMIN 默认全局；公开 owner_id 表示实际数据归属，历史未知不补造 |
| 原有 owner 范围接口的 owner_id 查询参数 | 已在 OpenAPI 明确声明；仅 ADMIN 可显式指定，其他角色传入 403。上传/创建任务默认个人 owner，无个人 owner 时须指定目标 |
| GET /api/parse/tasks/{task_id}/logs | page/page_size/date_from/date_to；持久化状态变化、文件状态及错误码，不包含原件名称/路径 |
| 原有任务详情/列表的 current_step、workload | 文件总数、终止/成功/失败数及文件完成比例；不是 OCR 内部阶段百分比 |
| GET /api/system/api-logs | 分页、带时区闭区间、level=info/warning/error；USER/REVIEWER 本人请求，ADMIN 全部 |
| GET /api/system/error-logs | 同上，只包含 HTTP 4xx/5xx，不提供原始堆栈或请求正文 |
| 原有审核及审计接口 | ADMIN 全部 owner；审核员仍按授权范围；记录实际 operator_id 与目标 owner_id |

阶段日志只在真实保存状态变化时产生。历史未记录任务返回 available=false、reason=historical_events_not_recorded；不回填历史阶段。单任务保留最近 2000 条并标记 truncated。API 日志只查询最近 10000 条窗口，截断会标记，不把窗口 total 当全部历史总数。

未确认身份的请求记录 principal_id=null、actor_confirmed=false，仅 ADMIN 全局日志可见；不把猜测账号或 owner 写作实际人员。API 日志不记录 Authorization、查询串、正文、响应体或任意用户路径，只保留路由模板、状态、耗时。

原 /api/system/resources 仍只代表 API 进程资源，不是宿主机/GPU 全量监控；模型健康仍为本地文件/配置核查，不做真实云探活。

DELETE /api/documents/{file_id}：ADMIN 可对任意 owner 的未形成证据链上传软删除，其他角色 403。任何解析历史、活动任务、PG/知识库引用均 409；原始字节保留、元数据隔离。列表不再返回，详情/历史/原件 GET/HEAD 404，重复删除 404。历史 owner 无法可靠确认时 409，不能改 owner 绕过审计。

## 入库、版本与检索

| 方法与路径 | 请求及行为 |
|---|---|
| POST /api/ingestion/precheck | kb_version、documents、可选 full_snapshot；只读，逐项 eligible/error_code/quality_passed，检查失败可以 200 eligible=false；认证、越界、存储错误仍非 2xx |
| POST /api/ingestion/batches | ADMIN，同正文；必需 Idempotency-Key；同步构建，成功 201 STAGED，不自动发布 |
| GET /api/ingestion/batches | 分页；ADMIN 全部操作，其他身份仅本人历史；无假批次 |
| GET /api/ingestion/batches/{batch_id} | 操作回执、阶段摘要、最后持久状态、execution_live、outcome_unconfirmed |
| GET /api/ingestion/version-check | kb_version；只读返回状态、当前 ACTIVE、base 是否匹配及技术可发布/回滚条件 |
| POST /api/ingestion/publish | ADMIN；kb_version、必填 expected_active_version（初次为 null）；Idempotency-Key |
| POST /api/ingestion/rollback | ADMIN；相同字段与幂等要求；目标须 ARCHIVED |
| POST /api/knowledge/search | 原 query/mode/limit，新增 kb_version、issuing_authority、effective_status |

documents 每项必须包含真实 parse_id、明确确认的 law_name、law_id、expected_review_version（至少 1），最多 20 项，不接收 owner_id/operator_id/路径。禁止把上传 ID、任务 ID、文档 hash 猜作 parse_id。

构建复用现有 to_legal_document、preview_documents、ingest_documents 和本地 BGE 工厂，不重写 OCR/RAG。需实际上传身份及字节哈希一致、MySQL 当前已批准版本和源结果摘要一致、最新批准操作者有效、质量门禁通过。候选数据只写知识库候选，原 OCR 与审核事件不改动。

当前正式构建适配只支持法规；含表格、部分失败、不能完整结构化的来源拒绝。人工修订正文的正式导出协议尚未确认，有 current_revision 时 409 reviewed_revision_export_required，不能把旧 OCR 偷偷作为已修订正文入库。处罚案例保留既有只读预览；前端必须读取能力字段，不提前开放相应正式入库。

发布/回滚复用原治理服务，在 PG 事务锁内原子比较 expected_active_version；投影、ACTIVE、发布历史共同提交。发布前重新核验来源和审核绑定，并持有 MySQL 审核头共享锁到发布完成，撤回审核不能并发绕过门禁。缺少可验证审核来源绑定的历史 CLI 版本返回 409，不能强行接管。

知识库写入必须有独立私密 KNOWLEDGE_WRITE_PG_DSN，未配置 503；ADMIN 有业务权限不代表存储已经启用。version-check 的 eligible 只是技术条件，publish_authorized=false 表示该只读请求未授予发布动作，不否定 ADMIN 角色本身。

同键同请求复用回执，异请求同键 409。长构建超时不能断言未写入；查询批次记录判断。RUNNING 只表示最后记录，重启后 execution_live=false/outcome_unconfirmed=true，不自动重跑；FAILED 的原键重试 409，失败写入可能部分保留于 FAILED 候选，write_performed=null，不能当 0 写入。阶段未知计数为 null，不伪造百分比。

发布回执的 event_id 与 PG 发布历史关联；若 PG 已提交但回执存储/网络失败，同键重试可核对该事件恢复回执。成功后仍重新查询当前 ACTIVE，不能把历史动作回执当作当前指针保证。

检索只允许当前/历史已发布版本（ACTIVE/ARCHIVED 且有发布记录），未发布候选不开放。机关/效力按已有 chunk/文档元数据精确过滤并在排序限额前生效，不推断法律事实。缺少来源字段无匹配，不生成假结果；默认无 ACTIVE 仍合法返回 unpublished/空列表。检索响应含真实版本、来源及 applied_filters。

## 本轮验证与前端待办

最终镜像：132 项 pytest 回归 + 1 项真实隔离 PG/MySQL 全链路 + 6 项真实 PG 删除引用测试，共 **139 个不同方法通过，0 跳过**，另有 25 subtests，不累加重复运行。83 个源码/入口文件按 Git 文本 LF 规范逐一比对，业务均从镜像导入。

真实 HTTP 验证纯密码模式、ADMIN 跨 owner 删除、USER 403、登出失效和运行期契约；HTTP 正向删除使用明确无引用夹具，真实引用另由 PG 六项验证。全链路使用测试 1024 维向量，不代表真实 BGE 推理质量或云 OCR 已验收。

同一最终镜像及固化前端另完成 7 个真实浏览器删除场景：方法门控存在/缺失、403/409/503 保留行、重复 404 不计成功、200 后真实刷新消失。密码表单未包含在这 7 项中。所有本轮临时测试容器均已退出，正式容器身份和启动时间未变。

前端仍需完成：

1. 账号密码登录表单、管理员账号/角色/范围/停用/重置密码页面，以及审计列表。
2. ADMIN 全权限适配：去掉“必须含 REVIEWER 才能审核”的旧前端限制；依据权限、实际方法与详情门禁收紧，不从 owner 推断人员。
3. 入库批次、预检、发布/回滚、日志及新筛选界面接入；原页面有硬编码禁用处，不是加后端路径就全部自动可点。
4. 删除门控已有方法级支持；仍须权限提示并在成功后真实刷新，403/409/503 不本地移除行。
5. 修正已核对的前端问题：审核表格应读取 pages[].tables；列表重试不能把终止态一律当不可恢复（与抽屉规则需统一）；首页修改 days 后应刷新或保留已加载窗口标签。
6. 用真实运行契约替换旧“22 路径/删除未实现/固定版本 SHA”说明；管理员统计注明全局范围。现有大 bundle 告警另作前端优化。

本轮没有实现宿主机/GPU 全量监控、没有凭空补出历史阶段日志或缺少明确口径的扩展成功率/趋势，不把这些标成已完成。

真实浏览器账号登录表单与账号管理页面尚不存在于冻结前端，因此未测试；审核四动作、多审核员、版本冲突和撤销的全新 UI 联合验证仍交 WorkBuddy/QA。后端单测/HTTP 不代替 UI PASS。

## 提交及交接

原分支 codex/backend-improvements-v023，保留 main=076d4f968aa2c71133c551007b5d082da96a5929。模块完整 SHA：

- 账号/管理员：2dae2735c50e6d5e5133b1ddd488960e937527ac。
- Bearer 兼容：5c7a93bb76bc5a837ced01778ffbb21777c87551。
- 日志：b51dbdee1dcf177089d0f1fedd84b79533bc05a2。
- 入库/检索：a448e51d3cb3bd8ac7aac22952663da6284f87e4。
- 日志身份/错误契约：7c667465f950c512fbb9b0a36386daa93da66817。
- 最终参数声明与冻结：f21e9861c2fddca9b0643cf4619e485332859f5a。

最终文档/测试交接提交另在交付消息记录，不自嵌尚不存在的提交 SHA。后续文档/验证文件不改变镜像中的冻结业务源码。

原始证据在 backend-api 工作区 ignored 的 local/frontend-api-v023/final/：full.log、workflow.log、delete-pg.log、http.log、source-hashes.json、browser/browser.json、browser-identity.txt。早期工具装配/归档差异日志保留，不计为产品失败或最终成绩。

下一步按 [独立 QA 任务](v023-draft4-qa-handoff.md) 验证同一镜像；前端对接后记录新的前端完整 SHA。未经新版本 QA 和用户最终部署授权，不注入正式账号/写入凭据、不切换 8180、不 Push/Merge/Tag。
