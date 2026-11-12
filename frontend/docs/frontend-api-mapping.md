# 前端 API 接口映射表

> 项目：市场监管智能文档解析与法规知识库管理平台（`frontend/`，分支 `feat/frontend-v0.2.1`）
> 基线：`codex/fix-v0.2.1` @ `f4a0af8`；2026-11-11 复核至 `5dd44b9`（发布归档）/ `3129479`（Fix 交接 HEAD）/ `843c64d`（QA 裁决）
> 更新：2026-11-10 首次编制；**2026-11-11 契约复核后更新**（见 §6）
> **事实来源**：`qa_core/document_parsing/mineru_api.py` 路由源码 + 后端自带参考客户端 `qa_core/document_parsing/parsing_upload.html`。
> 后端 `create_app()` 设置 `docs_url=None, redoc_url=None, openapi_url=None`，实测 `/openapi.json` = 404，**无法以 OpenAPI 为准**。
> 状态说明：`已实现` = 后端已有路由；`已接入` = 前端已调用；`Mock` = 使用 DEMO 数据并显著标注。

---

## 1. 已实现的真实接口（后端 f4a0af8）

| # | 页面 | 方法 | 路径 | 请求参数 | 响应字段 | 已实现 | 已接入 | Mock |
|---|---|---|---|---|---|---|---|---|
| A1 | 系统监控 | GET | `/` | 无（无鉴权） | 自带上传页 HTML | ✅ | ⭕ 未使用 | — |
| A2 | 工作台 / 解析中心 / 系统监控 | GET | `/api/parse/info` | Header `Authorization: Bearer <token>` | `{mode, provider, enabled, database_enabled, dual_engine_enabled}` | ✅ | ✅ 真实探活 | ❌ |
| A3 | 文档管理 | POST | `/api/parse/files` | Query `file_name`；**Body = 原始文件二进制流**（非 multipart）；≤100MB；后缀 `.pdf/.docx/.png/.jpg/.jpeg`；校验文件头魔数 | 201 `{file_id, sha256, bytes}`；400/413/415/503 | ✅ | ✅ 已修正为原始流 | ❌ |
| A4 | 解析中心 | POST | `/api/parse/tasks` | JSON 白名单 `{file_ids, strategy?, allow_cloud_fallback?, sensitive?}`；`file_ids` 32 位十六进制 1–20 个；可选 `Idempotency-Key` | 202 `public(task)` | ✅ | ✅ 已修正白名单 | ❌ |
| A5 | 解析中心 / 文档管理 | GET | `/api/parse/tasks/{id}` | Path `id` | `public(task)`：`task_id,status,mode,cancel_requested,cancel_scope,provider,created_at,completed_at,error,files[]`；`files[]` 含 `sha256,selected_engine,requires_review,fallback_reason,database_parse_id,status,error` | ✅ | ✅ 含 2s 轮询 | ❌ |
| A6 | 解析中心 | GET | `/api/parse/tasks/{id}/errors` | Path `id` | **仍为 `public(task)`**，非独立错误列表 | ✅ | ✅ | ❌ |
| A7 | 解析中心 | POST | `/api/parse/tasks/{id}/resume` | Path `id` | `public(task)` | ✅ | ✅ 仅真实任务可用 | ❌ |
| A8 | 解析中心 | POST | `/api/parse/tasks/{id}/cancel` | Path `id` | `public(task)` | ✅ | ✅ 仅真实任务可用 | ❌ |
| A9 | 解析中心 | GET | `/api/parse/tasks/{id}/results` | Path `id` | `{task_id, status, results:[{file_id, document}]}`，路径已脱敏 | ✅ | ✅ | ❌ |
| A10 | 解析中心 | GET | `/api/parse/tasks/{id}/files/{file_id}/artifact` | Path `id`, `file_id` | `FileResponse(artifact.bin)` 二进制（**解析产物，非原始文件**） | ✅ | ✅ 按 `arraybuffer` 接收 | ❌ |

**统一鉴权**：`Authorization: Bearer <token>`，Token ≥32 位，来源 `PARSING_API_TOKENS_JSON`，后端按 owner 隔离目录。前端 Token 仅内存 + `sessionStorage`，不写 `localStorage`、不打印日志；浏览器不接触 MinerU API Key 与数据库口令。

**开发期通路**：Vite dev proxy 将 `/api` 转发至 `http://127.0.0.1:8180`。

---

## 2. 按页面汇总

