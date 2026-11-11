# v0.2.2 前端真实 API 对接与联调交接报告

> 生成日期：2026-11-11（运行期联调完成后重写）
> 前端分支：`feat/frontend-api-v0.2.2` @ `96d4052`
> 后端契约 / 运行源码：`feat/backend-api-v0.2.2` @ `4fc4cf124a120762593064676ea5f8dbe2394119`
> 契约版本：`frontend-api-v0.2.2-1`
> 上一版结论：`FRONTEND_INTEGRATION_PARTIAL`（见提交 `d60f657`）

---

## 0. 最终结论

```
FRONTEND_INTEGRATION_READY
```

**结论范围（必须连同范围一起引用）**：七个页面的**约定只读能力**已在真实运行服务、真实会话凭证与真实浏览器中完成端到端联调，业务数据全部来自后端真实响应，无任何 Mock/DEMO 回退或伪造响应。此结论**不覆盖**：上传/创建任务/恢复/取消等写链路、正式审核写入与入库发布/回滚、独立 QA 验收、生产部署、MinerU 云端推理与大规模性能验证——这些按用户约束或后端契约明确不在本轮范围，见 §11。

**从 PARTIAL 升级的依据**：用户交付 `docs/integration/v0.2.2-local-runtime-handoff.md` 并确认 8180 已运行最新源码、容器健康。实测两个原阻塞项均已解除：

| 原阻塞项 | 上一轮 | 本轮实测 |
|---|---|---|
| 活动 8180 为 v0.2.1 旧镜像 | 新接口全部 404 | `GET /api/openapi.json` → **200**，`info.version=0.2.2-api-candidate`，**22 个路径**；`/api/documents`、`/api/system/health` 均在列 |
| 无联调 Token | `/api/*` 全 401 | 复用本机私有运行配置（`PARSING_API_TOKENS_JSON`，ignored，owner=`local-user`，长度 43）中的已有会话凭证；仅注入浏览器内存 + sessionStorage，**未写入任何源码、报告或 Git** |

**未做但允许做的事**：没有切换/重建 Docker、没有改后端源码或数据库、没有发布 public ACTIVE、没有自动调用 MinerU 云端、没有 Push / Merge / Tag / 部署。

---

## 1. 基线与事实来源

| 项 | 值 | 说明 |
|---|---|---|
| 前端工作区 | `F:\刘凯工作\market-regulation-platform-frontend` | 独立 Worktree，附带后端副本只读 |
| 前端分支 / HEAD | `feat/frontend-api-v0.2.2` / `96d4052` | 12 个本地 commit，工作区干净，未 Push / 未 Merge |
| 前端维护基线 | `5dd44b97710db0d3bdb84bcec6e1624dd70205dc` | 未使用过时 `main` 开发 |
| 后端仓库 / HEAD | `F:\刘凯工作\market-regulation-platform` / `4fc4cf124a120762593064676ea5f8dbe2394119` | 与 `release.ts` 记录一致 |
| 后端工作区状态 | 5 个 `M` 文件 | 已复核 `git diff --numstat` / `--ignore-cr-at-eol` 为空 → 仅 CRLF 归一化，无契约变化 |
| 活动容器 / 镜像 | `market-regulation-app-1` (healthy) / `market-regulation-workbench:candidate-v022-4fc4cf124a12` | 来自本地运行交接文档，本轮未改动 |
| 联调入口 | `http://127.0.0.1:8180` | 前端经 4173 同源 `/api` 代理转发 |
| 正式契约 | `docs/integration/frontend-api-contract.md` | 契约版本 `frontend-api-v0.2.2-1` |
| 缺口报告 | `docs/integration/frontend-api-gap-report.md` | 后端自评 `BACKEND_API_PARTIAL` |
| 运行交接 | `docs/integration/v0.2.2-local-runtime-handoff.md` | 28 项定向测试通过、9 项真实认证只读冒烟通过 |
| 离线 OpenAPI 快照 | `docs/integration/frontend-openapi.json` | OpenAPI 3.1.0，22 路径 |
| 运行期契约 | `GET /api/openapi.json` | 200，`0.2.2-api-candidate`，22 路径；仍关闭匿名 `/openapi.json`（实测 404） |

---

## 2. 接口映射矩阵（真实调用结果）

> 「未执行」= 写链路，按用户约束不得自动触发；「无数据」= 后端当前真实状态，前端按空态/错误态呈现。

