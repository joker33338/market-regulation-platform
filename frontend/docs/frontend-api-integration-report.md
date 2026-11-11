# v0.2.2 前端真实 API 对接与联调交接报告

> 生成日期：2026-11-11
> 前端分支：`feat/frontend-api-v0.2.2` @ `6ecb2ae`
> 后端契约分支：`feat/backend-api-v0.2.2` @ `4fc4cf124a120762593064676ea5f8dbe2394119`
> 契约版本：`frontend-api-v0.2.2-1`

---

## 0. 最终结论

```
FRONTEND_INTEGRATION_PARTIAL
```

**判定依据**：用户规则明确「只有真实接口成功调用并验证的功能才能标记 READY」。本轮源码层已把全部 v0.2.2 契约接入七个页面，并通过类型检查、生产构建、路由/产物、代理转发与安全校验；但**活动 8180 实例仍是 v0.2.1 旧镜像**（全部新接口实测 404），且**未提供 ≥32 位联调 Token**，因此没有任何一个真实接口在浏览器端成功返回并渲染业务数据。故只能给出 `PARTIAL`。

**边界说明**：`PARTIAL` 不等于「前端代码未完成」。前端可交付部分已全部完成并逐页提交（10 个本地 commit）；未验证项全部属于运行期环境（镜像切换 + 凭证），前端不得自行切换 Docker 或伪造响应来凑 READY。

---

## 1. 基线与事实来源

| 项 | 值 | 说明 |
|---|---|---|
| 前端工作区 | `F:\刘凯工作\market-regulation-platform-frontend` | 独立 Worktree，后端副本只读 |
| 前端分支 / HEAD | `feat/frontend-api-v0.2.2` / `6ecb2ae` | 未 Push、未 Merge main、未部署 |
| 前端维护基线 | `5dd44b97710db0d3bdb84bcec6e1624dd70205dc` | 从维护基线新建分支，未使用过时 `main` 开发 |
| 本轮提交数 | 10（`c23f011` → `6ecb2ae`） | 每完成一页/一组 API 单独提交 |
| 切换前备份 | `F:\刘凯工作\market-regulation-frontend-backup-20261111` | 46 个源码/文档，不含 `node_modules`/`dist` |
| 后端仓库 / HEAD | `F:\刘凯工作\market-regulation-platform` / `4fc4cf124a120762593064676ea5f8dbe2394119` | 与 `release.ts` 记录一致 |
| 后端工作区状态 | 5 个 `M` 文件（`qa_core/api/*`、`mineru_api.py` 等） | `git diff --numstat` 与 `git diff --ignore-cr-at-eol` 均为空 → **仅 CRLF 归一化，无内容/契约变化** |
| 正式契约 | `docs/integration/frontend-api-contract.md` | 11.4 KB，契约版本 `frontend-api-v0.2.2-1` |
| 缺口报告 | `docs/integration/frontend-api-gap-report.md` | 后端自评 `BACKEND_API_PARTIAL` |
| 离线 OpenAPI 快照 | `docs/integration/frontend-openapi.json` | OpenAPI 3.1.0，`info.version=0.2.2-api-candidate`，22 个路径 / 16 schema |
| 运行期契约 | `GET /api/openapi.json` | 需 Bearer Token，`include_in_schema=False`，不出现在公开 schema |
| 活动容器 | `market-regulation-app-1` `Up 4 hours (healthy)`，`127.0.0.1:8180->8180/tcp` | 未切换镜像（用户约束） |

> v0.2.1 时期的 `frontend/` 整体处于 untracked 状态、从未提交；本轮 `c23f011` 先将其纳入版本控制，再逐页改造，因此相对基线的 diff 统计表现为「新增 51 个文件」。

---

## 2. 接口映射矩阵（源码接入 vs 运行期验证）

「前端对接」= 本轮代码已完成；「运行期」= 2026-11-11 对活动 8180 实例的实测结果。

