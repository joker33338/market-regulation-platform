# 后端接口需求规格 v1 · 前端接入前置条件

> 生成时间：2026-11-10 (GMT+8)
> 前端项目：`F:\刘凯工作\market-regulation-platform-frontend\frontend`
> 分支基线：`feat/frontend-v0.2.1` @ `f4a0af8`（基于 `codex/fix-v0.2.1`）
> **当前状态（2026-11-11 更新）：后端 MVP 有限范围 QA 已 PASS，但四个最新提交的 HTTP 路由仍只有 9 个 API、契约零变化，本清单中的 P0 / P1 接口一个都未交付。前端优化已完成并保持「只读 + 写操作禁用 + 显著 DEMO」；接口真正提供后再做真实接入。QA PASS 不等于接口交付，也不等于独立前端全联调通过。**
> 事实来源：`qa_core/document_parsing/mineru_api.py` 路由源码 + 后端自带参考客户端 `qa_core/document_parsing/parsing_upload.html`。
> 注意：后端 `create_app()` 显式设置 `openapi_url=None`，实测 `/openapi.json` = 404，因此无法以 OpenAPI 为准，只能以源码为准。

---

## 0. 本轮工作边界与真实接入触发条件

| 项 | 状态 |
|---|---|
| 前端优化 | **已完成（2026-11-10）**；只修改 `frontend/` 目录内文件 |
| Git | 分支 `feat/frontend-v0.2.1`；工作区仅 `?? frontend/`（前端整体 untracked、从未提交）；无 commit / merge / push |
| 后端 / QA 工作区 | 未触碰；`qa_core/**`、`.venv*`、模型、`.env` 均只读 |
| 基线构建 | `npm run build` 通过（Vite 4.5.14） |
| 服务 | 后端 `127.0.0.1:8180` 在线；前端用 `npm run preview`（4173）提供构建产物预览 |

### 0.1 QA PASS 的边界（2026-11-11 复核）

`docs/qa/v0.2.1/final-release-decision.md`（`843c64d`）签发 **PASS**，但裁决明确：通过范围是「后端 MVP 及候选镜像的本地集成验收」，**不表示**生产部署、活动旧实例切换、Windows 整机恢复或**独立前端全部联调通过**；「独立前端全联调」被列为后续范围。

复核 `f4a0af8` / `3129479` / `843c64d` / `5dd44b9` 四个提交的 `mineru_api.py`：**路由定义逐行一致，仍为 9 个 API**，diff 仅注释中文化；全仓无第二套 HTTP 服务；`openapi_url=None` 依旧；在线实例对 §2/§3 列出的所有新接口均返回 404。

**因此「后端 QA 通过」不改变本清单的任何一条需求**：P0 三组仍是硬阻塞，`apiCapabilities` 的 11 个 false 项一个都不能置 true，前端 4 个审核写操作、入库批次、检索按钮继续禁用。只有后端真正实现并通过对应接口的验证，才能进入下面的接入流程。

**本轮已做（不依赖新接口）**：现有 9 个真实接口的契约修正与接入、UI/交互统一、统计口径一致性、Mock 层收敛与 DEMO 标注、Token 安全、状态语义五态/四态、写操作禁用、文档/任务/审核/入库/检索的可插拔接口适配层、接口映射文档、构建与类型检查与页面回归。

**接口到位后才做（真实接入触发条件）**：

1. 下文 **§2 P0 三组接口** 完成开发并通过 QA；
2. 后端提供可联调的访问 Token（≥32 位）与接口变更说明；
3. 后端确认 §1 现有 9 个接口契约未变，或同步给出变更后的契约；
4. 用户明确下达「接口已提供，可以接入」指令。

接口到位后，前端只需替换适配层实现即可启用真实预览 / 审核写入 / 列表 / 统计 / 检索 / 入库，无需重做页面。全程不重新设计、不新增页面、不升级 Vue / Vite / Element Plus 核心版本。

---

## 1. 现有可对接接口（已按源码核实，无需新增）

前端将直接按以下契约接入，共 **9 个真实接口 + 1 个无鉴权页面**。这些是既成事实，后端如要改动需提前通知前端。

