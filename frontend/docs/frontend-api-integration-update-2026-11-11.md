# v0.2.1 QA PASS 后 · 接口接入与更新报告

> 日期：2026-11-11（GMT+8）
> 前端：本 worktree 的 `frontend/` 目录，分支 `feat/frontend-v0.2.1` @ `f4a0af8`
> 触发：用户告知「v0.2.1 审查已经通过，对接口进行整体的接入和更新」
> 边界：仅修改 `frontend/`；后端 `qa_core/**`、QA 工作区、原始目录均未触碰；无 commit / merge / push / 部署

---

## 0. 一句话结论

**QA 确实 PASS，但后端没有新增任何 HTTP 接口，9 个 API 的契约在最新代码里一字未改。**
因此本轮完成的是「发布状态更新 + 接口契约复核留痕 + 接口清单可视化」，**不是新接口接入**；真实接入数量保持 9 个，未接入能力保持 11 组，写操作仍全部禁用。

---

## 1. 核实过程（以代码为准，不猜测接口）

### 1.1 QA 结论与边界

| 项 | 事实 |
|---|---|
| 裁决 | `docs/qa/v0.2.1/final-release-decision.md`（`codex/qa-v0.2.1` @ `843c64d`），签发 **2026-11-11，结论 PASS** |
| 通过范围 | 后端 MVP + c915 候选镜像的本地集成验收；源码身份 `c91547d393ca6b049e216c0051e25271d06d7359` |
| Fix 交接 HEAD | `3129479`（`codex/fix-v0.2.1`） |
| 发布归档 | `5dd44b9`（`codex/maint-v0.2.1-original`） |
| **明确排除** | 生产部署、活动旧实例切换、Windows 整机恢复、**独立前端全部联调**、外部来源迁移、多 Worker、MySQL 任务迁移 |
| 原文要点 | 「外部来源迁移、多Worker、MySQL任务迁移、**独立前端全联调**、大规模效果优化继续是后续范围」；「活动旧实例不是本次PASS镜像」 |

→ **QA PASS 不能推导出「前端可以标记正式可用」，也不能推导出「新接口已交付」。**

### 1.2 四分支路由逐行比对

对 `f4a0af8`（前端基线）、`3129479`（Fix）、`843c64d`（QA）、`5dd44b9`（发布归档）分别提取 `@app.*` 路由：

**四者完全一致，均为 9 个 API + 1 个无鉴权根页面**：

```
GET  /                                              (include_in_schema=False)
GET  /api/parse/info
POST /api/parse/files                              (201)
POST /api/parse/tasks                              (202)
GET  /api/parse/tasks/{task_id}
GET  /api/parse/tasks/{task_id}/errors
POST /api/parse/tasks/{task_id}/resume             (202)
POST /api/parse/tasks/{task_id}/cancel
GET  /api/parse/tasks/{task_id}/results
GET  /api/parse/tasks/{task_id}/files/{file_id}/artifact
```

- `mineru_api.py` 从 `f4a0af8` → `5dd44b9` 的 diff **只有 3 处注释中文化**；路径、参数、响应字段、状态码、`owner` 鉴权、`create_app()` 的 `docs_url=None / redoc_url=None / openapi_url=None` 全部未变。
- `GET /api/parse/info` 仍返回 `{mode, provider, enabled, database_enabled, dual_engine_enabled}`，无 `version` / `environment`。
- 全仓仅 `qa_core/document_parsing/mineru_api.py` 含 `FastAPI(...)`，**无第二套 HTTP 服务**：
  - 新增的 `deploy/local/entrypoint.py` 只是 `uvicorn qa_core.document_parsing.mineru_api:create_app --factory --port 8180` 启动器；
  - 新增的 `qa_core/indexing/preview.py` 是 CLI / 服务层只读切分预览，明确「不审核、向量化、建表或发布版本」，不是 HTTP 接口。
- 最新分支相对前端基线共 147 文件 / +6921 行差异，主体是 QA/发布文档与测试；核心 py 有修改，但**没有新增任何路由**。

### 1.3 运行期探测（`127.0.0.1:8180`）

| 路径 | 结果 |
|---|---|
| `/` | 200（自带上传页） |
| `/api/parse/info`（无 Token） | 401（符合既有鉴权） |
| `/openapi.json`、`/docs` | 404 |
| `/api/documents`、`/api/system/health`、`/api/stats/overview` | 404 |
| `/api/parse/engines/status`、`/api/ingestion/batches`、`/api/knowledge/search`、`/api/review/*` | 404 |

当前 8180 监听在 `127.0.0.1:8180`（PID 23224），QA 裁决注明「活动旧实例不是本次 PASS 镜像」，故不作为 PASS 镜像的运行证据。

---

## 2. 本轮实际改动

| 文件 | 改动 |
|---|---|
| `src/config/release.ts` | **新增**：发布状态唯一事实来源（QA 结论/日期/范围/短标签/告警文案/契约复核结论），避免 5 处文案各写各的 |
| `src/layout/AppLayout.vue` | 侧栏标签 → `{{ releaseStatus.shortLabel }}` |
| `src/views/DashboardView.vue` | 页头标签 → 统一常量 |
| `src/views/LoginView.vue` | 告警标题/描述 → 统一常量 + QA 范围说明 |
| `src/views/SystemView.vue` | 页头标签 + 底部告警 → 统一常量；**新增「接口接入状态总览」** |
| `src/stores/app.ts` | `qaAccepted` 注释与取值更新（仅状态追踪，不用于宣称正式可用） |
| `src/api/parse.ts`、`src/api/dataSource.ts` | 注释与基线标注更新；明确「QA PASS ≠ 接口交付」，11 个 false 开关一个不动 |
| `docs/frontend-api-mapping.md` | 头部基线更新 + **新增 §6 契约复核** |
| `docs/backend-api-requirements.md` | 状态段更新 + **新增 §0.1 QA PASS 边界** |
| `docs/frontend-optimization-report.md` | 第 7 条更新 + **新增 §11 追加更新** |