| 页面 | 功能 | 方法 / URL | 实测 | 结论 |
|---|---|---|---|---|
| 全局 | 运行期契约探测 | `GET /api/openapi.json` | 200 · 22 paths | READY |
| 全局 | 旧服务探活 | `GET /api/parse/info` | 200 · `provider=self_hosted, mode=local` | READY |
| 文档管理 | 上传 | `POST /api/parse/files` | 未执行（写） | 按约束不自动上传真实资料 |
| 文档管理 | 文档列表 | `GET /api/documents` | 200 · 4 条 | READY |
| 文档管理 | 详情 | `GET /api/documents/{file_id}` | 200 | READY |
| 文档管理 | 解析历史 | `GET /api/documents/{file_id}/parse-history` | 200 · 1 条，含 `file_mappings` | READY |
| 文档管理/审核 | 原始文件 | `GET /api/parse/files/{file_id}/source` | 200 · 246331 B，PDF | READY |
| 文档管理/审核 | 原始文件 HEAD | `HEAD /api/parse/files/{file_id}/source` | 200 | READY |
| 文档管理/审核 | 原始文件 Range | `GET .../source` + `Range: bytes=0-15` | 206 · `content-range` 正确 | READY |
| 智能解析 | 创建任务 | `POST /api/parse/tasks` | 未执行（写） | 页面保留 `Idempotency-Key` 实现 |
| 智能解析 | 任务列表 | `GET /api/parse/tasks` | 200 · 3 条 | READY |
| 智能解析 | 任务详情 / 失败 | `GET /api/parse/tasks/{task_id}`、`/errors` | 200 / 200 | READY |
| 智能解析 | 恢复 / 取消 | `POST .../resume`、`/cancel` | 未执行（写） | 按约束不改动历史任务 |
| 智能解析 | 结果 | `GET /api/parse/tasks/{task_id}/results` | 200 · 583 KB | READY |
| 智能解析 | 产物归档 | `GET .../files/{file_id}/artifact` | **404**（该历史任务无 artifact.bin） | 前端按错误处理，不伪造下载 |
| 文档审核 | 待复核队列 | `GET /api/review?requires_review=true` | 200 · 7 条，source=`document_review.documents` | READY |
| 文档审核 | 详情与候选对照 | `GET /api/review/{parse_id}` | 200 · 1.2 MB | READY |
| 文档审核 | 已持久化结果预览 | `POST /api/review/{parse_id}/preview` | 200 · `write_performed=false` | READY |
| 入库管理 | 任务文件 Chunk 预览 | `POST /api/parse/tasks/{t}/files/{f}/preview` | 200 · `write_performed=false` | READY |
| 入库管理 | 版本列表 | `GET /api/knowledge/versions` | 200 · 空列表，source=`public.mr_kb_versions` | READY（空态） |
| 入库管理 | 版本详情 | `GET /api/knowledge/versions/{version}` | 404 `version_not_found` | 错误态 READY；成功态因无版本记录未覆盖 |
| 法规检索 | 查询 | `POST /api/knowledge/search` | 200 · keyword 与 hybrid 均 `status=unpublished, count=0` | READY |
| 首页 | 统计 | `GET /api/stats/overview?days=14` | 200 · 分来源统计 | READY |
| 系统监控 | 健康 | `GET /api/system/health` | 200 · 五态真实 | READY |

**统计真实值（禁止相加）**：`uploads=4`（全量上传元数据）、`tasks=3`（近 14 天 SQLite，`status_distribution.completed=3`）、`parsed_documents.total=7` / `requires_review=7`（document_review 全历史，`available=true`）。

**健康真实值**：`fastapi/task_store/postgresql = ONLINE`（`request_handled` / `read_only_query`）；`paddle_ocr/pp_structure/bge_m3 = UNKNOWN`（`files_only_no_inference`，`model_ready=true` 仅表示文件存在）；`mineru = UNKNOWN`（`configuration_only_no_request`，未发起云请求）。

---

## 3. 浏览器联调方法与证据