| # | 方法 | 路径 | 请求要点 | 响应要点 |
|---|---|---|---|---|
| A1 | GET | `/` | 无鉴权 | 自带上传页 HTML |
| A2 | GET | `/api/parse/info` | Bearer Token | `{mode, provider, enabled, database_enabled, dual_engine_enabled}`（**无 version / environment 字段**） |
| A3 | POST | `/api/parse/files` | `?file_name=`；body 为**原始文件二进制流**（非 multipart）；≤100MB；后缀白名单 `.pdf/.docx/.png/.jpg/.jpeg`；校验文件头魔数 | 201 `{file_id, sha256, bytes}`；400 / 413 / 415 / 503 |
| A4 | POST | `/api/parse/tasks` | JSON 仅允许 `{file_ids, strategy, allow_cloud_fallback, sensitive}`；`file_ids` 为 32 位十六进制、1–20 个；可选 `Idempotency-Key` 头 | 202 `public(task)`；400 / 413 |
| A5 | GET | `/api/parse/tasks/{id}` | Token | `public(task)`：`task_id,status,mode,cancel_requested,cancel_scope,provider,created_at,completed_at,error,files[]`；`files[]` 含 `sha256, selected_engine, requires_review, fallback_reason, database_parse_id, status, error` |
| A6 | GET | `/api/parse/tasks/{id}/errors` | Token | **仍返回 `public(task)`**，不是独立错误列表 |
| A7 | POST | `/api/parse/tasks/{id}/resume` | Token | `public(task)` |
| A8 | POST | `/api/parse/tasks/{id}/cancel` | Token | `public(task)` |
| A9 | GET | `/api/parse/tasks/{id}/results` | Token | `{task_id, status, results:[{file_id, document}]}`，路径字段已脱敏 |
| A10 | GET | `/api/parse/tasks/{id}/files/{file_id}/artifact` | Token | `FileResponse(artifact.bin)`；仅 `status=completed` 且有 `result_path` 时可用 |

**契约保护点（请勿无通知变更）**：

- A3 是**原始字节流**上传，`multipart/form-data` 会必然触发 415 `file_type_mismatch`；前端第一版用 FormData，是已定位的 P0 缺陷，恢复实施时由前端修正，后端无需改。
- A4 请求体是**白名单校验**，多传 `mode` 等字段会 400；同理前端修正，后端无需改。
- A6 返回的是 `public(task)` 而非错误数组；结构化日志需要新增接口（见 §3 #5）。
- **`artifact.bin` 是 MinerU 解析产物归档，不是原始证据文件**（已核 `mineru_artifacts.py`），不可用于 PDF / Word 预览。

---

## 2. P0 阻塞接口（无此三组，前端无法合规交付）

> 以下为**建议契约**：路径与字段名后端可调整，但必须满足语义与 §4 的验收标准，并在交付时同步更新本表。

### P0-1 · 原始文件读取（最高优先，硬阻塞）

```
GET /api/parse/files/{file_id}/source
Authorization: Bearer <token>
Range: bytes=0-            (可选)
```

**用途**：审核中心 PDF / Word / 图片真实预览、缩略图、原始文件下载。任务书第 9 条明确要求「预览必须通过实际后端文件接口获取文件」，这是唯一合规来源。

| 要求 | 说明 |
|---|---|
| 返回内容 | **上传时的原始字节**，其 SHA256 必须与 A3 返回的 `sha256` 一致；**严禁返回 `artifact.bin` 或任何解析产物** |
| 响应头 | `Content-Type`（按真实后缀）、`Content-Disposition: inline; filename=...`、`Content-Length`、`Accept-Ranges: bytes`、`X-SHA256: <hex>`（或等价元数据接口） |
| Range | 支持 `206 Partial Content`；PDF 大文件按页渲染与缩略图依赖此能力 |
| 鉴权 | 沿用现有 Bearer Token **按 owner 隔离目录**，跨 owner 返回 403/404，不得越权读取 |
| 后缀 | `.pdf / .docx / .png / .jpg / .jpeg`；其它类型返回 415 |
| 错误 | 400 参数非法 / 403 越权 / 404 不存在或已清理 / 410 已归档 / 503 存储不可用 |
| 只读约束 | 该接口只读；不得提供任何改写、覆盖、删除原始文件的入口 |

配套（可选但强烈建议）：`HEAD /api/parse/files/{file_id}/source` 返回同样的元数据而不传输 body，供前端预取页数/大小。

### P0-2 · 文档列表（决定列表能否脱离 DEMO）

```
GET /api/documents?keyword=&doc_type=&status=&date_from=&date_to=&page=1&page_size=20&sort_by=&order=
```

响应契约（分页统一见 §3.3）：

```
{ "list": [{
    "file_id", "file_name", "doc_type", "size_bytes", "sha256",
    "uploaded_at", "status", "latest_task_id", "parse_count"
  }], "total": 1286 }
```

