# v0.2.3 draft-2 多用户身份与审核权限 —— 前端适配交付

> 日期：2026-11-12　分支：`feat/frontend-api-v0.2.2`（仅本地提交）
> **最终状态：`ADAPTATION_PREPARED`**（不是 QA_PASS / READY_FOR_RELEASE / RELEASED，也未达到 `READY_FOR_JOINT_QA`）
> 源码提交：`8d86ace7efb95a5128647a97f24a27d253172f73`；本说明文档提交后的前端完整 HEAD 以交付回复为准，Agent C 集成时请使用该最终 HEAD 记录前端 revision。

## 0. 状态判定依据

类型检查、生产构建、静态核查与「默认代理不向正式 8180 写入」的**实测**均已完成；但 Agent C 未在本机提供短生命周期隔离后端入口、合成身份凭证与 `market_review_test_` 隔离库，联合候选也尚未构建，因此任务书第五节的 7 项隔离联调**全部 `NOT_TESTED`**。按「不把构建通过当 QA_PASS」的要求，状态取 `ADAPTATION_PREPARED`，不签发 `READY_FOR_JOINT_QA`。

## 1. 版本核对（实施前只读，未重置或覆盖工作区）

| 项 | 实际值 |
|---|---|
| 前端分支 / 实施前 HEAD | `feat/frontend-api-v0.2.2` / `4779ed8bbe73f6dce362e59683b18a404cbefdd8` |
| 已知交接 HEAD | `77d12109e362a6d19ce4e35e4fd580b4bc539a04`（在历史中） |
| 两者差异 | 比交接 HEAD 多 2 个本会话提交：`b8f6e2a1d4268ef32c12ee4b5d5bf589c3a48a92`（文档列表多选/删除门控）、`4779ed8bbe73f6dce362e59683b18a404cbefdd8`（说明文档）。**已保留，未回退、未覆盖** |
| 实施前工作区 | 干净，无未提交文件 |
| C01 修复提交 | `03af02cedc84fce8b19e169e49c6bb456ef17371`（`event.request` 层级 + 冻结幂等快照），本轮完整保留 |
| 后端 RBAC 源码 | `b96c34901f783cd136235663d20ccef6cc62a019`（主目录可见，分支 `codex/backend-improvements-v023`，主目录 HEAD `228879d735831a07ef6843437bc25014b78847a0`） |
| 候选镜像 | 标签 `market-regulation-workbench:candidate-v023-rbac-b96c34901f78`；镜像 ID `sha256:be18c7064c73bcd5ac312b6919809ac6edc19008ee45b30249ed704ace797b4c`；OCI revision `b96c34901f783cd136235663d20ccef6cc62a019` → **镜像 ID 与源码 SHA 对应一致** |
| 后端独立 QA_PASS | 依据 `docs/release/v0.2.3/rbac-qa-handoff.md`，**仅覆盖后端隔离候选，不含新前端联合验收** |
| 正式 8180 | 容器 `market-regulation-app-1` healthy；镜像 `market-regulation-workbench:sha-30c4663…`，镜像 ID `sha256:e2a94f67…52a3`，OCI revision `30c4663ceb93…bfb4`；契约 `0.2.2-api-candidate` / 22 路径。**未用于新审核写入验证** |

## 2. 依据与 draft-1 → draft-2 契约差异

读取了任务书指定的 4 份依据：`docs/release/v0.2.3/identity-rbac-design.md`、`docs/release/v0.2.3/rbac-qa-handoff.md`、`docs/integration/frontend-openapi-v023-draft2.json`、`docs/integration/frontend-v023-contract-review.md`。

| 项 | draft-1（旧） | **draft-2（当前依据）** |
|---|---|---|
| 契约名 / 路径数 | `frontend-api-v0.2.3-draft-1` / 29 | `frontend-api-v0.2.3-draft-2` / **30** |
| 新增路径 | 4 写 + 3 读 | 再增 `GET /api/auth/me` |
| 身份 | Token→owner，owner 近似操作者 | `principal_id`（实际登录人员）与 `owner_id`（业务归属）分离，五个字段必填 |
| 角色 / 授权 | owner→writers 名单 | `roles` = USER/REVIEWER/ADMIN；`review_owner_scopes` 白名单；**ADMIN 不隐含 REVIEWER**，writers 完全退出授权计算 |
| 回执 / 事件 | `operator` 兼容别名 | 增 `operator_id`、`owner_id`、`identity_model`；旧事件可为 null / `legacy-owner`，**不补认具体人员** |
| 写请求 | 只要求不传 operator | `ReviewAction` 为 `additionalProperties:false`，传入 `operator_id`/`owner_id`/`roles` 等返回 422 |
| 幂等命名空间 | 按 owner + 客户端键 | 按 **数据 owner + principal_id + 客户端键** 隔离；不同人复用键不会拿到对方回执 |
| 越界 / 撤销 | — | 越界对象 404；凭证停用/撤销 401；角色/范围撤销后下一请求 403，配置读取失败 503 |