| 页面 | 功能 | 方法 | 实际 URL | 请求参数 | 返回字段 | 前端对接 | 运行期 |
|---|---|---|---|---|---|---|---|
| 文档管理 | 原始文件上传 | POST | `/api/parse/files` | query `file_name`；body 原始字节（非 multipart） | `file_id,sha256,bytes` | ✅ 复用 | 401（无 Token） |
| 文档管理 | 列表/搜索/分页 | GET | `/api/documents` | `page,page_size,keyword,status,doc_type` | `DocumentList{list,total,page,page_size,source}` | ✅ `cf1d3d1` | **404** |
| 文档管理 | 文档详情 | GET | `/api/documents/{file_id}` | path 上传 ID | `DocumentInfo` | ✅ `cf1d3d1` | **404** |
| 文档管理 | 解析历史 | GET | `/api/documents/{file_id}/parse-history` | path + `page,page_size` | `ListResponse{task,file_id,source_file_id,database_parse_id,elapsed_seconds}` | ✅ `cf1d3d1` | **404** |
| 文档管理/审核 | 原始文件授权读取 | GET / HEAD | `/api/parse/files/{file_id}/source` | path `source_file_id`；可选 `Range` | 二进制 + `X-SHA256`；206/416 | ✅ `18e2f28` | **404** |
| 文档管理 | 解析结果入口 | GET | `/api/parse/tasks/{task_id}/results` | path | `TaskResults` | ✅ 复用 | 401 |
| 智能解析 | 服务信息 | GET | `/api/parse/info` | 无 | `mode,provider,enabled,database_enabled,dual_engine_enabled` | ✅ 复用 | 401（可达） |
| 智能解析 | 创建任务 | POST | `/api/parse/tasks` | body `{file_ids}`；header `Idempotency-Key` | `ParseTask` | ✅ 复用 | 401 |
| 智能解析 | 任务列表 | GET | `/api/parse/tasks` | `page,page_size,status,engine` | `TaskList` + `file_mappings` | ✅ `d87b3a5` | **405**（旧服务仅 POST） |
| 智能解析 | 详情 / 失败 / 结果 / 产物 | GET | `/api/parse/tasks/{id}`、`/errors`、`/results`、`/files/{file_id}/artifact` | path | `ParseTask` / `TaskResults` / `artifact.bin` | ✅ 复用 | 401 |
| 智能解析 | 恢复 / 取消 | POST | `/api/parse/tasks/{id}/resume`、`/cancel` | path | `ParseTask` | ✅ 复用 | 401 |
| 智能解析 / 入库 | 任务文件 Chunk 预览 | POST | `/api/parse/tasks/{task_id}/files/{file_id}/preview` | body `PreviewRequest{document_type,max_chars}` | `PreviewResponse{preview,write_performed:false}` | ✅ `7b8fe74` | **404** |
| 文档审核 | 完整待复核队列 | GET | `/api/review` | `page,page_size,requires_review=true` | `ReviewQueue`（`document_review.documents`，非 `v_review_queue`） | ✅ `614d537` | **404** |
| 文档审核 | 详情 / 候选对照 | GET | `/api/review/{parse_id}` | path `parse_id` | `ReviewDetail{raw_text,markdown_content,original_result,quality,local_candidate,review_write_supported:false}` | ✅ `614d537` | **404** |
| 文档审核 / 入库 | 已持久化结果预览 | POST | `/api/review/{parse_id}/preview` | body `PreviewRequest` | `PreviewResponse` | ✅ `7b8fe74` | **404** |
| 知识库入库 | 版本列表 | GET | `/api/knowledge/versions` | `page,page_size` | `KbVersionList`（public 只读） | ✅ `7b8fe74` | **404** |
| 知识库入库 | 版本详情 | GET | `/api/knowledge/versions/{version}` | path | `VersionInfo` | ✅ `7b8fe74` | **404** |
| 法规检索 | 正式知识库检索 | POST | `/api/knowledge/search` | body `{query,mode:keyword\|hybrid,limit}`（额外字段 422） | `SearchResponse{status:ready\|unpublished,kb_version,list[SearchHit],count,source}` | ✅ `15e40a1` | **404** |
| 首页工作台 | 统计与趋势 | GET | `/api/stats/overview` | `days`（1–366，默认 14） | `StatsResponse{uploads,tasks,parsed_documents,recent_tasks}` | ✅ `c8bad73` | **404** |
| 首页 / 系统监控 | 组件健康五态 | GET | `/api/system/health` | 无 | `HealthResponse{status,components}` | ✅ `c8bad73` / `cf28557` | **404** |
| 全站联调 | 运行期能力探测 | GET | `/api/openapi.json` | 无（需 Bearer Token） | `app.openapi()`（paths / info.version） | ✅ `18e2f28` | **404** |

