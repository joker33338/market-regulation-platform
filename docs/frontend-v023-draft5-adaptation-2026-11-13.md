# v0.2.3 draft-5 前端接入交付（2026-11-13）

状态：**源码适配完成 / 运行期门控与真实浏览器验证通过 / 新版本独立 QA 未做（`ADAPTATION_PREPARED / NOT_LIVE_VERIFIED`）**

## 1. 依据与范围

按 Agent C 在 `codex/backend-improvements-v023` 分支的最新提交接入：

| 依据 | 说明 |
|---|---|
| `docs/integration/v023-postgresql-law-case-audit.md` | §F.6 明确「前端可按 draft-5 开发两个只读入口和合法空态；当前 8180 尚无新接口，不能宣称已正式可连接或整版上线」 |
| `docs/integration/frontend-openapi-v023-draft5.json` | 54 路径 / `frontend-api-v0.2.3-draft-5`，8 个 `/api/library/*` GET 的参数与响应 schema |
| `docs/integration/v023-pg-library-original-catalog.md` | 原结构目录（仅作背景，前端不依赖） |
| `frontend-openapi-v023-draft4.json`（上一轮） | 用于核对增量差异 |

**契约差异（只读比对结论）**：46 → 54 是**纯增量 8 条 GET**，无删除、无既有路径的方法变更。新增路径：

| 路径 | 用途 |
|---|---|
| `GET /api/library/laws` | 法规列表（query / kb_version / 分页） |
| `GET /api/library/laws/{doc_version_id}` | 法规版本详情、OCR 原文、原件入口 |
| `GET /api/library/laws/{doc_version_id}/chapters` | 章节（分页） |
| `GET /api/library/laws/{doc_version_id}/articles` | 条款（分页） |
| `GET /api/library/laws/{doc_version_id}/articles/{article_id}` | 条款正文与字符范围 |
| `GET /api/library/cases` | 案例列表（query / violation / kb_version / 分页） |
| `GET /api/library/cases/{doc_version_id}` | 案例详情与结构化字段 |
| `GET /api/library/cases/{doc_version_id}/references` | 处罚依据引用（分页） |

`CapabilitiesResponse` 在 draft-5 **未新增 library 字段**（只把 `contract_version` 改为 `frontend-api-v0.2.3-draft-5`），因此两个新页面的可用性判定**只能依赖 `GET /api/openapi.json` 的方法级门控**，不能读能力声明，也不能写死路径数或版本 SHA。

本轮**只改前端源码**：未改后端源码、OpenAPI 契约、数据库、ACTIVE 版本、正式角色 / runtime、共享镜像与数据卷；未重启或覆盖 8180 容器；未 Push / Merge main / 打 Tag / 部署生产。

## 2. 运行期基线只读复核（工作前重新核对，不沿用旧记录）

| 交接六项 | 本轮实测 |
|---|---|
| 后端源码 SHA（镜像 OCI revision） | `30c4663ceb93cbba302b322f1ecee0d06d80bfb4` |
| Docker 镜像 ID | `sha256:e2a94f67ffacef9e780e06bc1484cb5e7dde4b287fa5ef340a666f5e573e52a3` |
| 镜像标签 | `market-regulation-workbench:sha-30c4663ceb93cbba302b322f1ecee0d06d80bfb4` |
| 当前运行容器 | `market-regulation-app-1`（healthy，StartedAt `2026-11-13T00:24:00Z`）；容器 `.Image` 与上述镜像 ID 一致 |
| 8180 实际服务身份 | 带凭证 `GET /api/openapi.json` = 200 / `info.version=0.2.2-api-candidate` / **22 路径** / 无 `x-contract-version` |
| 镜像内前端 dist 标签 | `cn.market-regulation.frontend.revision=63bbcc07a6b6d12a6be56fa7b0e81731c3917a45`（冻结构建，不含本轮改动） |

**逐条门控证据**（容器内带凭证的只读 GET，凭证未出容器、未落盘、未写入任何产物）：

```
GET /api/library/laws        -> 404
GET /api/library/cases       -> 404
GET /api/system/capabilities -> 404
```

**关键结论**：活动 8180 仍是 v0.2.2 冻结镜像，8 条 library 路由一条都没有加载。因此本轮两个新页面在默认预览下必须如实呈现「运行期未加载该接口 → 禁用 / 合法空态」，**不发请求、不摆演示数据、不伪造成功**。这也是本轮浏览器验证的重点。

