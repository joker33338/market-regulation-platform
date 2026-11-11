# v0.2.2 前端 ↔ 后端 真实接口映射矩阵

> 建立时间：2026-11-11
> 前端分支：`feat/frontend-api-v0.2.2`，基线 `5dd44b97710db0d3bdb84bcec6e1624dd70205dc`
> 8180 运行 revision：`4fc4cf124a120762593064676ea5f8dbe2394119`；后端契约分支当前 HEAD：`20bfeef57e101f08a2f37bd4a73b6ed4237dcba5`
> 契约版本：`frontend-api-v0.2.2-1`
> 统一后端运行镜像身份（全体 Agent 共用）：后端源码 `4fc4cf124a120762593064676ea5f8dbe2394119`，镜像 ID `sha256:8f169cd82cc1bf55807eb48a9f75e0b5206ac4cb10ca27c38fe206a85e93d7a4`，标签 `market-regulation-workbench:candidate-v022-4fc4cf124a12`，OCI revision 同源码 SHA，运行容器 `market-regulation-app-1`；六项完整记录与证据见正式报告 §1.3。
> 状态说明：§0 的运行态探测记录为旧镜像时期（11:58）事实；后续前置阻塞已解除，最终状态见 §4、§5 与仓库根 `docs/frontend-api-integration-report.md`。

## 0. 事实来源与运行态核实（不得假设接口已实现）

| 事实来源 | 位置 | 状态 |
|---|---|---|
| 正式契约 | 原始工程 worktree 的 `docs/integration/frontend-api-contract.md` | 已读，11.4 KB |
| 缺口报告 | `docs/integration/frontend-api-gap-report.md` | 已读，后端自评 `BACKEND_API_PARTIAL` |
| OpenAPI 快照 | `docs/integration/frontend-openapi.json` | 已读，OpenAPI 3.1.0，`info.version=0.2.2-api-candidate`，**22 条路径 / 16 个 schema** |
| 提交计划 | `docs/integration/v0.2.2-git-commit-plan.md` | 已读，8 个模块提交 + 28 项测试通过 |
| 运行态 OpenAPI | `GET http://127.0.0.1:8180/openapi.json` | **404**（后端 `openapi_url=None`，设计如此） |
| 认证 OpenAPI | `GET http://127.0.0.1:8180/api/openapi.json` | **404**（活动实例未加载新路由） |

**8180 活动服务实测（无 Token，2026-11-11 11:58）**：

| 路径 | 实测 | 说明 |
|---|---|---|
| `/` | 200 | 旧版「文档解析工作台」HTML |
| `/api/parse/info` | 401 | 旧接口，需 Bearer Token |
| `GET /api/parse/tasks` | 405 | 旧服务只有 `POST`，新 `GET` 列表未挂载 |
| `/api/documents`、`/api/documents/{id}`、`/api/parse/files/{id}/source` | 404 | 新接口未加载 |
| `/api/review`、`/api/review/{parse_id}` | 404 | 新接口未加载 |
| `/api/knowledge/versions`、`/api/knowledge/search` | 404 | 新接口未加载 |
| `/api/stats/overview`、`/api/system/health` | 404 | 新接口未加载 |

**运行身份**：`127.0.0.1:8180` 由 Docker 容器 `market-regulation-app-1`（`Up 3 hours`，8:44 启动）端口转发，进程为 `com.docker.backend.exe`，响应头 `server: uvicorn`。后端交付文档明确：「**不能因候选代码已提交就默认活动 8180 实例已更新**」；`v0.2.2-git-commit-plan.md` 亦写明「现有 8180 更新由用户明确授权」。因此本矩阵中「已实现」= 源码与离线契约已交付；「运行期可用」= **待授权切换候选镜像后复核**，两者不混同。

> 前端采用**运行期探测** `GET /api/openapi.json` 判定新能力是否可用；探测失败一律显示 `SERVICE_OUTDATED / NO_PERMISSION / SERVICE_UNAVAILABLE`，不把离线契约当成运行期成功，不回退 DEMO。

## 1. 七页面接口映射矩阵

「返回字段」以 `frontend-openapi.json` 的 schema 与 `qa_core/api/*.py` 实现为准；「对接状态」指本轮前端代码接入状态。