`frontend-v023-contract-review.md` 指出的 C01（事件正文在 `event.request`）与重试语义（冻结首次请求、503 不得推断「一定没写入」）已在 C01 提交中修复，本轮**保持不破坏**。

## 3. 修改清单

| 文件 | 改动 |
|---|---|
| `src/api/authEvents.ts`（新） | 无依赖的 401/403/404 状态广播，避免请求层与身份层循环 import；只传状态码，不传凭证或响应正文 |
| `src/api/principal.ts`（新） | `GET /api/auth/me` 唯一出口；持有五字段身份、加载态与错误；`identityBlocksWrite`（只收紧）、身份文案 helper；401/403 清身份 + 清契约缓存并保留 `no-permission` 态，404 只标记需重新确认（避免 404 递归） |
| `src/api/types.ts` | `PrincipalInfo` / `PrincipalRole` / `CredentialStatus` / `ReviewIdentityFields`；`ReviewReceipt`、`ReviewEvent`、`AuditLogItem` 增 `operator_id`/`owner_id`/`identity_model`；`RuntimeOpenApi.info` 增 `x-contract-version` |
| `src/api/client.ts` | 响应拦截广播 401/403/404；注释改为 principal-v1 口径 |
| `src/api/dataSource.ts` | `V023_IDENTITY_ROUTE` + `hasV023Identity()`；`ContractMeta.contractVersion` 记录 `x-contract-version`；`CONTRACT_ROUTES_V023` 增至 8 行；清理 owner/writers 说明 |
| `src/api/reviewWrite.ts` | draft-2 注释；`assertNoIdentityFields()` 运行时防御（命中即不发送请求）；`makeReviewActionBody` 白名单构造；幂等命名空间与事件隔离口径说明 |
| `src/api/errors.ts` | 401/403 文案区分凭证失效与授权/范围；`/api/auth/me` 加入 404 新接口标记；清理旧镜像推断文案 |
| `src/stores/app.ts` | 登录 `probeAll()` 串行确认身份；登出 `clearPrincipal()` |
| `src/layout/AppLayout.vue` | 顶栏显示 `principal_id · roles`，下拉含 owner_id / 范围 / 角色 / 重新确认；**移除「审核员」误称** |
| `src/views/ReviewView.vue` | 身份条 + 身份口径说明；事件表新增 `operator_id`/`owner_id`/`identity_model`/兼容别名列；回执展示身份；meta-bar 区分登录人员与文档所属人；门控新增 `identity-locked`；提交前重新确认身份；6 类错误码分支；404 清空当前对象与回执 |
| `src/views/SystemView.vue` | 新增「当前登录身份」卡片；契约名显示；审计摘要身份列；v0.2.3 页签文案改 draft-2 / 30 路径 |
| `src/views/DocumentsView.vue`、`src/components/document/DocumentPreview.vue`、`src/api/documentFiles.ts`、`src/components/AsyncPanel.vue` | 隔离口径文案：按 principal 与业务 owner 范围，越界 404 |
| `src/config/release.ts` | 文件头补当前 draft-2 口径（历史事实保留） |
| `vite.config.ts` | `VITE_API_PROXY_TARGET` 可指向隔离入口；**默认目标（正式 8180）本地拦截非只读 `/api` 请求**，只读 POST（检索/结构预览）白名单；`VITE_ALLOW_WRITE_TO_DEFAULT_TARGET=1` 才解除 |
| `docs/frontend-v023-adaptation-2026-11-12.md` | 顶部加「口径更新提示」，明确 draft-1/29 路径/writers 为历史事实、当前依据为 draft-2；**原文不改** |

## 4. 接口映射