## 3. 门控与真实性设计

- **方法级门控**：新增能力先经 `hasRuntimeMethod('GET', path)` 比对运行期 OpenAPI 实测方法。源码契约存在 ≠ 活动实例已加载；未声明一律禁用 / 空态，不发请求。
- **门控先行**：`hasToken() → probeContract() → hasRuntimeMethod()` 全通过才发起业务请求；「契约 / 路由未加载」只由这一步判定，**绝不从响应 404 反推**。
- **两层渲染**：页面级状态区承载门控态、全部错误态与 `unpublished`，不经过 `AsyncPanel`；`AsyncPanel` 只接收 `loading | empty | ready` 三态。这样从根上避免把 library 的 404 误报成「后端服务未加载所需契约路由」。
- **404 语义**：后端对「对象不存在」与「不在当前 principal 授权范围」统一返回 404，不泄露对象是否存在。页面按 `status + code` 精确映射，绕开 `ApiError.kind` 的 not-found / outdated 二分；不自动重试、不强制重新探测、不弹提示，只清空当前层级并提供返回路径。
- **不改全局错误层**：`api/errors.ts`（含 `NEW_API_MARKERS`）、`composables/useAsyncData.ts`、`components/AsyncPanel.vue` 一律不动，避免影响既有 9 个页面。404 语义在页面局部查询层解决。
- **合法空态与错误态分离**：`status=unpublished / list=[] / total=0` 是**合法 200 空结果**（无 ACTIVE 版本），呈现 info 态；`ready` 但空列表是另一种文案；401 / 404 / 422 / 503 是 error 常显。`503 library_schema_not_installed` 明确说明「已发布版本存在但新库结构未安装」，**绝不当空数据**。
- **数据真实性**：`original_text` 按不可信纯文本渲染（禁止 `v-html`），标注 `ocr_not_manually_verified` 且与人工核验字段分框；`verification_status` 默认 `pending`，不把自动提取标成已核验；`penalty_amount` 是精确十进制字符串，不做数值转换或四舍五入；`raw_start / raw_end` 是零基左闭右开**字符范围**（非字节偏移），前端不重新切片；字段为 `null` 显示「后端未返回」，不补写、不推断。
- **身份与参数防错**：`doc_version_id` 只从列表响应行取，禁止从 URL 或拼接推导；`violation` 仅案例库可用（法规库整体隐藏），`kb_version` 仅 ADMIN 可显式选择；请求参数白名单构造，空值不发送，避免 422。
- **原件入口**：`source_url` 指向既有受保护 `/source`，仍需 Bearer；复用认证 Axios ArrayBuffer → Blob URL，**绝不直接塞进 iframe / img**。
- **改动范围**：8 条接口全是 GET，本轮**一条写请求都没有发出**；4173 预览的写保护（`frontend_write_guard`）保持启用。

## 4. 源码改动清单

本轮 14 个前端文件（6 改 + 8 新）。其中两页共用骨架在 Phase 2 规范中转后做了一次结构重构：初版（`36b5a94`）用 `useAsyncData` + 派生 state 映射，最终版（`9038b15`）改为页面局部 `useLibraryQuery` + L1/L2 分层渲染，两次提交均保留在本地历史中，最终以 `9038b15` 为准。