**统计口径**：离线 OpenAPI **22 个唯一路径**（复用 8 + 新增 14，其中 `/api/parse/tasks` 是复用路径上新增 GET 方法）＋ **1 个**不进入公开 schema 的认证探测端点；`CONTRACT_ROUTES` 按方法/路径组合列举 **24 行**（legacy 9 + new 15，`GET/HEAD /source` 合并为一行）。前端调用的全部 URL 字面量均已逐条核对，无契约外路径。

---

## 3. 逐页改造与提交记录

| 页面 | 接入的真实能力 | 移除的 DEMO / 假能力 | commit |
|---|---|---|---|
| 基线归档 | 备份、`.gitignore` 安全边界、映射矩阵 | — | `c23f011` |
| 全站 API 层 | 唯一 Axios、统一错误、`useAsyncData`、`AsyncPanel`、运行期契约探测、`/source` 适配、受控 `MrProTable` | 静态能力开关、localStorage Token | `18e2f28` |
| 文档管理 `/documents` | 列表/详情/解析历史/原件下载/重新解析/真实上传进度 | 假 SHA256、DEMO 列表、后端不支持的时间区间与任意排序 | `cf1d3d1` |
| 智能解析 `/parsing` | 真实任务列表、2s 轮询、终止态停止、卸载 abort、幂等键、真实引擎字段 | 模拟进度百分比、虚构阶段日志、DEMO 任务表 | `d87b3a5` |
| 文档审核 `/review` | 真实队列/详情/原件预览/按页关联/质量指标/候选对照 | 「已记入待办」假成功；4 个写操作全部禁用 | `614d537` |
| 知识库入库 `/knowledge/ingestion` | 两类 Chunk 预览、版本列表与详情、路由参数回填 | 七阶段流水线、批次四态、法规表、入库记录抽屉、kb_version 假阻断 | `7b8fe74` |
| 法规检索 `/knowledge/search` | 真实 keyword/hybrid 检索、法条原文纯文本展示、unpublished 区分 | 伪造法条、禁用输入框、假筛选器 | `15e40a1` |
| 首页工作台 `/dashboard` | 真实统计/趋势/引擎分布/最近任务/健康五态 | 6 卡 DEMO 统计、假成功率、假待办清单、假入库记录 | `c8bad73` |
| 系统监控 `/system` | 真实健康五态、运行期契约探测元数据、24 行契约清单 | 静态组件表、DEMO 审计日志、旧 9/11 接口计数 | `cf28557` |
| 联调配置 | `preview.proxy` 同源转发、发布状态文案校准 | 产物中的本地开发地址 | `6ecb2ae` |

---

## 4. 统一请求层与异常体系