- `status` 枚举需覆盖：`pending / parsing / succeeded / failed / pending_review / reviewed / ingested`（与前端状态色一一对应）。
- `keyword` 匹配文件名；`doc_type` 建议枚举 `pdf / docx / image`；时间范围用 UTC ISO-8601。
- `sha256` 必须是后端 A3 计算并存储的值，前端不自行生成展示值。

### P0-3 · 人工审核读写（决定 4 个写按钮能否解除禁用）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/review/{doc_id}` | 返回原始解析结果、当前人工修订、审计记录列表、`requires_review` 标记 |
| POST | `/api/review/{doc_id}/approve` | 审核通过 |
| POST | `/api/review/{doc_id}/reject` | 退回重新解析（body 含 reason） |
| POST | `/api/review/{doc_id}/mark-error` | 标记识别错误（body 含 page / span / reason） |
| POST | `/api/review/{doc_id}/save-revision` | 保存人工修订（body 含 page / content / base_result_id） |

**不可协商的约束**：

1. `save-revision` **必须新建修订版本**，原始解析结果只追加不覆盖；返回 `revision_id`、`base_result_id`、`version`。
2. 所有写操作留审计：`operator`、`action`、`timestamp`、`before/after` 差异摘要。
3. 审核写入与原始证据文件**物理隔离**，任何审核动作不得修改原始文件字节。
4. 无此接口时，前端 4 个按钮**保持 disabled 并说明原因**，不出现「点击后假装审核成功」。

---

## 3. P1 / P2 接口（决定真实性覆盖范围，可分批交付）

| # | 接口 | 用途 | 关键字段 / 要求 |
|---|---|---|---|
| 3 | `GET /api/documents/{id}` · `GET /api/documents/{id}/parse-history` | 文件详情、解析历史 | 历史含 `task_id, engine, status, started_at, duration_ms, error` |
| 4 | `GET /api/parse/tasks?status=&engine=&page=&page_size=` | 解析任务列表与分页 | 复用 `public(task)` 字段，附 `selected_engine`，任务数口径与统计接口一致 |
| 5 | `GET /api/parse/tasks/{id}/logs` | 结构化任务日志 | `{seq, ts, level, stage, message}`，阶段覆盖 `本地解析 → 质量评估 → MinerU 回退 → 结果标准化` |
| 6 | `GET /api/parse/engines/status` | 三引擎真实状态 | 每项 `{name, state, configured, model_ready, last_error}`；`state ∈ ONLINE/OFFLINE/NOT_CONFIGURED/UNKNOWN/ERROR`；**响应中不得含 API Key** |
| 7 | `GET /api/stats/overview` · `GET /api/stats/trend?days=14` | 首页统一统计与趋势 | 口径见 §3.5；返回文件数、任务数、成功/失败/执行中、待审核、已入库，以及按日趋势与引擎分布 |
| 8 | 入库 5 个：`GET /api/ingestion/batches`、`POST /api/ingestion/precheck`、`POST /api/ingestion/batches`、`GET /api/ingestion/batches/{id}/stages`、`GET /api/ingestion/version-check` | 入库前检查、批次授权、重复批次、阶段状态、kb_version 阻断 | precheck 返回 `kb_version` 一致性与重复批次判定；batches 创建需**幂等键 + 授权**；stages 每阶段返回 `success/fail/duration_ms/error_log`；状态四态 `已完成/执行中/失败/阻塞` |
| 9 | `POST /api/knowledge/search` | 法规检索 | body 支持 `query / keyword / semantic / hybrid` + `kb_version / issuing_authority / effective_only` 筛选；每条命中必须带 `regulation_name, article_no, article_text, issuing_authority, effective_date, expiry_date, kb_version, source_file_id, raw_score`；**无依据时返回空列表 + 原因，禁止返回生成式结论或编造原文** |
| 10 | `GET /api/system/health`、`/resources`、`/api-logs`、`/error-logs`、`/audit-logs` | 系统监控五态与日志 | health 覆盖 FastAPI / PostgreSQL / PaddleOCR / PP-StructureV3 / MinerU API / BGE-M3 共 6 组件，**仅真实探测成功才允许 ONLINE** |
| 11(P2) | 非生产环境启用 `openapi_url` | 后续接口映射可自动生成 | 便于替代「读源码」的映射方式 |

---

## 4. 跨接口统一约定（必须遵守）

