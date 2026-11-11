# v0.2.2 前后端 API 契约

契约版本：`frontend-api-v0.2.2-draft-1`。本文件随模块提交更新实现状态。

开发基线：`5dd44b97710db0d3bdb84bcec6e1624dd70205dc`，包含维护提交及 v0.2.1 已验收业务源码 `c91547d393ca6b049e216c0051e25271d06d7359`。历史 QA PASS 不代表本轮接口或独立前端联调已通过。

## 认证与通用规范

所有 `/api/*` 请求携带 `Authorization: Bearer <会话凭证>`，复用服务端 Token→owner 映射。浏览器不得持有 MinerU Key 或数据库凭据。不新增登录、审核身份、管理员权限系统。任务、源文件和审核结果按 owner 隔离；不存在或跨用户访问返回 404。public 法规知识库为已认证用户共享的正式检索域。

新增列表统一返回 `{list,total,page,page_size,source}`；page 从 1 开始，page_size 为 1–100，默认 20。空列表是合法 200。除明确给出筛选参数外，不支持任意排序、时间区间或其他字段筛选。不得根据前端 DEMO 中的状态臆造已审核、已入库等状态。

错误沿用 `{ "error": { "code": "..." } }`。401 未认证；404 不存在或无权限；409 幂等冲突、文件完整性或预览门禁；413 超限；415 类型不符；422 新接口参数无效；429 队列或模型查询并发上限；503 未配置或只读服务不可用；旧解析远端故障沿用 502。已有任务创建的非法 JSON/字段仍返回原有 400，不改变兼容行为。Range 越界由文件响应返回 416。

前端使用同源 `/api` 代理，统一指向 `http://127.0.0.1:8180`，不另建长期候选后端。不能因候选代码已提交就默认活动 8180 实例已更新。Agent C 统一负责候选镜像构建与交接，检查活动任务、状态挂载和回滚镜像并完成隔离测试后，经批准才切换 8180；QA 验收期间冻结运行镜像。运行身份记录见 `v0.2.2-backend-api-handoff.md`。

## 七页面接口矩阵

“复用”表示维护基线已有；“新增目标”仅在相应模块提交和测试记录齐全后视为实现。下列是选定契约路径，非前端建议路径的全部承诺。