- **唯一实例**：`src/api/client.ts`，`baseURL: '/'`，超时 30s，请求拦截器统一注入 `Authorization: Bearer <token>`；未新建第二套请求层。
- **认证**：Token 仅内存 + `sessionStorage`，启动时清理历史 `localStorage.mrp_api_token`；浏览器不接触 MinerU Key / DB 口令 / DSN。
- **错误归一化**：`src/api/errors.ts` 将 `401/403/404/409/413/415/416/422/429/500/502/503/504`、取消与超时映射为 `ApiErrorKind`；`NEW_API_MARKERS` 把新接口 404 判为 `outdated`（活动实例未加载契约）而非业务对象不存在；`SENSITIVE` 正则掩码凭证/连接串文案。
- **统一状态**：`useAsyncData<T>()` 负责契约前置探测、请求取消（`AbortController`）、Loading/Empty/Error 判定；`AsyncPanel.vue` 统一渲染 `loading / empty / error / no-permission / outdated / unavailable`，每个异常态均带重试入口。七个页面全部使用（AsyncPanel 命中 3–7 处/页）。
- **幂等与并发**：`POST /api/parse/tasks` 强制 `Idempotency-Key`；预览/检索/列表按 loading 防重复提交；页面卸载或作用域销毁自动 abort；解析轮询终止态停止并保留手动重试。
- **代理**：`vite.config.ts` 的 `server.proxy` 与 `preview.proxy` 共用同一 `/api` 规则，目标可用 `VITE_API_PROXY_TARGET` 覆盖；生产产物零硬编码本地地址。

---

## 5. 真实性治理结果

| 治理项 | 结果 |
|---|---|
| 页面 Mock / DEMO 引用 | **7 个 view 全部为 0**（`grep -rn "api/mock\|DemoBadge" src/views/*.vue` 无命中）；`src/api/mock/**` 仅作隔离模块保留，`dataSource.ts` 保留 deprecated 兼容导出供编译 |
| 不可信内容渲染 | **无实际 `v-html`**；Markdown、表格、JSON、法条原文均用 `<pre>` 纯文本 |
| 审核写入 | `REVIEW_WRITE_AVAILABLE=false`、`review_write_supported` 恒 false；4 个写按钮全部 `disabled`，无「已记入待办」类假成功 |
| 正式入库 | 批次/发布/回滚/precheck/version-check 全部禁用或空态；预览 `write_performed` 若返回 `true` 会触发红色异常告警 |
| 法规原文 | 仅渲染后端 `article_text`；`status=unpublished` / 空列表 / 错误分别呈现，零伪造法条或结论 |
| 统计口径 | `uploads`（全量）/ `tasks`（窗口内）/ `parsed_documents`（全历史）分开呈现，**禁止相加**；`available=false` 或 `null` 显示「暂无数据」而非 0；`status_distribution` 之和与 `tasks.total` 不一致时显示真实告警 |
| 健康五态 | 仅按后端 `state` 归一化；本地模型仅文件检查、MinerU 仅配置检查，不把 HTTP 200 当作推理/云端在线 |
| 身份边界 | 上传 `file_id` ≠ 任务文件 `files[].file_id`；`document_id` / `database_parse_id` 各司其职；映射只取自 `file_mappings` 与解析历史，禁止拼接推导 |
| 原始文件 | 只走带认证的 `/source` → `ArrayBuffer` → Blob URL；PDF iframe / 图片 `<img>` / DOCX 仅授权下载；`artifact.bin` 明确为解析产物而非原件；卸载 `revokeObjectURL` |

---

## 6. 测试与验证结果

