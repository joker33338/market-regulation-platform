# v0.2.3 前端适配准备说明（审核台账 · MySQL）

> 日期：2026-11-12　状态：**ADAPTATION_PREPARED / NOT_LIVE_VERIFIED**
> 前端业务源码提交：`3b7b62f6373509ee5da2bbccb89bca67e54583ee`（原分支 `feat/frontend-api-v0.2.2`，仅本地提交）
> 依据：后端交接《MySQL 审核台账批次》+ `docs/integration/frontend-openapi-v023.json`（`0.2.3-dev`、`frontend-api-v0.2.3-draft-1`、29 路径）+ 8180 运行契约实测。
> 本轮只改前端；未改后端源码、数据库、Docker 镜像、正式 8180 容器、数据卷，未 Push / Merge / 部署，未宣称 QA PASS。

## 0. 一句话结论

前端已按 v0.2.3 离线契约完成**能力探测式适配**：新增 7 条接口的请求层、审核中心四个写操作的真实交互、系统监控的资源/审计面板、文档高级筛选与统计不可用原因。但**正式 8180 仍是 `0.2.2-api-candidate` / 22 路径**，运行期探测不通过，因此所有新增能力保持禁用或空态，**写按钮没有提前解锁**；新接口在真实服务上的联验尚未执行。

## 1. 依据与实测身份

| 项 | 实测 |
|---|---|
| 后端源码 | 主目录 `codex/backend-improvements-v023 @ 4395c2e…`，四个交接提交均存在（审核台账 / 文档筛选 / 审计日志 / 修订正文完整性） |
| 离线契约 | `docs/integration/frontend-openapi-v023.json`，`info.version=0.2.3-dev`，`x-contract-version=frontend-api-v0.2.3-draft-1`，**29 路径**，`HTTPBearer` |
| 运行期契约 | 8180 带凭证 `GET /api/openapi.json` → 200 / `0.2.2-api-candidate` / **22 路径**；`/approve`、`/events`、`/system/resources`、`/system/audit-logs` 均不存在 |
| 正式容器 | `market-regulation-app-1` healthy；Vue 入口与 `/api` 同源；未做任何变更 |
| 契约认证 | `Authorization: Bearer <会话凭证>`；Token→owner 映射决定操作者，客户端不传 `operator` |

源码分支已交付 ≠ 运行期可用，这是本轮全部设计的出发点。

## 2. 双门控（写按钮唯一判定依据）

审核中心四个写按钮由 `ReviewView.vue` 的 `canWrite` 决定，两道门必须**同时**通过：

| 门 | 判定 | 数据来源 |
|---|---|---|
| ① 运行期契约 | `hasV023ReviewWriteRoutes()`：运行期 OpenAPI 路径集合同时包含 4 条写路径，且契约状态 `ready` | `dataSource.runtimePaths` ← 每次 `probeContract()` 的真实响应 |
| ② 审核详情 | `review_write_supported === true` **且** `review_ledger.available === true` | `GET /api/review/{parse_id}` 的真实响应；`requires_review` 只是 OCR 复核信号，不参与判定 |

任一不通过 → 按钮 `disabled`，并显示对应原因（契约未加载 / 台账不可用或当前 owner 未获写授权）。当前 8180 上第 ① 门必然不通过。

页面三态标签：`审核写入未启用 · 运行期契约未加载 v0.2.3` → `审核写入未解锁 · 台账或写授权未就绪` → `审核写入已启用 · 真实台账`。

## 3. 修改文件清单

| 文件 | 改动 |
|---|---|
| `src/api/reviewWrite.ts`（新增） | 7 条新接口封装：`approve/reject/mark-error/save-revision`、`events`、`resources`、`audit-logs`；`Idempotency-Key` 生成与沿用；不传契约外字段 |
| `src/api/types.ts` | 新增 `ReviewLedger / ReviewActionBody / ReviewReceipt / ReviewEvent / ProcessResources / AuditLogItem / AuditAction`；`ReviewDetail.review_ledger`、`DocumentQuery` 的 v0.2.3 参数、`StatsResponse.parsed_documents.reason` |
| `src/api/dataSource.ts` | 保存运行期路径集合 `runtimePaths`；`hasRuntimeRoutes()` 及 4 个能力判定；`CONTRACT_ROUTES_V023`（7 行）；纠正「明确不支持」清单文案 |
| `src/api/frontend.ts` | `listDocuments` 追加 `date_from/date_to/sort_by/order`，未确认能力时保持 `undefined`（不发送） |
| `src/views/ReviewView.vue` | 双门控、四写按钮确认弹窗与真实提交、版本锁、幂等键、409/403/401/422/503 分类提示、回执与台账事件页、修订正文纯文本渲染 |
| `src/views/SystemView.vue` | v0.2.3 契约页签（逐行运行期标注）、API 进程资源、审核审计摘要（均能力门控） |
| `src/views/DocumentsView.vue` | 日期闭区间（自动转带时区 ISO）、白名单排序筛选条（能力门控）；纠正「后端不支持」旧文案 |
| `src/views/DashboardView.vue` | `parsed_documents` 不可用时展示后端真实 `reason`，不做 0 填充 |
| `src/config/release.ts` | 文案口径改为「当前运行期契约」 |

**写入交互细节**：每次打开弹窗生成一个 `Idempotency-Key`，失败重试沿用同键同 body（避免自造同键异请求 409）；409 时刷新详情并换新键；`base_result_id` 恒等于路径 `parse_id`，`expected_version` 取详情 `review_ledger.version`；修订正文不做 `trim`，保留前导空格与换行；成功与否只认后端回执 `write_performed === true`，随后刷新详情与事件；回执中的 `original_result_modified / publish_authorized / reparse_task_created` 如实展示，不暗示已发布或已创建任务。