| 页面 | 功能 | 方法 | 实际 URL | 请求参数 | 返回字段 | 对接状态 |
|---|---|---|---|---|---|---|
| 文档管理 | 上传原始文件 | POST | `/api/parse/files` | query `file_name*`；body 原始字节（非 multipart） | `file_id,sha256,bytes`（201） | ✅ 已接入（复用） |
| 文档管理 | 文档列表 / 分页 / 搜索 / 筛选 | GET | `/api/documents` | `page,page_size,keyword,status,doc_type` | `DocumentList{list[DocumentInfo],total,page,page_size,source}` | ✅ 本轮接入 |
| 文档管理 | 文档详情 | GET | `/api/documents/{file_id}` | path `file_id` | `DocumentInfo` | ✅ 本轮接入 |
| 文档管理 | 关联 OCR 解析历史 | GET | `/api/documents/{file_id}/parse-history` | path `file_id` + `page,page_size` | `ListResponse{list[{task,file_id,source_file_id,database_parse_id,elapsed_seconds}]}` | ✅ 本轮接入 |
| 文档管理 / 审核 | 原始文件授权读取 | GET / HEAD | `/api/parse/files/{file_id}/source` | path `file_id`；可选 `Range`（206/416） | 二进制 + `X-SHA256`；PDF/图片 inline、DOCX attachment | ✅ 本轮接入（授权 Blob） |
| 文档管理 | 解析结果入口 | GET | `/api/parse/tasks/{task_id}/results` | path `task_id` | `TaskResults{task_id,status,results[]}` | ✅ 已接入（复用） |
| 智能解析 | 服务配置 | GET | `/api/parse/info` | 无 | `mode,provider,enabled,database_enabled,dual_engine_enabled` | ✅ 已接入（复用） |
| 智能解析 | 创建解析任务 | POST | `/api/parse/tasks` | body `{file_ids}`（白名单）；header `Idempotency-Key*` | `ParseTask`（202） | ✅ 已接入（复用） |
| 智能解析 | 任务列表 / 筛选 / 分页 | GET | `/api/parse/tasks` | `page,page_size,status,engine` | `TaskList{list[TaskSummary],total,page,page_size,source}` | ✅ 本轮接入 |
| 智能解析 | 任务详情 / 状态枚举 / 引擎 | GET | `/api/parse/tasks/{task_id}` | path `task_id` | `ParseTask`（含 `files[].selected_engine/fallback_reason/requires_review`） | ✅ 已接入（复用） |
| 智能解析 | 失败原因 | GET | `/api/parse/tasks/{task_id}/errors` | path `task_id` | `ParseTask` | ✅ 已接入（复用） |
| 智能解析 | 恢复 / 取消 | POST | `/api/parse/tasks/{task_id}/resume`、`/cancel` | path `task_id` | `ParseTask` | ✅ 已接入（复用） |
| 智能解析 | 标准化结果 | GET | `/api/parse/tasks/{task_id}/results` | path `task_id` | `TaskResults` | ✅ 已接入（复用） |
| 智能解析 | 解析产物归档 | GET | `/api/parse/tasks/{task_id}/files/{file_id}/artifact` | path `task_id,file_id` | `artifact.bin`（**非原始文件**） | ✅ 已接入（复用） |
| 智能解析 / 入库 | 法规 / 案例 Chunk 预览 | POST | `/api/parse/tasks/{task_id}/files/{file_id}/preview` | path + body `PreviewRequest{document_type:law\|case,max_chars}` | `PreviewResponse{preview,write_performed:false}` | ✅ 本轮接入 |
| 文档审核 | 完整待复核队列 | GET | `/api/review` | `page,page_size,requires_review=true` | `ListResponse{list[{parse_id,document_id,file_name,file_type,parsing_status,requires_review,source_location,quality,imported_at}]}` | ✅ 本轮接入（**不用 `v_review_queue` 视图**） |
| 文档审核 | 审核详情 / 候选对照 | GET | `/api/review/{parse_id}` | path `parse_id` | `ReviewDetail{raw_text,markdown_content,original_result,quality,source_file_id,task_id,local_candidate,local_candidate_available,review_write_supported:false}` | ✅ 本轮接入（只读） |
| 文档审核 | 已持久化结果 Chunk 预览 | POST | `/api/review/{parse_id}/preview` | path + `PreviewRequest` | `PreviewResponse` | ✅ 本轮接入（入库页复用） |
| 文档审核 | 审核通过 / 驳回 / 标记错误 / 保存修订 | — | **无接口** | — | `review_write_supported=false` | ❌ 后端明确不支持 → 按钮禁用，列入缺口 |
| 知识库入库 | 知识库版本列表 | GET | `/api/knowledge/versions` | `page,page_size` | `ListResponse{list[{kb_version,status,dimension,created_at,stats,active}]}`（public 只读） | ✅ 本轮接入 |
| 知识库入库 | 版本详情 | GET | `/api/knowledge/versions/{version}` | path `version` | `VersionInfo` | ✅ 本轮接入 |
| 知识库入库 | 正式入库批次 / 发布 / 回滚 | — | **无接口** | — | 契约「明确不支持」 | ❌ 不开放，列入缺口 |
| 法规检索 | 正式知识库检索 | POST | `/api/knowledge/search` | body `SearchRequest{query*,mode:keyword\|hybrid,limit}`（额外字段 422） | `SearchResponse{status:ready\|unpublished,kb_version,mode,list[{chunk_id,doc_version_id,regulation_name,article_no,article_text,chapter,kb_version,raw_score,score_kind,source}],count,source}` | ✅ 本轮接入 |
| 法规检索 | AI 问答 / 生成式结论 | — | **无接口** | — | 后端仅检索，不生成回答 | ❌ 页面不宣称支持 |
| 首页工作台 | 真实统计与趋势 | GET | `/api/stats/overview` | `days`（1–366，默认 14） | `StatsResponse{generated_at,window,uploads,tasks,parsed_documents,recent_tasks}` | ✅ 本轮接入 |
| 首页工作台 | 组件状态 | GET | `/api/system/health` | 无 | `HealthResponse{status,components}` | ✅ 本轮接入 |
| 系统监控 | 健康检查 | GET | `/api/system/health` | 无 | `components{fastapi,task_store,postgresql,paddle_ocr,pp_structure,bge_m3,mineru}` 各含 `state,check,model_ready?,configured?` | ✅ 本轮接入 |
| 系统监控 | 系统资源 / 接口调用 / 错误日志 | — | **无接口** | — | 缺口报告明确不实现 | ❌ 显示未接入空态 |
| 开发联调 | 运行期能力探测 | GET | `/api/openapi.json` | 无（需 Bearer Token） | `app.openapi()`，含 `paths` 与 `info.version` | ✅ 本轮接入（能力开关依据） |