| 页面 | 功能 | 方法 | 路径 | 请求参数 | 响应 | 基线状态/缺口 | 权限 |
|---|---|---|---|---|---|---|---|
| 文档管理 | 上传 | POST | `/api/parse/files` | query file_name，body 原始文件字节 | 201 file_id,sha256,bytes | 复用 | owner |
| 文档管理 | 文档列表 | GET | `/api/documents` | page,page_size,keyword,status,doc_type | DocumentList | 新增目标 | owner |
| 文档管理 | 详情 | GET | `/api/documents/{file_id}` | 上传 ID | DocumentInfo | 新增目标 | owner |
| 文档管理 | 解析历史 | GET | `/api/documents/{file_id}/parse-history` | 上传 ID，分页 | task、任务文件 ID、parse_id 映射 | 新增目标 | owner |
| 文档管理/审核 | 原文件 | GET/HEAD | `/api/parse/files/{file_id}/source` | 上传 ID；可选 Range | 原始二进制、X-SHA256；206/416 | 新增目标 | owner |
| 智能解析 | 服务信息 | GET | `/api/parse/info` | 无 | mode,provider,enabled,database_enabled,dual_engine_enabled | 复用 | 登录 |
| 智能解析 | 创建任务 | POST | `/api/parse/tasks` | file_ids；可选 strategy,allow_cloud_fallback,sensitive；Idempotency-Key | 202 ParseTask | 复用 | owner；云权限由服务器判定 |
| 智能解析 | 任务列表 | GET | `/api/parse/tasks` | page,page_size,status,engine | ParseTask 列表及 file_mappings | 新增目标 | owner |
| 智能解析 | 任务详情/失败 | GET | `/api/parse/tasks/{task_id}`、`/api/parse/tasks/{task_id}/errors` | 任务 ID | 同一 ParseTask 结构 | 复用 | owner |
| 智能解析 | 恢复/取消 | POST | `/api/parse/tasks/{task_id}/resume`、`/api/parse/tasks/{task_id}/cancel` | 任务 ID | ParseTask | 复用，不扩大恢复权限 | owner |
| 智能解析 | 结果 | GET | `/api/parse/tasks/{task_id}/results` | 任务 ID | task_id,status,results[{file_id,document}] | 复用 | owner |
| 智能解析 | 产物归档 | GET | `/api/parse/tasks/{task_id}/files/{file_id}/artifact` | 任务 ID、任务文件 ID | artifact.bin，绝非原始文件 | 复用 | owner |
| 文档审核 | 待审核列表 | GET | `/api/review` | page,page_size,requires_review=true | document_review.documents 列表 | 新增目标；不只读 v_review_queue | owner |
| 文档审核 | 详情与候选对照 | GET | `/api/review/{parse_id}` | PostgreSQL parse_id | ReviewDetail | 新增目标；无正式写入 | owner |
| 入库管理 | Chunk/结构预览 | POST | `/api/parse/tasks/{task_id}/files/{file_id}/preview` | document_type=law/case,max_chars | preview,write_performed=false | 新增目标；不入库 | owner |
| 入库管理/审核 | 已持久化结果预览 | POST | `/api/review/{parse_id}/preview` | 同上 | 同上 | 新增目标；不审核 | owner |
| 入库管理 | 版本列表/详情 | GET | `/api/knowledge/versions`、`/api/knowledge/versions/{version}` | 列表分页；版本字符串 | 版本状态、active、维度、创建时间、stats | 新增目标；public 只读 | 登录 |
| 法规检索 | 查询 | POST | `/api/knowledge/search` | query,mode=keyword/hybrid,limit | SearchResponse | 新增目标；仅 ACTIVE public | 登录 |
| 首页 | 统计及趋势 | GET | `/api/stats/overview` | days=14，1–366 | StatsResponse | 新增目标；标明来源、范围 | owner |
| 系统监控 | 健康 | GET | `/api/system/health` | 无 | HealthResponse | 新增目标；不推理、不调用云 | 登录 |
| 开发联调 | OpenAPI | GET | `/api/openapi.json` | 无 | 实际 app.openapi() | 新增目标；仍关闭匿名 /openapi.json | 登录 |

## 文件与任务身份

`file_id`（上传返回）对应 owner 上传目录中的原始字节和元数据；任务内 `files[].file_id` 是本地任务文件 ID，二者不相同。详情响应的 `document_id` 是解析结果身份；`database_parse_id` 是实际持久化回执，不是文件 Hash 或任务 ID。

用文档历史或任务列表的 `file_mappings` 获取映射。原文件下载使用 source_file_id，artifact 和任务 preview 使用任务文件 ID，审核使用 database_parse_id。禁止拼接推导 ID。

## 请求和响应示例（仅合成数据）

上传（非 multipart）：

```http
POST /api/parse/files?file_name=sample.pdf
Authorization: Bearer <session-token>
Content-Type: application/pdf

<PDF 原始字节>
```

```json
{"file_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","sha256":"<64hex>","bytes":128}
```

创建任务：

```json
{"file_ids":["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]}
```

必须提供稳定 `Idempotency-Key`。strategy/allow_cloud_fallback/sensitive 仅在已有双引擎配置支持时传入；这些参数不能授权云端外传。

文档列表：

```json
{"list":[{"file_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","file_name":"sample.pdf","doc_type":"pdf","size_bytes":128,"sha256":"<64hex>","uploaded_at":"2026-11-11T00:00:00+00:00","uploaded_at_source":"metadata_mtime","status":"uploaded","latest_task_id":null,"parse_count":0}],"total":1,"page":1,"page_size":20,"source":"owner_upload_metadata+sqlite.parse_tasks"}
```

