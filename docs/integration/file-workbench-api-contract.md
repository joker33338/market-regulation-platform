# 文件工作台接口契约（开发草稿）

日期：2026-11-17，Asia/Shanghai。分支：codex/file-workbench-ux。
契约：frontend-api-v0.2.3-workbench-draft-1；应用版本：0.2.3-workbench-dev。
本轮未替换正式8180；旧版冻结契约及正式v0.2.3标签保持原样。

## 使用流程

上传原件 → 保存批次、自动提交现有解析队列 → 确认类别、标题与拆分范围 → 人工审核 → 后台预检、清洗、切分及构建候选 → 核对实际发布清单 → 明确确认发布 → 法规库或处罚案例库查阅。

构建使用已保存、审核绑定的解析结果，不再次调用OCR/MinerU。默认不开启云端调用。没有ACTIVE时保留合法空态，不将审核通过或STAGED当作已发布。

## 新增接口方法

以下26个方法均在隔离HTTP导出的OpenAPI中声明。完整请求/响应、字段长度、必填项和枚举见[离线快照](frontend-openapi-workbench-draft-1.json)，运行可用性以当次认证后的GET /api/openapi.json为准。快照共77条路径；不将该数字硬编码为前端能力门禁。

| 方法 | 路径 |
|---|---|
| GET | `/api/review/{parse_id}/reviewed-text` |
| GET | `/api/workbench/documents/{file_id}/suggestions` |
| POST | `/api/workbench/documents/{file_id}/prepare` |
| GET | `/api/workbench/jobs` |
| GET | `/api/workbench/jobs/{job_id}` |
| GET | `/api/workbench/jobs/{job_id}/check` |
| POST | `/api/workbench/jobs/{job_id}/publish` |
| POST | `/api/workbench/review-batches` |
| GET | `/api/workbench/review-batches/{batch_id}` |
| GET | `/api/workbench/review-batches/{batch_id}/items` |
| POST | `/api/workbench/review-batches/{batch_id}/items` |
| POST | `/api/workbench/releases` |
| POST | `/api/workbench/releases/{release_id}/items` |
| GET | `/api/workbench/releases/{release_id}/items` |
| POST | `/api/workbench/releases/{release_id}/prepare` |
| GET | `/api/workbench/releases/{release_id}/check` |
| POST | `/api/workbench/releases/{release_id}/publish` |
| POST | `/api/workbench/selections` |
| GET | `/api/workbench/selections/{selection_id}/files` |
| GET | `/api/workbench/review-queue` |
| GET | `/api/workbench/documents` |
| POST | `/api/workbench/batches` |
| GET | `/api/workbench/batches` |
| GET | `/api/workbench/batches/{batch_id}` |
| POST | `/api/workbench/batches/{batch_id}/files` |
| POST | `/api/workbench/batches/{batch_id}/retry` |

## 身份、范围及错误

沿用HTTPBearer和现有账号密码会话。principal_id为操作者，owner_id为原始业务归属；服务端解析身份，不接受客户端伪造。USER按本人owner读取并确认资料；REVIEWER只在已授权owner范围内读取和审核；ADMIN拥有全部业务权限。准备资料不会给普通用户授予后台入库或发布权限，普通用户提交的记录等待管理员确认接手。后台审核和构建重新读取角色/凭证状态，不缓存已撤销权限。

审核批次和全选快照归发起人所有；发布清单限创建该清单的管理员操作。未知历史owner不默认归当前管理员，无法核实返回503。跨范围对象不可见，返回404；已认证但不具备动作权限返回403。

错误包络：{"error":{"code":"机器可读错误码"}}。401未认证/凭证失效；403无动作权限；404对象不存在或不可见；409来源、审核版本、幂等或ACTIVE冲突/完整性门禁；422非法参数；429排队/模型并发受限；503存储、台账或必要配置不可用。响应与日志不包含凭据、DSN或机器文件路径。

## 批次、选择与真实进度