| 页面 | 路由 | 真实接口 | 使用 Mock 的能力 | 写操作状态 |
|---|---|---|---|---|
| 首页工作台 | `/dashboard` | A2（FastAPI 探活） | 6 统计卡、趋势、引擎分布、成功率、待处理任务、最近入库、其余 5 组件状态 | 无写操作 |
| 文档管理 | `/documents` | A3（上传）、A5（解析历史） | 文档列表 / 搜索 / 筛选 / 分页 | 上传真实；下载、重新解析禁用（接口未接入） |
| 智能解析中心 | `/parsing` | A2、A4、A5、A6、A7、A8、A9、A10 | 任务列表、引擎统计面板 | 创建任务真实；重试 / 取消仅对真实任务启用 |
| 文档审核中心 | `/review` | A9（预留） | 审核队列、解析结果、质量指标、原始文件预览 | **4 个审核写操作全部 disabled** |
| 知识库入库管理 | `/knowledge/ingestion` | 无 | 流水线、批次、法规数据、检查清单、版本检查 | **发起批次 / 预检 / 授权全部 disabled** |
| 法规知识检索 | `/knowledge/search` | 无 | 检索 UI、结果字段契约说明（**无任何法条原文**） | 检索按钮禁用；显示「未检索到相关依据」 |
| 系统监控 | `/system` | A2 | 组件状态（除 FastAPI）、审计日志、接口调用记录 | Token 保存为本地会话行为，非后端写入 |
| 登录 | `/login` | A2（验证） | 无 | 保存会话 Token |

---

## 3. 后端待交付接口（前端已建适配层，接口到位即启用）

完整需求规格见 `docs/backend-api-requirements.md`。下表的「前端适配点」即接口交付时只需修改的位置。

| # | 方法 / 路径 | 用途 | 前端适配点 | 优先级 |
|---|---|---|---|---|
| B1 | `GET /api/parse/files/{file_id}/source` | 原始文件真实预览与下载（支持 Range、返回 SHA256） | `src/api/documentFiles.ts` + `apiCapabilities.sourceFile` | **P0** |
| B2 | `GET /api/documents` | 文档列表 / 搜索 / 筛选 / 分页 | `src/views/DocumentsView.vue` 的 `MrProTable` fetcher + `apiCapabilities.documentList` | **P0** |
| B3 | `GET/POST /api/review/{doc_id}/...` | 审核读写与审计留痕 | `src/views/ReviewView.vue` 按钮禁用条件 + `apiCapabilities.reviewWrite` | **P0** |
| B4 | `GET /api/documents/{id}` + `/parse-history` | 文件详情与解析历史 | `DocumentsView.vue` 详情抽屉 | P1 |
| B5 | `GET /api/parse/tasks` | 解析任务列表 | `ParsingView.vue` 任务表 fetcher | P1 |
| B6 | `GET /api/parse/tasks/{id}/logs` | 结构化日志 | `ParsingView.vue` 日志抽屉 | P1 |
| B7 | `GET /api/parse/engines/status` | 三引擎真实状态（不得返回 Key） | `ParsingView.vue` 引擎面板 + `apiCapabilities.engineStatus` | P1 |
| B8 | `GET /api/stats/overview`、`/trend` | 统一统计与趋势 | `src/api/mock/stats.ts` 数据源 + `apiCapabilities.dashboardStats` | P1 |
| B9 | 入库 5 接口（precheck / batches / stages / version-check） | 入库前检查、批次授权、阶段状态、kb_version 阻断 | `IngestionView.vue` + `apiCapabilities.ingestion` | P1 |
| B10 | `POST /api/knowledge/search` | 法规检索（返回来源文件与原始分数） | `src/api/mock/search.ts` + `apiCapabilities.knowledgeSearch` | P1 |
| B11 | `GET /api/system/health` 等 | 六组件五态、系统资源、日志 | `SystemView.vue` + `apiCapabilities.systemHealth` | P1 |
| B12 | 非生产启用 `openapi_url` | 自动生成接口映射 | 本文档可改为自动生成 | P2 |

---

## 4. 接口契约中的已知陷阱（前端已规避）

1. **A3 不是 multipart**：后端 `request.stream()` 读原始字节并校验前 8 字节魔数；发送 `multipart/form-data` 必然 415。前端已改为 `body: File` 原始流。
2. **A4 是白名单校验**：多传 `mode` 等字段会 400；且返回的是完整 `public(task)` 而非 `{task_id}`。
3. **A6 返回 `public(task)`**：错误详情要从 `files[].error` 取，不能当数组渲染。
4. **A10 的 `artifact.bin` 不是原始证据文件**：仅为 MinerU 解析产物归档，不得用于 PDF / Word 预览。
5. **`ParseServiceInfo` 无 `version` / `environment` 字段**：系统页已移除伪字段展示。
6. **引擎路由决策在后端**：`selected_engine` / `fallback_reason` / `requires_review` 一律以 A5 返回为准，前端不按文件类型自行判断。

---

## 5. 数据真实性规则