| 后端接口 | 前端出口 | 使用页面 / 作用 |
|---|---|---|
| `GET /api/auth/me` | `src/api/principal.ts` | 顶栏、审核中心身份条、系统监控身份卡；五字段展示，失败显示未确认 |
| `GET /api/openapi.json` | `src/api/dataSource.ts` | 运行期路径 + 方法级门控；记录 `x-contract-version` 与路径数 |
| `GET /api/review` | `src/api/frontend.ts` | 待复核队列（后端按范围过滤，前端不本地伪造） |
| `GET /api/review/{parse_id}` | `src/api/frontend.ts` | 详情 + `review_write_supported` / `review_ledger.available` 第二道门 |
| `POST /api/review/{parse_id}/approve\|reject\|mark-error\|save-revision` | `src/api/reviewWrite.ts` | 四写动作；白名单 body + `Idempotency-Key` + `expected_version` |
| `GET /api/review/{parse_id}/events` | `src/api/reviewWrite.ts` | 台账事件；正文/理由/页码取 `event.request`，身份取 `operator_id`/`owner_id` |
| `GET /api/system/audit-logs` | `src/api/reviewWrite.ts` | 审计摘要；展示操作者与文档所属人 |

## 5. 授权、错误与重试语义

- **门控**：`canWrite = 运行期 4 条写路径 + 详情双门控 + 身份已确认 + 非明确非 REVIEWER`。本地 `roles`/`review_owner_scopes` **只收紧、绝不放宽**；REVIEWER 也不能仅凭角色写入，最终由后端按每次请求的 Principal 与目标 owner 判定。
- **USER / ADMIN**：身份已确认且不含 REVIEWER 时，页面显示「审核写入未启用 · 当前身份无审核角色或未确认」，四个按钮禁用；不存在「ADMIN 自动获得审核权」。
- **提交前**：`submitAction` 在发送前向后端重新 `GET /api/auth/me`；身份未确认或角色不含 REVIEWER 直接取消提交，不沿用旧可写状态。
- **请求体**：`makeReviewActionBody` 白名单构造 + `assertNoIdentityFields` 运行时拦截，绝不发送 `operator_id` / `owner_id` / `roles` / `principal_id` 等。
- **错误码**：

| 状态 | 前端行为 |
|---|---|
| 401 | 清除身份 + 运行期契约缓存，双门控失效；清冻结快照与回执；提示凭证失效/撤销 |
| 403 | 清快照；重新确认身份、刷新详情与队列；提示角色/范围撤销或不在 `review_owner_scopes` |
| 404 | 清快照、清空当前详情/事件/回执、刷新队列与身份；提示对象越界或范围撤销 |
| 409 | 清快照、刷新详情；提示版本变化或同 principal 同键异请求，作为新操作换键 |
| 422 | 清快照；提示必填字段/页码/契约外身份字段 |
| 503 / 0 / 5xx / 408 / 429 | **保留冻结的 action / parseId / body / 幂等键**，弹窗提示「结果未确认 · 同键同请求重试」，不推断一定没有写入 |

- **身份展示**：实际操作者取 `operator_id`，文档所属人取 `owner_id`（后端给出，前端不从登录 owner 推断）；旧事件为 null 显示「未知（历史记录）」，`legacy-owner` 明确标注为历史 owner 别名；不把历史 owner 补认成人员。
- **C01 保留**：事件正文/理由/页码从 `event.request` 读取；修订正文不 trim、保留前导空格与换行；表格/Markdown/修订一律纯文本，无 `v-html`。
- **语义边界**：回执如实展示 `publish_authorized` / `reparse_task_created`；审核通过不等于发布 ACTIVE，退回不等于已创建解析任务，原始 OCR 与原件只读。

## 6. 已完成的验证（可核验）

| 项 | 结果 |
|---|---|
| `npm run typecheck` | 退出 0 |
| `npm run build` | 退出 0；产物 `index-5027556f.js`、`ReviewView-b17e4efa.js`、`SystemView-6b3a8b0b.js`、`principal-424e6ae2.js`、`AppLayout-036bd9b1.js`（仅既有 >500 kB 告警） |
| `git diff --check` | 无错误 |
| 敏感信息扫描 | 2 处命中仅为既有 Token 输入框的**环境变量名称**占位文案；无凭证值、DSN、绝对机器路径、原始业务资料或敏感截图进 Git |
| 4173 本地预览 | `/review` 200 且引用 `index-5027556f.js`；新 chunk 均 200；`GET /api/openapi.json` 未带凭证 401 |
| 写入保护实测 | `POST /api/parse/tasks` → **403 `frontend_write_guard`**（本地拦截，未转发正式 8180）；`POST /api/knowledge/search` → 401（只读白名单正常转发）；测试后正式容器仍 healthy |
| 正式 8180 | 只读复核：容器 healthy、镜像 ID 与 OCI revision 未变；未向其发起任何写入 |