1. **鉴权与安全**：统一 `Authorization: Bearer <token>`；按 owner 隔离；任何响应体、响应头、日志均**不得出现 MinerU API Key、数据库口令、Token 本身**。MinerU 云端调用只能由 FastAPI 后端发起。
2. **错误结构**：统一 `{ "code": "<machine_code>", "message": "<可读文案>", "detail": {...} }` + 标准 HTTP 状态码；前端据此映射 400/403/404/410/413/415/503 文案。
3. **分页契约**：所有列表接口统一 `page`（从 1）、`page_size`、`sort_by`、`order`，返回 `{ list, total }`；便于前端 `MrProTable` 一处适配。
4. **时间与枚举**：时间统一 UTC ISO-8601；任务终止态固定 `completed / partial / failed / canceled / timed_out`；组件五态、入库四态见 §3；枚举值变更需同步通知。
5. **统计口径（消除现有矛盾）**：
   - 明确区分「**文件数**」（上传记录）与「**解析任务数**」（任务记录），二者不相加；
   - 恒等式 `成功 + 失败 + 执行中/待处理 = 任务总数`；
   - 所有统计接口使用**同一时间范围**（默认近 14 天）并由 `days` 参数控制；
   - 引擎分布之和必须等于任务总数。
   - 现有 DEMO 中的矛盾（引擎合计 1104 任务 / 1053 成功 / 51 失败，首页却写「成功 1104 / 失败 23」）在真实接口上线后自然消除。
6. **幂等**：所有 POST 写操作支持 `Idempotency-Key` 请求头，重复提交返回首次结果而非重复创建；入库批次额外做重复批次检查。
7. **原始证据不可变**：SHA256 一律由后端计算返回；前端只做重复文件识别提示，不改写任何原始文件；审核修订以追加版本方式保存。
8. **路由决策归属后端**：`selected_engine` / `fallback_reason` / `requires_review` 由后端返回，前端**不自行判断引擎、不默认把所有文档提交 MinerU**。

---

## 5. QA 验收清单（可逐条勾选）

- [ ] P0-1 上传一个 PDF 后请求 `/source`，返回字节的 SHA256 与上传响应 `sha256` **完全一致**，且不是 `artifact.bin`
- [ ] P0-1 `Range: bytes=0-1023` 返回 206 且 `Content-Range` 正确
- [ ] P0-1 换用另一个 owner 的 Token 请求同一 `file_id` 返回 403/404
- [ ] P0-2 六项筛选条件组合查询后 `total` 与 `list.length` 自洽，分页不越界
- [ ] P0-3 `save-revision` 后原始解析结果字节未变，且产生新 `revision_id` 与审计记录
- [ ] 六组件 health 中未配置 MinerU 时状态为 `NOT_CONFIGURED`，不是 `ONLINE`
- [ ] 全部响应体搜索 `api_key / token / password` 无命中
- [ ] 同一 `Idempotency-Key` 重复提交任务 / 批次，只创建一条记录
- [ ] 检索无命中时返回空列表与明确原因，不含任何生成式法条文本
- [ ] 统计接口满足 `成功 + 失败 + 执行中 = 任务总数`，且引擎分布之和等于任务总数
- [ ] `v0.2.1` 正式 QA 验收通过（在此之前前端不得将任何功能标记为正式可用）

---

## 6. 联调交付方式

| 项 | 约定 |
|---|---|
| 后端地址 | `http://127.0.0.1:8180`；前端 Vite dev proxy 将 `/api` 转发至该地址（浏览器不直接持有 MinerU Key） |
| Token | 由后端提供 ≥32 位测试 Token；前端仅内存 + `sessionStorage` 会话级保存，不写 `localStorage`、不打印日志 |
| 接口变更 | 后端每次调整路径 / 字段 / 枚举，需同步更新本表并通知前端；建议启用非生产 `openapi_url` |
| 环境区分 | 开发期 = Vite 代理 + 手工 Token；生产 = 服务端安全会话机制，前端不接触任何密钥 |
| 版本警示 | v0.2.1 未通过正式 QA 期间，前端全局保留版本警示，不标记「正式可用」 |

---

## 7. 前端边界（重申）

恢复实施后，前端**只修改** `frontend/` 目录内文件；不修改 `qa_core/**`、`docs/mineru-integration/**`、`docs/qa/**`、`.venv*`、OCR 离线模型、BGE-M3 模型、`.env`、`requirements*.txt`、`compose*.yaml`；不删除已有业务功能；不自动 commit / merge / push / 部署。

无真实接口的能力，一律保持「只读 + 写操作禁用 + 显著 DEMO 标注」，**不得把 Mock 结果伪装成真实业务数据，不得伪造法律原文，不得假装审核或入库成功**。