- 整批文件数量不设固定上限；单次追加最多100项，客户端自动分页；原任务单次20份和单文件100MB限制保持。后台复用SQLite任务，浏览器不必手拆任务。
- 上传面板最多两个同时上传；已传完的字节与已提交任务分别记账。未传完的本地文件不会在关闭浏览器后继续上传。
- 批次创建、资料准备、审核批次、发布清单和发布请求均使用Idempotency-Key；浏览器生成并在结果不明确时复用。相同键不同内容409。
- 上传批次状态queued/dispatching/submitted/parsed/failed/duplicate；parsed以SQLite单文件结果为准。仅失败项重试，成功项不重新排队；队列满返回等待状态。后台构建按到期时间公平领取，避免待审核文件阻塞后续文件。
- SHA去重限定同owner、本批次；跨owner不借用原件。文件名不同但同内容在同批标明重复。未声称对全系统跨批次自动去重。
- POST selections固定当时匹配的file_id、SHA、parse_id和审核版本；有效期1小时，后续新增文件不被纳入。分页读取时重新检查当前权限与SHA。筛选改变须重新选择。
- 工作台按真实来源聚合上传、任务、解析、审核和ACTIVE成员关系。处理状态包括待开始解析、处理中、待审核、待确认资料、待构建、待发布、已发布、需处理、状态待核实；台账不可用不变成已审核，多篇文件部分发布不变成整份发布。
- 支持文件名/资料标题/文号/案号关键词、law/case/unconfirmed类别、文件格式、批次、上传时间与阶段筛选；后端全文匹配只返回匹配信号，不在列表泄露正文。待审核队列包括正常OCR但未人工审核的文件，不仅依赖旧复核视图。

## 确认资料与汇编范围

POST documents/{file_id}/prepare必须包含title、document_type、expected_sha256，可绑定source_parse_id。source_range为start/end（Unicode字符，左闭右开）及expected_text_sha256；whole_file_confirmed表示用户明确选择整份资料。

标题识别和law/case归类仅是建议；无法可靠分类或存在多篇资料时停下等待确认。范围建议包含页码和全文指纹；正文分段读取默认20000字符、最多50000字符，界面支持翻段和分别设置起点/终点。每篇保留原页码、块标识、坐标及原文字位置。越界、指纹变化、不可映射的版面及未承接表格继续阻断，不截去异常内容后发布。多个范围重叠由前端要求调整，服务端同样拒绝与已确认候选的重叠范围。已发布来源的范围/类别变更返回409 published_source_change_requires_replacement，不能把旧整篇与新拆分篇同时无提示加入ACTIVE；专门的已发布资料范围更正流程尚不在本轮实现。

候选任务queued/awaiting_parse/awaiting_review/awaiting_admin/building/awaiting_publish/published/needs_attention/superseded。失败原因保留，用户在文件上下文重新确认可生成新候选；已经失败的构建操作不以同一键伪装重新完成。superseded不删除历史候选或解析结果。

## 整页正文修订协议

用户已确认采用page_body_v1：save-revision发送page、该页完整content和revision_scope=page_body_v1，并继续携带base_result_id及expected_version。

只在深拷贝中替换该页正文块，保留原始OCR、原文件、表格/图片/页眉页脚及追加式审核事件。每页使用最新修订，绑定revision_id、operator_id及审核版本；保存后必须重新审核。GET reviewed-text返回当前审核副本、是否已审核和原件未变标识。旧事件未声明整页语义、缺少实际操作者或版本不符时409，必须人工重新确认，不推断成整页替换。

人工批准正文不自动确认法律效力、机关等业务事实。结构化条款仍标待核验；缺乏正式表格修订承接的内容继续受完整性门禁约束。

## 发布与数据保护

发布清单固定选中的job_id及对应来源/审核版本；全部待发布也在服务端固定快照。逐页核对标题与目标库，发布时复核现有审批、原件、最新解析、候选身份、模型/规则签名和expected_active_version。并入同一增量候选时复用已经生成的向量，保留未被选中更新的ACTIVE资料，不再次调用OCR或模型。

来源不符、重复逻辑身份、版本不兼容或ACTIVE变化时拒绝，保留原有发布版本。发布后以真实ACTIVE成员和发布记录判断可见性；历史发布回执不直接证明仍属于当前ACTIVE。法规和案例分别投影到既有business_library；案例引用法规条文不会被当作法规结构入库。

检索新增document_type=law/case/all，默认law；HTTP检索按当前身份限制owner。PG优先采用经过校验的业务目录owner，否则采用受控来源元数据；缺少owner时普通用户失败关闭。管理员可查询所有授权业务资料，不向普通用户开放全局范围。

## 持久化与启用前置条件

SQLite继续保存解析任务，PG保存原始解析/业务目录/知识库版本，MySQL保存追加式审核。工作台操作快照保存在既有解析结果持久化目录下五类私密子目录，使用现有原子JSON写与文件锁；备份和回滚不得漏掉这些目录，不把它们提交Git。

整页修订法规的条款范围检查需要[scripts/sql/20261116_reviewed_article_range_up.sql](../../scripts/sql/20261116_reviewed_article_range_up.sql)所定义的函数升级。脚本仅已在全新隔离库执行，正式库本轮未执行；缺少标记时返回503，不自动DDL。无新增数据库引擎、表或字段。原始OCR与ACTIVE本轮不修改。

后端与新前端须一起验证和启用。正式启用仍需单独确认数据库函数升级、最终源码/镜像身份、活动任务、挂载、备份与回滚兼容性，不凭源码或离线OpenAPI宣布8180已更新。
