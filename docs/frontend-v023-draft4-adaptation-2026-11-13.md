# v0.2.3 draft-4 前端接入交付（2026-11-13）

状态：**源码适配完成 / 静态与真实浏览器门控验证通过 / 新版本独立 QA 未做（`ADAPTATION_PREPARED / NOT_LIVE_VERIFIED`）**

## 1. 依据与范围

按 Agent C 提交 `e24cbad4238e348844b8951e8977513bfa730761` 接入，依据文件：

| 依据 | 用途 |
|---|---|
| `docs/integration/frontend-v023-draft4-backend-handoff.md` | 接口口径、「前端仍需完成」6 条、错误码与授权边界 |
| `docs/integration/v023-account-role-design.md` | ADMIN 全权限、角色 / 范围 / permissions / data_scope 口径 |
| `docs/integration/frontend-openapi-v023-draft4.json` | 46 路径、请求 / 响应 schema（含 `additionalProperties: false`） |
| `docs/integration/v023-draft4-qa-handoff.md` | QA 范围与禁止继承旧 PASS 的约定 |

本轮**只改前端源码**：未改后端源码、OpenAPI 契约、数据库、ACTIVE 版本、正式角色 / runtime、共享镜像与数据卷；未重启或覆盖 8180 容器，未 Push / Merge main / 打 Tag / 部署生产。

## 2. 运行期基线只读复核（工作前重新核对，不沿用旧记录）

| 交接六项 | 本轮实测 |
|---|---|
| 后端源码 SHA（镜像 OCI revision） | `30c4663ceb93cbba302b322f1ecee0d06d80bfb4` |
| Docker 镜像 ID | `sha256:e2a94f67ffacef9e780e06bc1484cb5e7dde4b287fa5ef340a666f5e573e52a3` |
| 镜像标签 | `market-regulation-workbench:sha-30c4663ceb93cbba302b322f1ecee0d06d80bfb4` |
| 当前运行容器 | `market-regulation-app-1`（healthy） |
| 8180 实际服务身份 | `GET /api/openapi.json` 带凭证 200；`info.version=0.2.2-api-candidate`、**22 路径**、`x-contract-version` 未提供 |
| 镜像内前端 dist 标签 | `cn.market-regulation.frontend.revision=63bbcc07a6b6d12a6be56fa7b0e81731c3917a45` |
| 本轮前端源码提交 | `b99dab9fcdc9fd4db1c8c9e98caa76149d5c63fd` |

**关键结论**：活动 8180 仍是 v0.2.2 冻结镜像，逐项复核 `POST /api/auth/login`、`GET /api/system/capabilities`、`DELETE /api/documents/{file_id}`、`POST /api/ingestion/batches`、`GET /api/system/api-logs`、`GET /api/ingestion/version-check`、`GET /api/auth/me` **全部未声明**。因此本轮所有 draft-4 新能力在默认预览下必须如实呈现「禁用 / 空态」，这既是设计目标，也是本轮浏览器验证的重点。镜像内 dist 是 Agent C 当时的冻结构建，不含本轮改动。

## 3. 逐条对应后端「前端仍需完成」

| # | 后端待办 | 落地 | 本轮结论 |
|---|---|---|---|
| 1 | 账号密码登录表单、管理员账号 / 角色 / 范围 / 停用 / 重置密码页面与审计列表 | 新增 `api/accounts.ts`、`views/AccountsView.vue`；重写 `views/LoginView.vue` 双模式；`AppLayout` 下拉加账号管理入口与登出 | 已在旧实例验证「双模式 + 登录按钮禁用 + 账号页门控空态」；**正向登录与账号 CRUD 未在 draft-4 隔离实例执行** |
| 2 | ADMIN 全权限：去掉「必须含 REVIEWER 才能审核」，依据权限 / 实际方法 / 详情门禁收紧，不从 owner 推断人员 | `principal.ts` 的 `identityBlocksWrite` 改为 `REVIEWER || ADMIN`；`ReviewView` 提交前检查同步；`SystemView` 展示 `permissions` / `data_scope`；全部文案改为「不能从 owner 反推人员」 | 旧实例无 `/api/auth/me`，身份卡如实显示「未确认」，不编造人员与权限 |
| 3 | 入库批次 / 预检 / 发布回滚 / 日志 / 新筛选界面接入；解除硬编码禁用 | `IngestionView` 新增完整写链路卡片；`SearchView` 三个新筛选；`SystemView` 三类运行日志；`ops.ts` 封装 11 个接口 | 页头「发起入库批次」由 `disabled` 硬编码改为运行期方法 + ADMIN + `write_configured` 三重门控；旧实例下全部禁用 / 空态 |
| 4 | 删除门控权限提示 + 成功后真实刷新，403 / 409 / 503 不移除行 | `DocumentsView` 加 `isAdminIdentity` 双重门控、分情况 hint、确认框与注释明确错误态；保留成功后 `list.load()` | 浏览器实测 20 行真实文档、行内删除按钮全部禁用、提示含 403 / 409 / 503 口径 |
| 5 | 审核表格读 `pages[].tables`；列表重试不把终止态一律当不可恢复；首页 days 修改后刷新 | `ReviewView.tableItems` 改读 `original_result.pages[].tables`（旧快照回退顶层）；新增共享 `canRetryStatus()` 供列表与抽屉共用；`DashboardView` 加 `loadedDays` + `watch(days)` 自动重新请求 | 前两项中「审核表格」「首页窗口」浏览器实测通过；**重试解锁分支因真实 15 个任务无 failed / partial / canceled / timed_out 样本，未能浏览器验证**（见 §7） |
| 6 | 用真实运行契约替换「22 路径 / 删除未实现 / 固定版本 SHA」说明；管理员统计注明全局范围 | 全局 14 处文案改为「运行期方法级探测为准」；`config/release.ts` 移除 6 个固定 SHA / 路径数 / 缺口数字段，短标签与告警重写；`AccountsView`、`SystemView` 注明 ADMIN 全局范围 | 浏览器实测页面不再出现「22 路径」字样，短标签为「真实 API · 运行期契约驱动」 |