- 所有数据经 `src/api/dataSource.ts` 的 `apiCapabilities` 判定来源；`real` 显示 `REAL`，`demo` 显示 `DEMO` 徽章并贴近数值。
- 统计全部来自 `src/api/mock/stats.ts` 单一快照，恒等式 `成功 + 失败 + 执行中 = 任务总数`，引擎分布之和等于任务总数，统一近 14 天口径。
- 组件状态五态 `ONLINE / OFFLINE / NOT_CONFIGURED / UNKNOWN / ERROR`，**只有 A2 真实探测成功才允许 ONLINE**。
- 无检索依据时显示「未检索到相关依据（检索接口未接入）」，**前端不生成、不伪造任何法条原文或法律结论**。
- 所有未接入的写操作一律 `disabled` + 说明原因，不出现「点击后假装成功」。
- 原始证据文件只读；SHA256 以后端 A3 返回为准，前端计算值仅用于重复文件识别提示。

---

## 6. 2026-11-11 契约复核（QA PASS 后）

用户告知 v0.2.1 审查已通过，要求「整体接入与更新接口」。以代码为准复核后的结论：

### 6.1 QA 结论与边界

| 项 | 事实 |
|---|---|
| 裁决文件 | `docs/qa/v0.2.1/final-release-decision.md`（QA 分支 `843c64d`），签发 2026-11-11，结论 **PASS** |
| 通过范围 | 后端 MVP + c915 候选镜像的本地集成验收；源码身份 `c91547d393ca6b049e216c0051e25271d06d7359` |
| **明确排除** | 生产部署、活动旧实例切换、Windows 整机恢复、**独立前端全部联调**、外部来源迁移、多 Worker、MySQL 任务迁移 |
| 发布归档 | `codex/maint-v0.2.1-original` @ `5dd44b9`；Fix 正式交接 `3129479` |

QA 裁决原文：「外部来源迁移、多Worker、MySQL任务迁移、**独立前端全联调**、大规模效果优化继续是后续范围」；且「活动旧实例不是本次PASS镜像」。因此 **QA PASS 不等于前端可以标记功能正式可用**，也不等于新增接口已交付。

### 6.2 接口契约复核结果：零变化

对四个提交逐一提取 `@app.*` 路由定义：

| 提交 | 分支 | 路由数 | 结论 |
|---|---|---|---|
| `f4a0af8` | `feat/frontend-v0.2.1`（前端基线） | 9 个 API + 根页面 | 基准 |
| `3129479` | `codex/fix-v0.2.1` | 9 个 API + 根页面 | 逐行一致 |
| `843c64d` | `codex/qa-v0.2.1` | 9 个 API + 根页面 | 逐行一致 |
| `5dd44b9` | `codex/maint-v0.2.1-original` | 9 个 API + 根页面 | 逐行一致 |

- `mineru_api.py` 从 `f4a0af8` → `5dd44b9` 的 diff **只有 3 处注释中文化**，路径、参数、响应字段、状态码、鉴权逻辑全部未变；`create_app()` 仍为 `docs_url=None, redoc_url=None, openapi_url=None`。
- `GET /api/parse/info` 仍返回 `{mode, provider, enabled, database_enabled, dual_engine_enabled}`，无 `version` / `environment`。
- 全仓仅 `qa_core/document_parsing/mineru_api.py` 含 `FastAPI(...)`，**没有第二套 HTTP 服务**；新增的 `deploy/local/entrypoint.py` 只是 `uvicorn ... create_app --factory --port 8180` 启动器；新增的 `qa_core/indexing/preview.py` 是 CLI/服务层只读切分预览，明确「不审核、向量化、建表或发布版本」，不是 HTTP 接口。
- 在线实例 `127.0.0.1:8180` 探测：`/openapi.json` 404、`/docs` 404、`/api/documents` 404、`/api/system/health` 404、`/api/stats/overview` 404、`/api/parse/engines/status` 404、`/api/ingestion/batches` 404、`/api/knowledge/search` 404、`/api/review/*` 404；`/api/parse/info` 无 Token 返回 401（符合既有鉴权）。

### 6.3 对本轮「整体接入」的实际影响

| 项 | 变化 |
|---|---|
| 真实 API 接入数量 | **仍为 9 个**，无一新增（本轮无接口可接） |
| Mock / 未接入能力 | **仍为 11 组**，`apiCapabilities` 的 false 项一个都不能置 true |
| 前端 QA 状态 | 5 处「尚未完成 QA 验收」改为统一常量 `src/config/release.ts`：后端 MVP 有限范围 PASS、独立前端全联调未完成、不宣称正式可用 |
| 系统监控页 | 新增「接口接入状态总览」，计数取自 `apiCapabilities`（9 已接入 / 11 待交付），列出路径、优先级与解锁能力 |
| 页面写操作 | 仍全部禁用（禁用原因是接口不存在，与 QA 是否通过无关） |

**结论**：本轮能做的是「状态与文案更新 + 契约复核留痕 + 接口清单可视化」，不是「接入新接口」。真正接入需后端交付 §3 的 P0 三组并提供联调 Token；届时只需替换适配层并把 `apiCapabilities` 对应项置 `true`，页面无需重做。