> 4173 是本地预览服务，为使 `vite.config.ts` 的写入保护生效而重启过一次；**未重启或替换任何共享后端服务/容器**。

## 7. 隔离联调：全部 NOT_TESTED

本机只读探测：仅 `127.0.0.1:8180`（正式 v0.2.2）在监听；运行容器只有正式 app / redis / mysql / pgvector；无 `VITE_API_PROXY_TARGET`、无隔离入口、无合成身份凭证、无 `market_review_test_` 隔离库、无联合候选。`rbac-qa-handoff.md` 明确候选是 `--rm`、无端口发布的短生命周期容器。因此：

| # | 任务书要求的验证项 | 状态 | 前置条件 |
|---|---|---|---|
| 1 | USER / REVIEWER / ADMIN 页面差异 | `NOT_TESTED` | 隔离入口 + 3 类合成凭证 |
| 2 | 授权与越界文档访问（越界 404） | `NOT_TESTED` | 隔离入口 + 双 owner 合成数据 |
| 3 | 四个审核动作及事件正文显示 | `NOT_TESTED` | 隔离 draft-2 实例 + 审核台账 |
| 4 | 两名审核员的独立身份记录 | `NOT_TESTED` | reviewer-1 / reviewer-2 同 owner 合成凭证 |
| 5 | 角色撤销、Token 失效、版本冲突、未知结果重试 | `NOT_TESTED` | 可动态改私密配置的隔离实例 |
| 6 | 审核不等于发布 | `NOT_TESTED` | 隔离实例 + 发布状态观测 |
| 7 | 退回不等于已创建解析任务 | `NOT_TESTED` | 隔离实例 + 任务列表观测 |

未做浏览器正向 UI 联验，未调用任何真实审核写入接口，未伪造截图或成功结果。

## 8. 交 Agent C / QA

**Agent C**：
1. 以本轮**最终前端完整 HEAD**（见交付回复）集成联合候选，把新 `dist` 带入镜像（旧候选内仍是冻结的 `63bbcc07…` 前端，不可用后端通过替代 UI 联验）；生成新的唯一候选标签，不覆盖旧候选。
2. 提供短生命周期隔离 HTTP 入口、合成身份凭证（USER、REVIEWER×2 同 owner、越界 REVIEWER、纯 ADMIN）、`market_review_test_` 前缀隔离库；不注入正式 runtime、不改正式角色/正式 `market_review`、不切换 8180。
3. 交接记录六项：后端源码完整 SHA、Docker 镜像 ID、镜像标签、OCI revision、当前运行容器、8180 实际服务身份；另记前端 Git SHA 与 `frontend-api-v0.2.3-draft-2` 契约版本。镜像 ID 必须与源码 SHA 明确对应。

**QA**：按 §7 逐项独立验收，并记录候选镜像 ID、源码 SHA、前端 SHA、契约版本、测试脚本提交、数据隔离与实际执行范围；Agent C 的 61 项自测不得复制为 QA_PASS；旧事件未被改写、两名审核员 `operator_id` 不同且 `owner_id` 相同、撤销后不残留可写状态需单独确认。

## 9. 剩余问题与硬边界

- 无隔离入口与合成身份，联合候选未构建 → 正向联验缺口（§7）。
- 正式 `market_review` 已创建但未注入 runtime、未启用审核；**未当作测试库，未读取或传播正式账号密码**。
- 未改后端源码、数据库、ACTIVE、正式角色或 runtime；未构建/替换共享后端镜像，未重启正式服务，未改数据卷。
- 凭证仅存内存 + `sessionStorage`，未写入源码、文档、证据或 Git；证据卷为 ignored 目录。
- 未 Push / Merge main / 打 Tag / 部署；未自行签发 QA_PASS、READY_FOR_RELEASE、RELEASED。
- 默认开发代理现在会拦截指向正式 8180 的写入请求；隔离联调须显式设置 `VITE_API_PROXY_TARGET`，否则写动作返回 403 `frontend_write_guard`（这是预期边界，不是功能故障）。

## 10. 证据索引

`local/frontend-evidence/v023-rbac-adaptation-verification.json`（ignored，不入 Git），索引键 `v023_rbac_adaptation` 见 `local/frontend-evidence/evidence-manifest.json`。包含版本核对、契约差异、实现检查表、构建产物、写入保护实测、隔离环境探测结果与 NOT_TESTED 清单。