**统计**：真实 HTTP 路径 **22 条**（复用 9 + 新增 13），前端已接入 22 条；后端明确不支持的能力 **8 组**（审核写入 4、入库批次/发布/回滚 3、结构化日志 1），前端一律禁用或空态。

## 2. 统一契约要点

- **认证**：所有 `/api/*` 携带 `Authorization: Bearer <会话凭证>`，复用服务端 Token→owner 映射；不存在或跨用户返回 404。浏览器不持有 MinerU Key / 数据库凭据。
- **列表**：统一 `{list,total,page,page_size,source}`，`page` 从 1、`page_size` 1–100 默认 20；空列表是合法 200。
- **错误**：`{ "error": { "code": "..." } }`；401 未认证 / 404 不存在或无权限 / 409 幂等冲突·完整性·预览门禁 / 413 超限 / 415 类型不符 / 416 Range 越界 / 422 参数无效 / 429 并发上限 / 503 未配置或只读服务不可用 / 502 旧解析远端故障。旧创建任务非法字段仍 400。
- **身份不可推导**：`file_id`（上传 ID）≠ 任务内 `files[].file_id`（任务文件 ID）；`document_id` 为结果身份；`database_parse_id` 为持久化回执。原文件用 `source_file_id`，artifact / 任务 preview 用任务文件 ID，审核用 `database_parse_id`，映射取自 `file_mappings` / 解析历史。
- **真实性边界**：`uploaded_at_source=metadata_mtime` 只能标为「元数据修改时间」；`status` 仅有 `uploaded / pending_review` 与真实任务状态，不得臆造「已审核 / 已入库」；统计的 `uploads / tasks / parsed_documents` 来源与范围不同，**不相加**；DB 不可用 `available=false`、计数 `null`，显示「暂无数据」而非 0；`engine_file_selections` 是文件引擎选择次数，**不等于任务数**。
- **健康五态**：仅 `fastapi`（请求被处理）、`task_store`（SQLite 只读查询）、`postgresql`（只读查询）可为 ONLINE；本地模型仅文件检查 → UNKNOWN，MinerU 仅配置检查 → UNKNOWN / NOT_CONFIGURED。响应不含 DSN / Token / 模型路径 / 异常堆栈。
- **检索**：仅 public 的 ACTIVE 版本；`status=unpublished` → 显示「知识库尚未发布」；`raw_score` 的 `keyword_match` 只表示匹配、`rrf` 为融合排序分，**不是法律准确率**；不编造发布机关、法效日期、历史版本。
- **预览**：`write_performed=false`，门禁失败 409 不是空成功；Chunk 预览成功 ≠ 正式入库成功。