## 4. 真实 API 映射（本轮新增对接）

| 方法 / 路径 | 页面 | 关键字段 |
|---|---|---|
| `POST /api/review/{parse_id}/approve` | 审核中心 | `Idempotency-Key` + `base_result_id`、`expected_version`；`reason` 可选 |
| `POST /api/review/{parse_id}/reject` | 审核中心 | 必填 `reason` |
| `POST /api/review/{parse_id}/mark-error` | 审核中心 | 必填 `reason`、`page`；可选 `span` |
| `POST /api/review/{parse_id}/save-revision` | 审核中心 | 必填 `page`、`content`（原样提交） |
| `GET /api/review/{parse_id}/events` | 审核中心「审核台账」页 | `page` / `page_size`；owner 隔离 |
| `GET /api/system/resources` | 系统监控 | `scope=api_process`；`available=false` 时展示 `reason` 与 null 指标 |
| `GET /api/system/audit-logs` | 系统监控 | `page` / `page_size` / `action`；仅摘要，不含修订正文 |
| `GET /api/documents`（扩展） | 文档管理 | `date_from/date_to`（含时区闭区间）、`sort_by` 白名单、`order` |
| `GET /api/stats/overview`（扩展） | 首页 | `parsed_documents.reason` |

检索页 **未**新增筛选器：后端明确 `SearchRequest` 仍只允许 `query/mode/limit`，多传字段会 422，前端不静默忽略也不伪造筛选。

## 5. 验证结果

| 项 | 结果 |
|---|---|
| `npm run typecheck` | 退出 0 |
| `npm run build` | 退出 0；产物 `index-ead71bdb.js`（仅有既有 chunk >500 kB 体积告警） |
| 浏览器回归 | 有头 Edge + CDP，1440×1200，4173 独立预览（`/api` 代理转发 8180），真实登录会话，七页面逐个巡检 + 审核详情 + 系统页 v0.2.3 页签 |
| 审核页 | 四按钮 `disabled=true ×4`；门控标签「未启用 · 运行期契约未加载 v0.2.3」；无「审核台账」页签、无写入弹窗、无台账元数据 |
| 系统页 | v0.2.3 页签 7 行、8 处「未加载」、0 处「已加载」；资源与审计卡片未渲染；旧空态保留 |
| 文档 / 首页 | 高级筛选条未渲染；统计卡片真实加载，未把不可用显示为 0 |
| 网络与错误 | **新增 7 条接口调用 0 次**（未向不存在的接口发请求）；JS 异常 0、Log error 0；9 张截图 + 逐张 SHA256 在 ignored 证据索引 `v023_adaptation_evidence` |

**如实说明的失败尝试**：为验证门控会随运行期契约正向翻转，尝试在浏览器内注入合成路径 / 拦截 `openapi.json` 响应；打包后模块导出被压缩无法定位响应式 ref，Fetch 拦截后页面停在「未探测」，**未得到稳定正向结论，记为「未验证」，不作为证据**。门控的响应式依赖由源码审阅确认；正向联验必须等真实 v0.2.3 服务与台账就绪后由 QA 执行。

## 6. 未完成 / 待联验 / 风险

- **未与真实 v0.2.3 服务联验**：4 个写接口、事件、资源、审计日志、文档新参数均未在运行服务上实际调用；不宣称写入闭环 PASS。
- **审核台账需管理员初始化**：正式运行默认无 `REVIEW_MYSQL_CONFIG_JSON`，后端会 503；`writers` 名单与 Docker 网络 host 需管理员配置，前端不做任何配置代劳。
- 入库批次 / 发布回滚、任务阶段日志、API/错误日志、`total_steps` 进度、模型真实探活、检索三项筛选、首页新增指标 —— 后端本批未交付，前端保持禁用或空态，清单交 Agent C。
- 8181 历史容器仍保留作回滚，不作为入口。
- 写链路浏览器点击验收（上传 → 创建任务 → 真实 OCR → 审核写入 → 事件留痕）仍待隔离实例授权，未执行。

## 7. 交接

- **Agent C**：按后端交接 §4 走「候选镜像 → 挂载与回滚验证 → 单独批准切换 8180」；切换后前端 `probeContract()` 会读到 29 路径，第 ① 门自动通过；**不要**为验证一句文案或前端门控单独重启正式容器。C-2 项（前端 dist 固化在镜像内）仍待镜像更新，8180 目前显示的是旧产物。
- **QA**：请以真实 v0.2.3 实例单独验收 ① 只有 `review_write_supported=true` 且台账可用时按钮才启用；② 409 并发/源变更、403 未授权、422 缺字段、503 未配置各态；③ 幂等键同键同请求返回原回执、同键异请求 409；④ 事件追加与修订正文不被篡改、原始解析结果不变；⑤ `publish_authorized=false` 与 `reparse_task_created=false` 在页面如实呈现。
- **状态**：`ADAPTATION_PREPARED / NOT_LIVE_VERIFIED`，不是 `READY_FOR_FINAL_QA`，更不是 v0.2.3 前端正式交付完成。

## 8. 边界

后端源码、数据库结构与数据、正式镜像、8180 容器、数据卷、ACTIVE 版本、PostgreSQL 记录、已通过的 QA 历史报告均未改动；Token 只在内存 + `sessionStorage`，未硬编码、未打印、未入库；未 Push / Merge main / 打 Tag / 部署。