| # | 验证项 | 命令 / 方法 | 结果 |
|---|---|---|---|
| 1 | TypeScript 类型检查 | `npm run typecheck`（每页提交前均执行） | ✅ EXIT=0，0 错误 |
| 2 | 生产构建 | `npm run build` | ✅ `built in ~9s`；仅有已知 Element Plus/ECharts >500 kB 非阻断警告 |
| 3 | 路由检查 | 读 `router/index.ts` + preview 逐路径 curl | ✅ 7 业务路由 + `/login` + `/` 全部 200 |
| 4 | 懒加载产物 | 8 个 `*View-*.js` chunk + entry chunk curl | ✅ 全部 200 |
| 5 | 生产产物本地地址 | `grep -rl "127.0.0.1:8180" dist/` | ✅ 无命中（文案中的本地地址已移除） |
| 6 | API 契约一致性 | 逐条核对 `frontend.ts` / `parse.ts` / `documentFiles.ts` URL 字面量 vs `CONTRACT_ROUTES` | ✅ 零契约外调用 |
| 7 | Mock / DEMO / v-html 扫描 | `grep -rn` 全量扫描 | ✅ 见第 5 节 |
| 8 | 敏感信息与忽略规则 | 每页 `git diff` 敏感词扫描 + `git ls-files` 违禁文件扫描 | ✅ 无命中；`.env.example` 为基线占位文件、无真实凭证；`node_modules`/`dist`/`.env`/DB/日志/上传文件均未入库 |
| 9 | Token 存储 | `grep` client.ts | ✅ 内存 + sessionStorage，含旧值清理 |
| 10 | 代理转发 | preview 4173 → `/api/parse/info` 与直连 8180 对比 | ✅ 两侧同为 `401 application/json`；新接口两侧同为 404；SPA 路由不受影响 |
| 11 | 运行期契约探测 | curl 8180 全端点 | ❌ 见下节，全部新接口 404 |
| 12 | ESLint | `package.json` 未配置 ESLint、无配置文件 | ⚠️ 不适用（未新增依赖/配置） |
| 13 | 浏览器渲染 / 控制台 / 截图 | 当前会话无浏览器自动化工具，且后端未就绪 | ⚠️ **本轮未执行**，不谎称通过；见第 7 节 |

**8180 实测明细（无 Token）**：`/` 200（旧版工作台 HTML）、`/openapi.json` 404（后端 `openapi_url=None`）、`/api/openapi.json` 404、`/api/parse/info` 401、`POST /api/parse/tasks` 401、`GET /api/parse/tasks` 405；`/api/documents`、`/api/system/health`、`/api/stats/overview`、`/api/knowledge/versions`、`/api/review`、`/source`、`POST /api/knowledge/search` 全部 **404**。

---

## 7. 每页三场景验证矩阵

| 页面 | 正常有数据 | 无数据 | API 错误 |
|---|---|---|---|
| 文档管理 | 代码路径已实现，运行期未验证 | `AsyncPanel` empty 分支已实现，运行期未验证 | ✅ 404/401 实测；`outdated`/`no-permission` 分支已实现 |
| 智能解析 | 代码路径已实现，运行期未验证 | 空列表分支已实现，运行期未验证 | ✅ 405/401 实测；轮询异常停止并保留重试 |
| 文档审核 | 代码路径已实现，运行期未验证 | 队列/详情空态已实现，运行期未验证 | ✅ 404/401 实测 |
| 知识库入库 | 代码路径已实现，运行期未验证 | 预览/版本/详情空态已实现，运行期未验证 | ✅ 404/401 实测；409 门禁失败按错误态呈现 |
| 法规检索 | 代码路径已实现，运行期未验证 | 空列表 / `unpublished` 两种空态已实现，运行期未验证 | ✅ 404/401 实测；429/503 由统一错误模型呈现 |
| 首页工作台 | 代码路径已实现，运行期未验证 | 图表/表格空态与「暂无数据」已实现，运行期未验证 | ✅ 404/401 实测 |
| 系统监控 | 代码路径已实现，运行期未验证 | 组件空态已实现，运行期未验证 | ✅ 404/401 实测；契约探测失败显示 `outdated` 并给重试 |

**如实说明**：由于活动实例未加载契约且无 Token，「正常有数据」「无数据」两类场景**无法通过真实响应验证**；本轮不以 Mock/拦截响应凑测试（用户明确禁止创建虚假接口响应冒充成功）。浏览器端的渲染、控制台与截图回归亦未执行（当前会话无浏览器自动化工具）。这三项是 `PARTIAL` 的直接原因，需在授权后补齐。

---

## 8. 完整业务链路联调状态