## 4. 源码改动清单

本轮 23 个前端文件（20 改 + 3 新），`git diff --stat` 已跟踪部分 `+1346 / −193`。

| 层 | 文件 | 要点 |
|---|---|---|
| 契约 / 类型 | `api/types.ts` | draft-4 账号、身份、能力、日志、入库、发布回滚、任务完成度类型；`SearchRequest` 新筛选、`SearchResponse.applied_filters`；`canRetryStatus()` |
| | `api/dataSource.ts` | draft-4 路由常量、方法级门控文案、`MISSING_CAPABILITIES` 重写为「已交付待运行期验证」 |
| | `api/frontend.ts` | `searchKnowledge` 白名单构造请求体，UI 驼峰映射为契约 snake_case（避免 `additionalProperties:false` 触发 422） |
| | `api/errors.ts`、`api/parse.ts`、`api/reviewWrite.ts`、`components/AsyncPanel.vue` | 错误态与状态面板文案改为运行期口径 |
| 新 API 模块 | `api/accounts.ts` | 登录 / 登出 / 角色目录 / 账号 CRUD / 账号事件审计 |
| | `api/ops.ts` | 能力声明缓存（401/403 自动清除）、三类日志、预检 / 批次 / 版本校验 / 发布 / 回滚；`searchFilterEnabled()` 兼容 snake_case 与 camelCase 声明 |
| 身份与会话 | `api/principal.ts`、`stores/app.ts`、`layout/AppLayout.vue`、`router/index.ts` | ADMIN 全权限口径、Bearer 会话、账号管理路由 `/admin/accounts`、登出与身份重确认 |
| 页面 | `views/LoginView.vue`、`views/AccountsView.vue` | 双模式登录、账号列表 / 创建 / 修改 / 停用 / 重置密码 / 事件审计，全部按方法门控 |
| | `views/IngestionView.vue` | 新增 #ingestion-write 卡片：预检、批次创建、批次历史 / 详情、版本校验、发布 / 回滚、回执展示、能力状态表 |
| | `views/SystemView.vue` | 三类运行日志（独立分页、时间区间带时区、level、task_id）、身份权限展示、日志空态 |
| | `views/SearchView.vue` | 三个新筛选按 `search_filters` 能力字段门控、提交时冻结筛选快照、展示 `applied_filters` |
| | `views/DocumentsView.vue`、`views/ReviewView.vue`、`views/ParsingView.vue`、`views/DashboardView.vue` | 删除双重门控、ADMIN 审核口径与 `pages[].tables`、重试规则统一、统计窗口自动刷新 |
| 发布状态 | `config/release.ts` | 移除固定 SHA / 路径数 / 缺口数，短标签与告警改为运行期契约驱动 |

## 5. 门控与写入安全设计

- **运行期方法级门控**：所有 draft-4 能力先经 `hasRuntimeMethod(method, path)` 比对 `GET /api/openapi.json` 实测方法；路径存在不等于方法可用（删除接口即典型）。未声明一律禁用 / 空态，不发请求。
- **三重收紧**：入库写操作额外要求 `isAdminIdentity` 与 `runtimeCapabilities.ingestion.write_configured`；`configured` 不等于数据库健康，最终仍由后端逐请求授权。
- **能力字段门控**：`kb_version` / `issuing_authority` / `effective_status` 仅在 `GET /api/system/capabilities` 的 `search_filters` 声明后可填写并随请求发送，绝不偷偷带上未支持参数；401/403 时能力缓存立即清除，避免沿用上一位登录者的能力。
- **幂等键**：批次与发布 / 回滚必带 `Idempotency-Key`；`outcome_unconfirmed` / 503 / 网络不明沿用同键重试核对回执，仅结果确认后换键；403 / 409 / 503 不本地移除行、不伪造成功。
- **预览写保护**：4173 生产构建预览的默认代理会拦截所有非 GET 请求（`frontend_write_guard`）。写链路需显式把 `VITE_API_PROXY_TARGET` 指向经授权的短生命周期隔离入口才会放行；本轮未做任何写入尝试。