## 3. 前端接入策略

1. 复用唯一 Axios 实例 `src/api/client.ts`，不新增第二套请求层；Base URL 固定同源 `/`，Vite 代理指向 8180（target 支持 `VITE_API_PROXY_TARGET` 覆盖，生产构建不含本地地址）。
2. 所有页面数据来自 `src/api/frontend.ts` 的真实请求函数；`src/api/mock/**` 从页面引用中全部移除（隔离，不作为业务结果渲染）。
3. 能力判定由 `GET /api/openapi.json` 运行期探测驱动，页面不硬编码「已接入」；探测失败展示明确异常态 + 重试，绝不回退 DEMO。
4. 写操作（审核 4 个、入库发布/回滚）依据 `review_write_supported` 与契约「明确不支持」保持禁用，不前端改状态假装成功。
5. 原始文件预览：Axios 取 `ArrayBuffer` → 创建 Blob URL → PDF 用浏览器内置渲染、图片用 `<img>`、DOCX 按后端 attachment 契约提供授权下载；离开页面 `revokeObjectURL`。**不引入新依赖**，不把带鉴权要求的接口 URL 塞进无请求头的 iframe。

## 4. 联调前置条件（2026-11-11 复测：已满足）

| 原阻塞项 | 上一轮状态 | 本轮实测 | 责任/结果 |
|---|---|---|---|
| 8180 活动实例为 v0.2.1 旧镜像 | 新接口全部 404 | 已重建为 `market-regulation-workbench:candidate-v022-4fc4cf124a12`，`market-regulation-app-1` healthy；`GET /api/openapi.json` 200 / 22 路径 / `0.2.2-api-candidate` | 用户已交付 `docs/integration/v0.2.2-local-runtime-handoff.md`；前端未自行切换 Docker |
| 缺少联调 Token | `/api/*` 全 401 | 复用本机 ignored 私有运行配置中的已有会话凭证（owner=`local-user`，长度 43），仅内存 + sessionStorage | 未写入任何源码、文档或 Git |
| 审核写入、正式入库批次/发布/回滚、结构化日志、资源监控接口 | 保持禁用/空态 | 契约「明确不支持」，仍保持禁用 | 后端后续迭代（缺口清单见 `frontend/docs/frontend-api-integration-report.md` §10） |
| 正式 public 知识库 ACTIVE 版本 | 检索页空态 | `POST /api/knowledge/search` 实测 `status=unpublished, count=0`，页面显示「知识库尚未发布」 | 后端/QA 按既有授权流程发布，前端不写库 |

## 5. 最终联调结论（2026-11-11 运行期浏览器复测）

七页面与全部约定只读路径已完成真实浏览器端到端联调（前端 `feat/frontend-api-v0.2.2` @ `96d4052`，12 个本地 commit）：

- **运行期契约**：`GET /api/openapi.json` → 200，`info.version=0.2.2-api-candidate`，22 路径；页面契约标签均为「契约就绪」。
- **七页面**：1440×900 全量渲染 + 交互，`errors=[]`、`apiFails=[]`；1366 / 1920 抽查无横向溢出。
- **真实数据**：文档 4 条、任务 3 条、待复核 7 条、统计 `4 / 3 / 7 / 7`（来源分离不相加）、健康七组件五态；审核详情 1.2 MB + 原件 `/source` 200 + `x-sha256` 校验；两类 Chunk 预览 `write_performed=false`；检索 keyword / hybrid 均 `unpublished`。
- **状态与错误态**：未认证（零业务请求）、401 / 404 / 416 / 422、200 空列表、`artifact.bin` 404 均无假成功；四个审核写按钮与入库批次/发布/回滚保持禁用。
- **真实性治理**：七个页面零 `api/mock` / `DemoBadge` 引用、零实际 `v-html`；生产产物无本地地址与过时 DEMO 文案；`npm run typecheck` / `npm run build` 通过。
- **联调后修正**：检索页初始空态与契约探测、登录页过时 DEMO 文案、favicon 404、发布状态标签（详见报告 §7，提交 `96d4052`）。

因此最终状态为（范围限定：约定只读能力 + 七页面交互，不含写链路 / 独立 QA / 生产部署）：

```
FRONTEND_INTEGRATION_READY
```

完整证据、接口逐条实测、三场景矩阵、8 组缺失接口与 7 类未验证事项见 `frontend/docs/frontend-api-integration-report.md`。报告明确：本报告不代表 QA PASS 或生产可用，后端自评仍为 `BACKEND_API_PARTIAL`、未达合并 main 门禁。