| 环节 | 前端入口 | 真实接口 | 状态 |
|---|---|---|---|
| ① 上传原始文件 | 文档管理拖拽/批量上传 | `POST /api/parse/files` | 代码就绪；运行期 401（需 Token） |
| ② 创建解析任务 | 文档管理「重新解析」/ 解析中心 | `POST /api/parse/tasks` + `Idempotency-Key` | 代码就绪；运行期 401 |
| ③ 任务状态轮询 | 解析中心 2s 轮询 | `GET /api/parse/tasks/{id}` | 代码就绪；运行期未验证 |
| ④ Chunk 结构预览 | 解析中心「Chunk 预览」→ 入库页 `?task=&file=` | `POST /api/parse/tasks/{id}/files/{file_id}/preview` | 跳转回填已实现；接口 404 |
| ⑤ 待复核队列 / 详情 | 审核中心 | `GET /api/review`、`/api/review/{parse_id}` | 代码就绪；接口 404 |
| ⑥ 原件对照 | 审核中心左栏 | `GET /api/parse/files/{source_file_id}/source` | 代码就绪；接口 404 |
| ⑦ 审核写入 | — | **无接口** | 断点：4 个按钮禁用，链路合法中止 |
| ⑧ 正式入库 / 发布 / 回滚 | — | **无接口** | 断点：入库页只读，链路合法中止 |
| ⑨ 版本与检索 | 入库页版本列表 / 法规检索 | `/api/knowledge/versions`、`POST /api/knowledge/search` | 代码就绪；接口 404；无 ACTIVE 版本时显示 `unpublished` |

链路在⑦⑧处按契约「明确不支持」合法中止，前端不伪造审核通过或入库成功，不写数据库。

---

## 9. 缺失接口清单（反馈 Codex Fix）

| 优先级 | 缺失接口 | 对应业务 | 前端当前处理 |
|---|---|---|---|
| P0 | `POST /api/review/{parse_id}/approve` | 审核通过 | 按钮禁用 |
| P0 | `POST /api/review/{parse_id}/reject` | 退回重新解析 | 按钮禁用 |
| P0 | `POST /api/review/{parse_id}/mark-error` | 标记识别错误 | 按钮禁用 |
| P0 | `POST /api/review/{parse_id}/save-revision` | 保存人工修订（含审计留痕、不覆盖原始证据） | 按钮禁用 |
| P1 | `POST /api/ingestion/batches` | 正式入库批次 / 批次授权 / 重复批次检查 | 「发起入库批次」禁用 |
| P1 | `POST /api/ingestion/publish`、`/rollback` | ACTIVE 发布与回滚 | 不开放 |
| P1 | `GET /api/parse/tasks/{task_id}/logs` | 结构化解析阶段日志 | 日志抽屉只展示 `public(task)` 真实字段 |
| P1 | `GET /api/system/resources`、`/api-logs`、`/error-logs`、`/audit-logs` | 资源与三类日志 | 空态，不展示演示记录 |

> 另需后端/QA 按既有授权流程发布 public ACTIVE 版本，检索页才会返回 `status=ready`；前端不自动填充 public，也不写库。

---

## 10. 阻塞项与责任方

| 阻塞项 | 影响 | 责任方 |
|---|---|---|
| 8180 活动容器仍为 v0.2.1 旧镜像 | 全部 v0.2.2 新接口 404，无法完成真实联调 | **用户授权**切换候选镜像；切换前需检查活动任务、备份任务库、准备旧镜像回滚 |
| 未提供 ≥32 位联调 Token（`PARSING_API_TOKENS_JSON`） | 所有 `/api/*` 返回 401，无法验证 owner 隔离 | **用户**提供测试凭证 |
| 无浏览器自动化工具 / 后端未就绪 | 页面渲染、控制台、截图与「有数据/无数据」场景未回归 | 环境补齐后由前端执行 |
| 审核写入、入库发布/回滚、日志与资源接口 | 业务链路在⑦⑧中止 | 后端后续迭代 |
| public ACTIVE 版本未发布 | 检索只能返回 `unpublished` | 后端/QA 授权流程 |