### 系统监控页新增能力

「接口接入状态总览」计数直接取自 `apiCapabilities`（`Object.values` 过滤），**不伪造运行期探测结果**：

- Tab 1「已接入（9）」：方法、路径、使用页面、REAL 标记；
- Tab 2「待交付（11）」：优先级 P0/P1、建议接口、解锁能力、未接入状态；
- 卡片下方明确：「仅反映后端路由源码事实，不代表这些接口已在运行实例上探测成功（探活需有效 Token）」。

页面自身现在就能回答「还缺哪些接口」，无需翻文档。

---

## 3. 接入数量与状态（无变化）

| 指标 | 上轮 | 本轮 |
|---|---|---|
| 真实 API 接入数 | 9 | **9** |
| Mock / 未接入能力 | 11 组 | **11 组** |
| 已解除禁用的写操作 | 0 | **0** |
| 伪造法条 / 假审核成功 / 假预览 | 0 | **0** |
| 页面上可自查的接口清单 | 无 | **系统监控页新增** |

**禁用原因是接口不存在，与 QA 是否通过无关**——审核 4 项、入库批次、检索、文档下载/重新解析继续保持 `disabled`。

---

## 4. 仍需后端交付（按优先级）

### P0 · 硬阻塞 3 组

1. `GET /api/parse/files/{file_id}/source` —— 原始字节、SHA256 与上传响应一致、支持 `Range` 206、按 owner 隔离；**不得用 `artifact.bin` 冒充**（解析产物）。解锁审核中心真实 PDF/Word 预览、缩略图、下载。
2. `GET /api/documents?...` —— `{list, total}`、7 态枚举、后端计算 SHA256。解锁文档列表真实搜索/筛选/分页。配套 `GET /api/documents/{id}`、`/parse-history`。
3. 审核 5 个：`GET /api/review/{doc_id}` + `POST .../approve`、`/reject`、`/mark-error`、`/save-revision`；修订必须追加新版本、留审计、不修改原始文件字节。解锁 4 个写按钮。

### P1 · 8 组

任务列表 `GET /api/parse/tasks`、结构化日志 `/logs`、引擎状态 `/api/parse/engines/status`（响应不含 Key）、统一统计 `/api/stats/overview` + `/trend`、入库 5 接口（precheck / batches / stages / version-check）、检索 `POST /api/knowledge/search`（命中必须带来源文件与原始分数，无依据返回空列表）、系统健康检查与三类日志、六组件五态。

### P2

非生产环境启用 `openapi_url`，接口映射可自动生成（当前只能读源码）。

### 联调前置条件

1. 后端提供 ≥32 位测试 Token（`PARSING_API_TOKENS_JSON`）；
2. 后端确认现有 9 个接口契约未变，或给出变更说明；
3. 用户明确下达「接口已提供，可以接入」。

接口到位后：替换 `src/api/documentFiles.ts` 等适配层实现 + 把 `apiCapabilities` 对应项置 `true`，**页面无需重做**；真实 PDF/Word 渲染还需批准引入 `pdfjs-dist@4.10.38`(Apache-2.0)、`@vue-office/docx@1.6.3`(MIT)、`vue-demi`(MIT) 三个纯 JS 依赖。

---

## 5. 构建与回归结果

| 项 | 结果 |
|---|---|
| `npm run build` | ✅ 14.50s（仅有既存的 chunk >500kB 提示，非错误） |
| `npm run typecheck`（`tsc --noEmit`） | ✅ 0 错误 |
| 7 条业务路由直访 / 刷新 | ✅ 全部渲染，history fallback 正常 |
| 控制台错误 | ✅ 7/7 页面无 uncaught / console error |
| 新内容渲染校验 | ✅ 「后端 QA PASS」「接口接入状态总览」「已接入（9）」「待交付（11）」「/api/parse/files/{file_id}/source」均命中；旧文案「尚未完成正式 QA 验收」「v0.2.1 未验收」零残留 |
| 截图 | ✅ `r5-system-1920.png`、`r5-system-1366.png`、`r5-dashboard-1920.png`（1366 无横向溢出，1920 表格与卡片布局正常） |

预览地址：`http://127.0.0.1:4173/dashboard`（`npm run preview`，构建产物）。

---

## 6. Git 安全边界

- 分支 `feat/frontend-v0.2.1` @ `f4a0af8` 未变；工作区仍仅 `?? frontend/`（前端整体 untracked）。
- 未同步/合并后端最新分支：虽然 `5dd44b9` 领先基线 47 个提交，但 API 契约零变化，且用户既定边界为「不自动提交、合并、推送」，故前端 worktree 的后端副本保持只读原样。
- 未修改 `qa_core/**`、`docs/qa/**`、`.venv*`、OCR/BGE-M3 模型、`.env`、`compose*.yaml`；未触碰 QA 工作区与原始目录。
- 未引入/升级任何依赖（保持 Vite 4.5，规避本机 WDAC 对未签名 `.node` 的拦截）。

---

## 7. 需要用户确认的一件事

若新接口其实在**本仓库之外的另一个服务/分支/文档**里（例如用户另行提供的新 API 规格），请给出路径或文件；当前本仓库全部 worktree 分支与运行中的 8180 实例均只包含那 9 个 API。拿到新契约后即可立即进入真实接入，不需要重做页面。