uploaded_at_source=metadata_mtime 表示历史上传缺乏显式时间戳，仅可用元数据修改时间；不得向用户宣称它是确证的上传时间。status 使用真实文件任务状态，未创建任务为 uploaded；completed 且 requires_review 为 true 时列表显示 pending_review。不提供 reviewed/ingested 的推测状态。

读取原文件使用认证 Axios ArrayBuffer/Blob，再创建临时 URL；不能直接把带鉴权要求的接口地址塞进无请求头的 iframe。离开页面撤销 Blob URL。PDF/图片 inline、DOCX attachment；不提供 Word→PDF 转换。文件名和下载头由后端编码，浏览器不解析 artifact.bin 冒充原文。

任务列表项保留旧 ParseTask 字段并增加 `elapsed_seconds`（仅记录过时非空）和 `file_mappings`。质量详情从现有 results.document.quality 读取；引擎路由追踪位于 quality.routing_trace。不存在确定总工作量时不得模拟进度百分比。

审核详情包含 parse_id、document_id、source_file_id、task_id、quality、raw_text、markdown_content、original_result（含 pages/layout_blocks/tables）及 local_candidate。最终候选是 original_result。local_candidate_available=false 表示本地 checkpoint 未保留或身份无法核验，不能伪造对照；review_write_supported 恒为 false。前端必须把 Markdown/表格 HTML 作为不可信内容安全渲染，不能直接执行 HTML。

预览：`{"document_type":"law","max_chars":800}`；使用原有预览器返回 parents/chunks/tables/quality/warnings，法规表格等门禁失败 409，失败不是空成功。预览不创建版本、不嵌入、不发布、不自动认定法效。

检索：`{"query":"合成规范","mode":"keyword","limit":8}`。keyword 复用关键词检索、不加载模型；hybrid 复用 BGE-M3 混合检索，模型签名必须与 ACTIVE 一致，单进程受限并发返回 429。默认只允许本地向量模型，不隐式请求外部 Embedding。

```json
{"status":"unpublished","kb_version":null,"mode":"keyword","list":[],"count":0,"source":"public"}
```

有命中返回 chunk_id、doc_version_id、regulation_name、article_no、article_text、chapter、kb_version、raw_score、score_kind、脱敏 source 元数据。keyword_match 分数只表示匹配，不是法律准确率；rrf 是融合排序分数。尚无效力日期、发布机关等可靠字段时不编造。不支持历史版本查询、semantic-only 或未实现的筛选参数（额外 JSON 字段 422）。

统计：uploads=当前用户全部上传元数据，tasks=当前用户指定窗口的 SQLite 任务，parsed_documents=当前用户 document_review 全历史解析回执。不同对象及范围分开返回，不能相加。status_distribution 之和等于任务 total；engine_file_selections 是文件引擎选择次数，**不保证等于任务数**。created_daily 为真实任务创建日计数，不是处理耗时或成功数。DB 不可用时 available=false、计数=null，不能显示 0 假装已连接。

健康：FastAPI 请求成功/任务库只读查询成功才能为 ONLINE；PostgreSQL 只读查询成功才能 ONLINE。本地模型仅文件检查，MinerU 仅检查配置，均为 UNKNOWN/NOT_CONFIGURED，不能据此宣称推理或云 API 在线。浏览器不返回 DSN、Token、模型路径或异常堆栈。

## 明确不支持

正式审核通过/驳回/编辑及审核日志写入；任意路径脚本执行；自动入库批次、发布、回滚；虚构引擎日志；操作系统敏感日志；生产资源监控；自动填充 public；匿名 OpenAPI；新登录系统。本轮前端只读，页面切换能力开关须 WorkBuddy 按本契约独立提交并经 QA。

真实响应 Schema 以本分支实际 `/api/openapi.json` 及同目录导出文件为准。模块提交 SHA 和验证结果见 `v0.2.2-git-commit-plan.md`。