## 6. 验证结果

方法：4173 生产构建预览 + 无头 Edge 157 / CDP 9223，注入容器内既有会话凭证，**只发只读 GET**。脚本 `local/frontend-evidence/draft4-adaptation-check.mjs`，结论 `local/frontend-evidence/screenshots/draft4/draft4-adaptation-verification.json`。

- `npm run typecheck` 退出 0；`npm run build` 退出 0（产物 `IngestionView-df561044.js`、`SystemView-37c44c37.js`、`AccountsView-a82d3c01.js` 等；仅有既存 >500 kB chunk 告警，另作优化）。
- 九页面 / 19 项可验证断言 **19 通过、0 失败**，console 异常 **0 条**。

| 页面 | 实测要点 |
|---|---|
| `/login` | 「账号登录」+「API Token」双模式；密码登录按钮禁用（旧实例未声明 `POST /api/auth/login`） |
| `/admin/accounts` | 创建账号按钮禁用、门控提示真实、ADMIN 全局范围说明 |
| `/system` | 三类日志各显示「运行期未加载该接口，不展示演示记录」；身份卡始终可见且旧实例显示「未确认」；`permissions` / `data_scope` 行存在 |
| `/knowledge/ingestion` | `#ingestion-write` 卡片存在；页头「发起入库批次」、预检、发布、回滚全部禁用；运行期能力状态表 7 行全「未加载」；无「后端明确不支持」旧文案 |
| `/knowledge/search` | 三个新筛选输入框存在且禁用；`applied_filters` 与 draft-4 范围说明可读 |
| `/documents` | 20 行真实文档；行内删除按钮全部禁用；提示含方法 + ADMIN + 403/409/503 口径 |
| `/dashboard` | 「已加载：近 14 天」窗口标签；短标签已更新 |
| `/parsing` | 15 行真实任务、15 个重试按钮（共用 `canRetryStatus` 规则生效） |
| `/review` | 正常渲染、ADMIN 口径文案 |

截图 9 张（`draft4-01-login` … `draft4-07-dashboard`，含入库写入区与运行日志区滚动截图）；截图与 JSON 位于 ignored 的 `local/` 目录，不入库。`git diff --check` 无错误；源码与本文档敏感词 / 绝对路径扫描无命中（仅出现配置变量名，无凭证值、DSN 或机器路径）；未把会话凭证写入源码、报告、截图或 Git。

## 7. 未验证与边界（如实标注，不得据此签发 QA_PASS）

- **7 项隔离联调仍 `NOT_TESTED`**：账号密码正向登录、账号 CRUD / 停用 / 重置密码、审核四动作与多审核员 / 版本冲突 / 撤销、预检与入库批次、发布 / 回滚、删除成功回执、新筛选真实命中，均需在 Agent C 提供的短生命周期隔离实例上由 WorkBuddy / QA 完成。
- **写链路本轮一次都没有执行**：4173 预览的写保护会返回 403，旧 8180 也无这些路由；全部仅验证「未加载即禁用 / 空态」。
- **重试解锁分支未浏览器验证**：真实 15 个解析任务中没有 failed / partial / canceled / timed_out 状态，无法观察「终止态仍可重试」；该行为仅由 `canRetryStatus()` 代码保证，**未使用请求拦截伪造状态**来制造通过。
- 「无筛选 + 后端真实空列表时返回按钮禁用」分支沿用上一轮结论，仍未实测。
- 独立 QA 验收与生产部署未做；public 无 ACTIVE 版本，检索为 `unpublished` 真实空态；不继承任何历史 QA_PASS 作为整版结论。

## 8. 提交与交接

- 分支 `feat/frontend-api-v0.2.2`，**仅本地提交**：源码 `b99dab9fcdc9fd4db1c8c9e98caa76149d5c63fd`，本文件为文档提交（最终前端完整 HEAD 见交付消息 / 工作记忆）。
- 8180 容器内 dist 仍是冻结的 `63bbcc07…` 构建，**前端源码提交不会自动反映到 8180**。
- 请 **Agent C 在构建 v0.2.3 联合候选时带入本轮最新 dist**，并在交接六项中记录文档提交后的最终前端完整 HEAD；QA 报告另记镜像 ID、8180 身份、前端 SHA 与实际验收范围。
- 未经新版本独立 QA 与用户最终部署授权，不注入正式账号 / 写入凭据、不切换 8180、不 Push / Merge / Tag。