| 层 | 文件 | 要点 |
|---|---|---|
| 契约 / 类型 | `api/types.ts` | 新增 draft-5 分节：`LibraryRecord / LibraryList / LibraryDetail / LibraryParts<T> / LibraryQuery`、章节 / 条款 / 引用 / 结构化详情类型；不改 `LoadState` 等既有定义 |
| | `api/library.ts`（新，254 行） | 8 个 GET 封装、`LIBRARY_ROUTES`（8 条 method+path）、白名单参数构造（空值 `undefined` 不发送）、`doc_version_id` 来源校验；404 / 422 / 503 重抛为保留 `status + code` 的 `ApiError`，**仅作异常兜底，不参与页面状态映射** |
| | `api/dataSource.ts` | `CONTRACT_ROUTES_V023_DRAFT5`、`hasLibraryRoute()` 方法级门控函数；`probeContract` hint 增加 draft-5 路由加载状态（不写死路径数）；清理「46 路径」硬编码 |
| 页面 | `components/LibraryBrowser.vue`（新，803 行） | 两页共用骨架：8 条路由运行期状态表、筛选与分页、列表 → 页内主从详情 → 章节 / 条款 / 引用 → 条款正文；详情页不注册路由（避免刷新后跨身份残留）；原件走认证 Blob URL |
| | `views/library/useLibraryQuery.ts`（新，205 行） | **页面局部状态机**：13 态自定义联合类型（不复用 `LoadState`）；`hasToken → probeContract → hasRuntimeMethod` 门控先行；按 `status + code` 精确映射（404 / 401 / 422 / 503 / 5xx），禁止用 `e.kind === 'outdated'` 判定契约状态；`L2_STATES` 白名单确保 `AsyncPanel` 只接 `loading / empty / ready` |
| | `views/library/LibraryStatePanel.vue`（新，119 行） | L1 状态面板：门控态（warning 标签 + 禁用说明）、错误态（`el-alert type=error` 常显 + 返回上一级 / 返回列表）、`unpublished` 合法空态（info）、请求取消，各自独立分支；L2 才交 `AsyncPanel` |
| | `views/library/copy.ts`（新，75 行） | Phase 2 定稿文案集中管理：门控、unpublished、ready-空、404、422、503、OCR 未核验、字符范围、罚款十进制、NULL 字段 |
| | `views/LawLibraryView.vue`、`views/CaseLibraryView.vue`（新） | 两个薄壳：`kind` 决定差异。法规库**整体不渲染** `violation` 控件，含章节 / 条款 / 条款正文；案例库多 `violation` 筛选、处罚依据引用与案例结构化字段 |
| | `router/index.ts`、`layout/AppLayout.vue` | 新增 `/library/laws`（`LibraryLaws`）、`/library/cases`（`LibraryCases`）；两个菜单项挂在既有「法规知识库」子菜单下作第 3 / 4 项，不新增顶级菜单 |
| 发布状态 | `config/release.ts` | 草稿演进追加 draft-5；顺带移除「22 路径」「30 路径」两处历史硬编码，告警文案补充两页的门控与真实性边界 |
| 样式 | `styles/index.css` | 追加 `lib-` 前缀样式，复用既有 `--mr-*` 变量；沿用注释折叠与 `prefers-reduced-motion` 全局约定 |

**未改动**（避免影响既有 9 页）：`api/errors.ts`（含 `NEW_API_MARKERS`）、`composables/useAsyncData.ts`、`components/AsyncPanel.vue`、`utils/noteToggle.ts`。

## 5. 验证结果

方法：4173 生产构建预览 + 无头 Edge 157 / CDP 9223，注入容器内既有会话凭证（仅内存 / sessionStorage，不落盘、不写入证据），**只发只读 GET**。脚本 `local/frontend-evidence/draft5-adaptation-check.mjs`，结论 `local/frontend-evidence/screenshots/draft5/draft5-adaptation-verification.json`。

- `npm run typecheck` 退出 0；`npm run build` 退出 0（产物含 `LawLibraryView` / `CaseLibraryView` / `LibraryBrowser` / `useLibraryQuery` 相关 chunk；仅有既存 >500 kB chunk 告警，另作优化）。两项均由主理人独立复跑确认。
- **结构重构后完整重跑**：typecheck / build / CDP 全套验证在最终版 `9038b15` 上重新执行一遍，结论一致。
- **11 页面 / 19 项断言 19 通过、0 失败**，console 异常 **0 条**；**5 项如实标注 `NOT_VERIFIABLE`**。

| 验证项 | 结论 |
|---|---|
| 两页渲染、标题、导航新增两项正确归组 | 通过（含截图） |
| 两页「运行期未加载该接口」门控提示 + 筛选 / 查询 / 刷新按钮全部禁用 | 通过 |
| 8 条路由运行期状态表全为「未加载」 | 通过 |
| **网络层断言：`/api/library/*` 请求数 = 0** | 通过（未加载态不偷跑请求） |
| 无业务假数据行、无 `el-skeleton` 假行、无 DEMO 徽章 | 通过 |
| 法规库无 `violation` 控件、案例库有且仅 1 个 | 通过（按真实 DOM 控件判定，非文本匹配） |
| 不出现「后端服务未加载所需契约路由」「资源不存在或已被移除」「重新探测」三类误导文案 | 通过 |
| 不写死 22 / 46 / 54 路径数；draft-5 口径可见 | 通过 |
| `unpublished` 合法空态说明可读 | 通过 |
| 既有 9 个页面（文档 / 检索 / 入库 / 首页 / 系统 / 解析 / 审核 / 账号 / 登录）无回归 | 通过（含 2 张回归截图） |