| 项 | 实现 |
|---|---|
| 浏览器 | Microsoft Edge 157 headless，CDP `127.0.0.1:9222`（本机已有签名程序，无新增依赖） |
| 前端服务 | `npm run preview -- --host 127.0.0.1 --port 4173 --strictPort`；`vite.config.ts` 的 `server.proxy` 与 `preview.proxy` 均转发 `/api` |
| 代理验证 | 经 4173 的 `/api/parse/info` 无认证返回 **401**，与直连 8180 完全一致；带认证后所有页面接口 **200** |
| 认证方式 | 在真实登录页输入会话凭证并点击「验证并进入」→ `saveToken()` → `probeBackend()` + `probeContract(true)` → 跳转 `/dashboard`；未直接调用内部 API 绕过登录 |
| 缓存 | `Network.setCacheDisabled(true)`，确保加载最新构建产物 |
| 视口 | 1440×900 七页面全量；1366×768（dashboard/review）、1920×1080（system）响应式抽查；三者 `scrollWidth === clientWidth`，无横向溢出 |
| 采集 | CDP `Network.responseReceived` / `loadingFailed`、`Runtime.exceptionThrown`、`Log.entryAdded`、DOM `innerText`、按钮禁用态、`Page.captureScreenshot` |
| 截图 | `C:\Users\aa\AppData\Local\Temp\mrp-screenshots\final\`（七页面 + 初始/结果检索 + 1366/1920 抽查），仅本机证据，不入库 |

**最终七页面扫描结果（1440×900）**：全部 `label=v0.2.2 运行期联调通过 · 只读`、旧标签 `待运行期联调` 已消失、`契约就绪` = true、`errors=[]`、`apiFails=[]`。

---

## 4. 逐页联调结果

| 页面 | 真实接口 | 渲染的真实数据 | 关键交互验证 | 控制台 / API 失败 |
|---|---|---|---|---|
| 首页工作台 `/dashboard` | stats/overview、system/health | 4 张卡 `4 / 3 / 7 / 7`，`created_daily` 与 `engine_file_selections` 真实图表 | 统计窗口切换、刷新统计 | 0 / 0 |
| 文档管理 `/documents` | documents、详情、parse-history、source | 4 行真实文件、SHA256 后端值、`uploaded_at_source=metadata_mtime` 明确标注 | 打开详情抽屉（详情 + 1 条解析历史）、下载原件 `/source` 200 | 0 / 0 |
| 智能解析 `/parsing` | parse/tasks、详情、results、errors、health | 3 条任务、真实 `native` 引擎与回退原因、无模拟进度 | 任务详情抽屉、标准化结果、错误原因、产物下载 404 错误态 | 0 / 0 |
| 文档审核 `/review` | review、详情、source | 7 条待复核队列、1.2 MB 详情含 `original_result.pages[10]`、Markdown/JSON/表格纯文本 | 点击队列首行 → 详情 200 + 原件 `/source` 200 + iframe 预览；四个写按钮全部 `disabled` | 0 / 0 |
| 入库管理 `/knowledge/ingestion` | knowledge/versions、两类 preview | 版本列表真实空态、Chunk `chunks(1)/parents(1)/tables(0)/warnings(2)`、`write_performed=false` | 回填路由参数 → 两类预览分别 200；发起入库批次禁用 | 0 / 0 |
| 法规检索 `/knowledge/search` | knowledge/search | 初始「尚未发起检索」；检索后 `unpublished / kb_version — / 命中 0 / 来源 public` | keyword 与 hybrid 两种模式各发起一次真实检索 | 0 / 0 |
| 系统监控 `/system` | system/health、openapi.json、parse/info | 七组件五态、39 行接口能力清单、契约就绪标签 | 重新探测、Token 会话配置说明 | 0 / 0 |

**审核写操作实测**：`审核通过 / 退回重新解析 / 标记识别错误 / 保存人工修订` 四个按钮 DOM 均为 `disabled`；后端 `review_write_supported=false`，页面无任何本地状态变更或假成功提示。

**原件身份实测**：`GET /source` 返回 `x-sha256: d9e8da75…`（64 hex）、`content-disposition: inline; filename*=utf-8''…`、`content-security-policy: sandbox`、`accept-ranges: bytes`；前端 `DocumentPreview.vue` 走认证 ArrayBuffer → Blob URL → 浏览器内置 PDF viewer，未把 `artifact.bin` 当原件。

---

## 5. 状态、空态与错误态验证

| 场景 | 触发 | 实测 | 页面表现 |
|---|---|---|---|
| 未认证 | 清除 sessionStorage Token 后刷新 `/documents` | 页面**零业务 API 请求** | `AsyncPanel` 显示「未认证 / 无权限」+ 配置重试 |
| 401 | 无 Token 直连 `/api/documents` | 401 `unauthorized` | 请求层归一化为 `no-permission` |
| 404 对象不存在 | 不存在 `file_id` / `parse_id` / 版本 | 404 `source_not_found` / `document_not_found` / `version_not_found` | `not-found`，不回退演示数据 |
| 404 产物缺失 | 历史任务 `artifact.bin` | 404 | 「解析产物下载失败」错误提示，不假装下载成功 |
| 422 参数非法 | `page=0&page_size=999`、`days=999`、非法 `document_type`、请求体附加字段 | 422 `invalid_request` | `invalid` 错误态 |
| 416 Range 越界 | `Range: bytes=99999999-…` | 416 | `limit` 错误态 |
| 200 空列表 | `keyword=__no_such_file__`、非法 status 筛选、`/api/knowledge/versions` | 200 `list:[]` | 正常空态，不显示 0 冒充统计、不伪造法条 |
| 服务未发布 | `POST /api/knowledge/search` | 200 `status=unpublished` | 「知识库尚未发布」而非「未检索到相关依据」 |
| 契约未就绪（回归） | 旧镜像时期的探测逻辑 | — | `outdated` 态保留；本轮服务已就绪，未触发 |

> `409 / 413 / 415 / 429 / 503` 的真实触发需要构造幂等冲突、超限文件或模型并发，可能改动业务数据或触发远程动作，本轮未执行；前端 `ApiError` 已按契约归一化这些状态码。

---

## 6. 契约字段一致性核对

以真实 200 响应逐字段比对 `src/api/types.ts`，全部吻合：

- `DocumentInfo`：`file_id/file_name/doc_type/size_bytes/sha256/uploaded_at/uploaded_at_source/status/latest_task_id/parse_count` ✓
- `ParseHistoryItem`：`task/file_id/source_file_id/database_parse_id/elapsed_seconds` ✓（任务文件 ID 与上传 ID 明确分离）
- `TaskSummary` / `ParseTask`：`files[].selected_engine/requires_review/fallback_reason`、`file_mappings`、`elapsed_seconds` ✓
- `ReviewDetail`：顶层含 `source_file_id`、`task_id`、`local_candidate_available=true`、`review_write_supported=false`、`original_result.pages[10]`、`source_location.source_file_id` ✓
- `PreviewResponse`：`preview` + `write_performed=false`、`preview.rag_index_written=false` ✓
- `SearchResponse`：`status/kb_version/mode/list/count/source` ✓
- `StatsResponse`：`window{since,until}`、三组 `source/scope` 分离、`available/total/requires_review` ✓
- `HealthResponse`：`status=ok` + `components[7].{state,check,model_ready?,configured?}` ✓
- `RuntimeOpenApi`：`openapi/info/paths`，`info.version=0.2.2-api-candidate` ✓

结论：前端未调用任何契约外路径，未拼接推导 ID，未对 `uploads/tasks/parsed_documents` 做相加。

---

## 7. 联调发现并修正的问题

| # | 问题 | 修正 | 文件 |
|---|---|---|---|
| 1 | 检索页未发起检索时误写「未检索到相关依据（后端返回空列表）」，暗示已查过后端 | 新增 `emptyDescription` 计算属性，区分「尚未发起检索 / 尚未发布 / 后端返回空列表」三种状态；按钮文案随状态切换 | `SearchView.vue` |
| 2 | 直接刷新检索页时契约标签停在「未探测」（该页不自动发起检索） | `onMounted` 在契约状态为 `unknown` 时主动 `probeContract()`，只探测、不发起检索 | `SearchView.vue` |
| 3 | 登录页仍保留过时 DEMO 话术（2 处） | 改为「业务数据均来自真实接口，未就绪时显示异常态」；后端离线提示不再引导查看 DEMO | `LoginView.vue` |
| 4 | 浏览器自动请求 `/favicon.ico` 产生非业务 404 日志 | `index.html` 显式声明空图标 | `index.html` |
| 5 | 发布状态仍写「待运行期联调」、标签为 warning | `releaseStatus.frontendIntegrated=true`、`shortLabel` 改为「v0.2.2 运行期联调通过 · 只读」、补充运行期镜像/契约事实；三处状态标签改 `success` | `release.ts`、`AppLayout.vue`、`DashboardView.vue`、`SystemView.vue` |

修正后复验：检索页初始态 `尚未发起检索` 出现 2 次（页头 + 空态标题）、无「后端返回空列表」、契约就绪、0 控制台错误；七页面发布标签全部更新。

---

## 8. 统一请求层与异常体系（保持不变）

- 全站唯一 Axios 实例 `src/api/client.ts`，`baseURL='/'`，Bearer Token 内存优先 + sessionStorage，清理历史 localStorage 值，敏感词掩码。
- `ApiError` 归一化 401/403/404/409/413/415/416/422/429/500/502/503/504、取消与超时；新接口 404 识别为 `outdated`（旧镜像）而非「对象不存在」。
- `useAsyncData` 统一契约探测、`AbortSignal` 取消、页面卸载中止；`AsyncPanel` 统一 Loading / Empty / Error / Retry / No Permission / Service Unavailable / Outdated。
- `MrProTable` 受控模式，页面负责真实 API 调用；创建任务强制 `Idempotency-Key`；解析中心 2s 轮询在终止态与卸载时停止。
- `vite.config.ts` 的 `server.proxy` 与 `preview.proxy` 均支持 `VITE_API_PROXY_TARGET` 覆盖，生产构建产物不含本地地址。

---

## 9. 真实性治理结果

- 七个页面**零 `api/mock` / `DemoBadge` 引用、零实际 `v-html`**；`src/api/mock/**` 仅作为不被引用的历史隔离模块保留，不参与任何页面数据流。
- 审核 4 个写操作、正式入库批次 / 发布 / 回滚保持禁用；无「已记入待办」等假成功。
- 检索只渲染后端 `article_text`，无伪造法条；public 无 ACTIVE 时显示 `unpublished`。
- 统计按来源分开展示，`available=false` / `null` 显示「暂无数据」而非 0；健康五态只按后端 `state` 归一化，不把模型文件存在误标为推理 ONLINE。
- 生产 `dist/` 无硬编码 `127.0.0.1:8180`，无过时 DEMO 文案；`git ls-files` 无 `node_modules` / `dist` / `.env` / 数据库 / 日志 / 模型 / Token 文件。

---

## 10. 缺失接口清单（反馈后端 / Codex Fix）

以下能力在 v0.2.2 契约中「明确不支持」，前端一律禁用或空态，**不是前端未完成项**：

| 组 | 缺失接口 | 前端处理 |
|---|---|---|
| 1 | `POST /api/review/{parse_id}/approve` | 审核通过按钮禁用 |
| 2 | `POST /api/review/{parse_id}/reject` | 退回重新解析禁用 |
| 3 | `POST /api/review/{parse_id}/mark-error` | 标记识别错误禁用 |
| 4 | `POST /api/review/{parse_id}/save-revision` | 保存人工修订禁用 |
| 5 | `POST /api/ingestion/batches` + `precheck` + `version-check` | 发起入库批次禁用 |
| 6 | `POST /api/ingestion/publish`、`/rollback` | 不开放发布 / 回滚 |
| 7 | 结构化引擎运行日志 `/logs` | 日志抽屉只展示后端 `public(task)` 真实字段 |
| 8 | 资源监控、审计/操作日志 | 系统页不展示伪造指标与日志 |

后端补齐并通过契约验收、且保留原始解析结果与审计留痕后，方可逐项解除禁用。

---

## 11. 未验证 / 不在本轮范围（如实列出）

1. **写链路未执行**：上传 `POST /api/parse/files`、创建任务 `POST /api/parse/tasks`、`resume` / `cancel`。用户约束「不自动上传真实资料、不修改正式 ACTIVE 或历史任务」，且运行交接要求先在合成数据/隔离对象验证写链路；页面实现与 `Idempotency-Key` 已就绪，但未在真实 8180 触发。
2. **`GET /api/knowledge/versions/{version}` 成功态未覆盖**：public 当前无版本记录，只验证了 404 `version_not_found`；版本列表为空是后端真实状态。
3. **有法条命中的检索结果未覆盖**：public 无 ACTIVE 版本，`status=unpublished`、`count=0`；前端 `SearchHit` 渲染分支只做了静态契约核对，未用真实命中数据渲染。
4. **409 / 413 / 415 / 429 / 503 真实触发**：见 §5 说明，仅验证请求层归一化逻辑。
5. **独立 QA 验收、跨 owner 隔离的对抗测试、production 部署、MinerU 云端推理、大规模分页性能**：均不在本轮；后端交接文档自评仍为 `BACKEND_API_PARTIAL`，并明确未达到合并 main 的门禁。
6. **PDF 逐页渲染 / Word 转换**：PDF 使用浏览器内置 viewer（iframe + `#page&zoom`），图片用 `<img>`，DOCX 按 `attachment` 契约只提供授权下载；未引入 `pdfjs-dist` / `@vue-office/docx`，不做 Word→PDF 转换。
7. **回滚演练**：运行交接明确「回滚分支已准备但未实际演练」，与本轮前端结论无关，不由前端代为宣称。

---

## 12. 安全与合规

- Token 仅内存 + sessionStorage，不写 localStorage；错误文案对 `token/api_key/password/secret/bearer/dsn/postgres` 等掩码；浏览器不接触 MinerU Key、PG DSN 或私有 `.env`。
- 联调凭证来自本机 ignored 私有运行配置，未写入源码、报告、截图或 Git；提交前 `git diff` 敏感词扫描通过（`96d4052`）。
- 所有请求同源 `/api`，不硬编码后端地址；原始文件按 owner 隔离，跨用户 / 不存在返回 404。
- Markdown / 表格 / JSON 等不可信内容按纯文本 `<pre>` 展示，不执行 HTML / 脚本；Blob URL 在切换与卸载时撤销。
- 未 Push、未 Merge main、未打 Tag、未部署生产、未切换 Docker、未改后端源码 / 数据库 / 模型 / OCR 流程。

---

## 13. 提交清单（`5dd44b9..96d4052`，12 个本地 commit）

| Commit | 内容 |
|---|---|
| `c23f011` | 归档 v0.2.1 前端基线，建立 v0.2.2 联调起点 |
| `18e2f28` | 统一 Axios 请求层、`ApiError`、类型契约、运行期探测、`AsyncPanel` / `useAsyncData`、`/source` 适配 |
| `cf1d3d1` | 文档管理真实接口对接 |
| `d87b3a5` | 智能解析中心真实接口对接 |
| `614d537` | 文档审核中心（只读）真实接口对接 |
| `7b8fe74` | 知识库入库中心（预览与版本只读） |
| `15e40a1` | 法规检索真实接口对接 |
| `c8bad73` | 首页统计与系统健康接入 |
| `cf28557` | 系统监控五态与运行期契约总览 |
| `6ecb2ae` | 补齐 `preview.proxy`、校准发布状态文案 |
| `d60f657` | 上一版 `FRONTEND_INTEGRATION_PARTIAL` 报告 |
| `96d4052` | **运行期联调后更新发布状态、修正检索初始态与过时 DEMO 文案** |

---

## 14. 交付物

| 文件 | 说明 |
|---|---|
| `frontend/docs/frontend-api-integration-report.md` | 本报告（最终 READY 版） |
| `frontend/docs/frontend-api-mapping-v0.2.2.md` | 接口映射矩阵，§5 已同步为 READY 结论 |
| `frontend/docs/frontend-api-mapping.md`、`backend-api-requirements.md`、`frontend-optimization-report.md`、`frontend-api-integration-update-2026-11-11.md` | 历史轮次文档，保留作为决策记录 |
| `frontend/src/**` | 七页面 + 唯一请求层 + 共享组件 + 类型契约（工作区干净） |
| 浏览器截图 | 本机临时目录，仅供本轮验收复核，不入库 |

---

## 15. 状态标记与后续建议

```
FRONTEND_INTEGRATION_READY
```

**建议的后续顺序（均需用户/QA 另行授权，本轮未执行）**：

1. 独立 QA 绑定后端 `4fc4cf1` 与前端 `96d4052`，按交接文档 §QA 重点验证认证/跨 owner、原件 Hash/Range、任务恢复、源文件身份映射、PG `requires_review`、候选对照、Chunk 门禁、public 空知识库与真实统计。
2. 在隔离合成对象上补做写链路（上传 → 创建任务 → 结果 → 审核写入候选）与 409/413/415/429/503 触发测试；不触碰正式 ACTIVE 与历史任务。
3. public 知识库按既有授权流程发布 ACTIVE 版本后，复验检索命中态与版本详情成功态。
4. 后端补齐 §10 的 8 组接口并通过契约验收后，再逐项解除前端禁用；每解除一项需单独提交与验收。
5. 合并 main 前按后端门禁单独评审；本报告不代表 QA PASS 或生产可用。

> 提醒：`releaseStatus.shortLabel` 是本次构建的静态联调结论；运行期能力仍以页面上的 `GET /api/openapi.json` 契约探测标签为准。若服务回退到旧镜像，页面会显示 `后端服务未加载 v0.2.2 契约` 异常态，不会回退 DEMO。