---

## 11. 授权后的联调步骤（用户确认后执行）

1. 用户明确授权切换 8180 候选镜像；切换前记录当前容器/镜像 revision，完成任务库备份与回滚准备。
2. 用户提供 ≥32 位测试 Token；在系统监控页「保存并验证」写入会话（不写 localStorage）。
3. 启动 `npm run dev`（5173）或 `npm run preview`（4173，两种模式均已配置 `/api` 同源代理；如需指向候选端口设置 `VITE_API_PROXY_TARGET`）。
4. 确认 `GET /api/openapi.json` 返回 `info.version=0.2.2-api-candidate` 且包含 `/api/documents`、`/api/system/health`；系统监控页契约标签变为「契约就绪」。
5. 按第 7 节矩阵逐页验证三场景；按第 8 节链路走一遍 ①→⑨；抽查 PDF/图片/DOCX 原件预览与 `X-SHA256` 校验、审核写按钮禁用态、检索无命中与 `unpublished`、统计 `available=false`。
6. 全部通过后更新 `src/config/release.ts` 的 `frontendIntegrated=true` 与 `shortLabel`，重新生成本报告并将结论改为 `FRONTEND_INTEGRATION_READY`。

---

## 12. 安全与合规

- 未修改任何后端源码、数据库、模型、OCR 流程；未切换 Docker 镜像；未 Push / Merge；未调用 MinerU 云端。
- Token 不长期保存；错误文案掩码 `token|api_key|password|secret|bearer|dsn|postgres|pg_`；浏览器不接触任何服务端密钥。
- `.gitignore` 覆盖 `node_modules`、`dist`、`.env*`、`*.pem/key/p12/pfx`、`*secret*`、DB、日志、`local/`、`uploads/`、`sources/`、`artifact.bin`；`git ls-files` 复核无违禁文件。
- 不可信内容零 `v-html`；`/source` 走认证 Axios，不把带鉴权要求的接口地址塞进无请求头 iframe。
- 所有提交均执行 `git diff --check` 与敏感词扫描；工作区当前干净。

---

## 13. 交付物

- **源码**：`frontend/src/`（API 层、7 个 view、共享组件、布局、路由、样式、配置）。
- **文档**：`frontend/docs/frontend-api-mapping-v0.2.2.md`（接口映射矩阵）、`frontend/docs/frontend-api-integration-report.md`（本报告）、以及既有的 `frontend-api-mapping.md`、`backend-api-requirements.md`、`frontend-optimization-report.md`、`frontend-api-integration-update-2026-11-11.md`。
- **提交**：`c23f011`、`18e2f28`、`cf1d3d1`、`d87b3a5`、`614d537`、`7b8fe74`、`15e40a1`、`c8bad73`、`cf28557`、`6ecb2ae`（均在 `feat/frontend-api-v0.2.2`，本地）。

---

## 14. 未完成 / 未验证事项（明确列出）

1. 活动 8180 实例未切换，22 个新路径 + 认证探测端点全部未在运行期生效。
2. 无 Token，owner 隔离与鉴权行为未在浏览器端验证。
3. 浏览器渲染、控制台错误、响应式截图回归未执行。
4. 每页「正常有数据 / 无数据」两类场景未通过真实响应验证。
5. 审核写入、正式入库/发布/回滚、结构化日志、资源监控、审计日志接口后端未实现。
6. `ESLint` 未配置（项目无 ESLint 依赖与配置，本轮未新增）。
7. 构建存在 Element Plus / ECharts 大包非阻断警告，未做代码分割（本轮范围外）。

---

## 15. 状态标记

```
FRONTEND_INTEGRATION_PARTIAL
```

前端代码、类型、构建、路由、代理、安全与真实性治理均已完成；**真实接口成功调用并验证**这一 READY 必要条件尚未满足，阻塞项为「活动镜像切换授权」与「联调 Token」，二者均由用户控制，前端不得自行绕过。