**首次验证 3 项失败均已查清为验证脚本口径问题，非实现缺陷**：`tableRows=8` 是运行期接口状态表的合法静态行（不是业务假数据）；法规库出现的 "violation" 字样来自「法规库不渲染也不发送 violation 参数」说明文案（控件本身由 `v-if="isCase"` 隐藏）；OCR / Bearer 说明位于详情抽屉，旧实例下列表为空、抽屉不可打开。断言相应改为精确的业务表格行计数、真实 DOM 控件检测，并把详情级说明如实转入不可验证清单，**未通过放宽断言或伪造响应制造通过**。

截图 4 张位于 ignored 的 `local/frontend-evidence/screenshots/draft5/`，不入库。`git diff --check` 无错误；源码与本文档敏感词 / 绝对路径扫描无命中（仅出现既有配置变量名说明，无凭证值、DSN 或机器路径）；未把会话凭证写入源码、报告、截图或 Git。

## 6. 未验证与边界（如实标注，不得据此签发 QA_PASS）

- 活动 8180 未加载任何 library 路由，因此**列表 → 详情 → 章节 / 条款 / 条款正文 / 处罚依据引用**的真实数据链路、分页、以及 `unpublished / 401 / 404 / 422 / 503` 的真实响应分支**全部 `NOT_TESTED`**。本轮只验证「未加载即禁用 / 空态」，不使用请求拦截或伪造响应制造通过。
- 后端专项报告明确：真实库当前无 ACTIVE 版本，法规 / 案例结构化记录为 0，法规与处罚案例 Chunk 均为 0；「结构可用」不等于业务数据齐备。前端两页不得据此宣称已可检索法规或案例。
- `kb_version` 仅 ADMIN 的 403 分支、`violation` 仅案例库的 422 分支、原件下载实物闭环，均需在 Agent C 提供含 draft-5 且已发布 ACTIVE 版本的**短生命周期隔离实例**上，由 WorkBuddy / QA 完成。
- 8180 容器内 dist 仍是冻结的 `63bbcc07…` 构建，**前端源码提交不会自动反映到 8180**；需 Agent C 在 v0.2.3 联合候选中带入最新 dist，并在交接六项中记录最终前端完整 HEAD。
- 独立 QA 验收与生产部署未做；不继承任何历史 `QA_PASS` 作为整版结论，不签发 `QA_PASS`。未经新版本独立 QA 与用户最终部署授权，不切换 8180、不 Push / Merge / Tag。

## 7. 提交与交接

- 分支 `feat/frontend-api-v0.2.2`，**仅本地提交**，共 3 笔：
  1. `36b5a94de9946c73a5635851df2e9ffc46261353` — `feat(frontend)`: draft-5 契约层 + 两页初版接入；
  2. `9038b15981fcf3f3ce45f6a7bd38f4f900359594` — `refactor(frontend)`: 两页改用页面局部状态机与 L1/L2 分层渲染（**最终源码 HEAD**）；
  3. 本文件为文档提交（最终前端完整 HEAD 见交付消息 / 工作记忆）。
- 未 Push / Merge main / 打 Tag / 部署生产。
- 8180 容器内 dist 仍是冻结的 `63bbcc07…` 构建，**前端源码提交不会自动反映到 8180**；4173 预览已用本轮新构建产物验证，但那是独立预览服务，不代表活动实例已更新。
- 请 **Agent C 在构建 v0.2.3 联合候选时带入本轮最新 dist**，并在交接六项中记录文档提交后的最终前端完整 HEAD；QA 报告另记镜像 ID、8180 身份、前端 SHA 与实际验收范围。
- 后端专项报告 §F 已明确数据准备阻塞项（法规 / 案例分类、可信法规事实、原文条款定位、案例字段及引用核验、审核门禁、正式候选发布），这些不是前端能补齐的；前端两页不得据此宣称已可检索法规或案例。
- 未经新版本独立 QA 与用户最终部署授权，不注入正式账号 / 写入凭据、不切换 8180、不签发 `QA_PASS`。
