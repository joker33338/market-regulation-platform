# 前端第四轮优化报告（业务真实性 · 接口集成 · 安全）

> 日期：2026-11-10
> 项目：`F:\刘凯工作\market-regulation-platform-frontend\frontend`
> 分支：`feat/frontend-v0.2.1` @ `f4a0af8`（基于 `codex/fix-v0.2.1`）
> 用户决策：**现在开展前端优化，接口后续提供再接入真实数据**
> 边界：仅修改 `frontend/`，后端 `qa_core/**` 与 QA 工作区零改动；无 commit / merge / push / 部署

---

## 1. 七个页面优化报告

| 页面 | 本轮改动 | 真实性处理 |
|---|---|---|
| 首页工作台 | 6 张统计卡改从单一快照取值、新增统一口径说明条与一致性自检；成功率显示分子分母；组件状态改五态；补 1366/1920 断点 | 统计一律 DEMO（后端无统计接口）；只有 FastAPI 由 `/api/parse/info` 真实探活 |
| 文档管理 | 上传契约改为**原始二进制流**（原 FormData 必 415）；新增后缀/100MB/魔数/批量≤20 预校验、逐文件进度与失败原因；SHA256 一律用后端返回；前端 SHA256 仅做重复识别；新增「本次会话真实上传」REAL 表与创建解析任务；接入 `MrProTable` | 列表/搜索/筛选/分页为 DEMO 并标注；下载、重新解析按钮禁用并说明缺失接口 |
| 智能解析中心 | 展示 `/api/parse/info` 真实配置；新增创建解析任务（最小白名单 + `Idempotency-Key`）；真实任务按 ID 查询 + 2s 轮询（终止态停止、卸载清理）；接入 results / errors / artifact 下载；错误从 `files[].error` 呈现 | 引擎面板状态固定 UNKNOWN（无探活接口），统计来自统一快照；DEMO 任务的重试/取消禁用；引擎选择只展示后端 `selected_engine` |
| 文档审核中心 | 左侧换 `DocumentPreview`（唯一文件源 = `documentFiles.ts` 适配层），右侧与左侧共享 `currentPage` 按页对照；5 个结果 Tab；元信息条 | **4 个审核写操作全部 disabled**；删除原「已记入待办」假成功；预览显示明确未接入态，不模拟页面、不用 artifact.bin 冒充；解析文本改占位内容，不含法规原文 |
| 知识库入库管理 | 新增 kb_version 不一致**整批阻断横幅**、入库前检查清单（阻断项标红）、批次四态（已完成/执行中/失败/阻塞）、错误详情 | 「发起入库批次」禁用并说明；页面明确「无真实入库 API，不执行任何数据库写入」 |
| 法规知识检索 | 检索输入/按钮/筛选器全部禁用；新增结果字段契约说明与四种检索模式说明 | **删除全部伪造法条原文**；明确显示「未检索到相关依据（检索接口未接入）」；不生成任何法规结论或相关度分数 |
| 系统监控 | 组件五态表；移除后端不返回的 `version/environment` 伪字段，改展示 `/api/parse/info` 真实字段；新增系统资源/接口调用/错误日志「接口未接入」空态；Token 安全说明 | 仅真实探测成功标 ONLINE；审计日志与三个新模块标 DEMO |

登录页同步更新 Token 存储与生产会话说明。

---

## 2. API 接口映射表

独立文档：`docs/frontend-api-mapping.md`（页面 / 路径 / 方法 / 请求参数 / 响应字段 / 已实现 / 已接入 / 是否 Mock，含 6 条契约陷阱）。
后端交付清单：`docs/backend-api-requirements.md`（12 组接口规格 + 跨接口约定 + QA 验收清单）。

**事实来源**：后端 `openapi_url=None`（实测 `/openapi.json`=404），映射以 `mineru_api.py` 路由源码 + 内置 `parsing_upload.html` 为准，未猜测接口。

---

## 3. 真实 API 接入数量

**9 个真实请求函数全部按源码契约修正并接入**（`src/api/parse.ts`）：

| 接口 | 修正点 |
|---|---|
| `GET /api/parse/info` | 类型改为真实 5 字段，去掉 version/environment 伪字段 |
| `POST /api/parse/files` | **FormData → File 原始流**（后端读 `request.stream()` + 魔数校验），响应改 `{file_id, sha256, bytes}` |
| `POST /api/parse/tasks` | 去掉白名单外 `mode`；返回类型改完整 `public(task)`；必带幂等键 |
| `GET /api/parse/tasks/{id}` | 真实查询 + 轮询 |
| `GET /api/parse/tasks/{id}/errors` | 明确返回 `public(task)` 而非错误数组 |
| `POST /api/parse/tasks/{id}/resume`、`/cancel` | 仅对真实任务启用 |
| `GET /api/parse/tasks/{id}/results` | 标准化结果查看 |
| `GET /api/parse/tasks/{id}/files/{file_id}/artifact` | 去掉后端不识别的 `kind`，改 `arraybuffer` 二进制接收，明确为**解析产物非原始文件** |

另有 1 个无鉴权根页面 `GET /` 未使用。

---

## 4. Mock 接口数量 / 未接入清单

- **Mock 数据模块 8 个**：新增唯一统计源 `mock/stats.ts`；`dashboard / parsing / documents / review / ingestion / search / system` 全部收敛到 `dataSource.ts` 的 `apiCapabilities` 开关与 `demoResult()` 统一来源标记。
- **能力开关**：20 项能力中 9 项 `true`（真实接口），11 项 `false`（待交付）。
- **未接入接口 11 组**（详见 `docs/backend-api-requirements.md`）：原始文件 source（P0）、文档列表（P0）、审核读写 4 个（P0）、文档详情/解析历史、任务列表、任务日志、引擎状态、统计聚合、入库 5 接口、知识检索、系统健康与日志；另有 P2 建议开放非生产 OpenAPI。

---

## 5. PDF / Word 预览实现结果

**结论：接口未接入，未启用真实渲染（合规，不伪造）**。

- 已交付 `src/api/documentFiles.ts`：全站唯一文件源适配层，接口未交付时返回 `NOT_AVAILABLE`；接口到位后只需替换该函数实现 + 把 `sourceFileAvailable` 置 `true`。
- 已交付 `src/components/document/DocumentPreview.vue`：页码跳转、上下页、缩放、缩略图、按页关联的完整交互骨架；未接入时显示明确提示与所需接口路径，控件全部禁用。
- **未引入** `pdfjs-dist` / `@vue-office/docx`：无原始文件来源时无法验证真实渲染，且用户未批准新增依赖；研究报告已核过许可证（Apache-2.0 / MIT）与纯 JS 约束，接口交付后可立即引入。
- 严格遵守：不用 `artifact.bin` 冒充原始证据，不提供本地选文件预览，不渲染模拟页面。

---

## 6. Token 安全改进结果

| 项 | 改进 |
|---|---|
| 存储 | `localStorage` → **内存优先 + sessionStorage 会话级**，关闭标签页失效；启动时清除历史版本写入的 localStorage 旧 Token |
| 日志 | 不打印 Token；响应错误文案含 token/key/password 关键字时自动降级为通用提示 |
| 浏览器密钥 | 只发 `Authorization: Bearer` 到 FastAPI；MinerU API Key / DB 口令仅在后端；Vite 代理 `/api` → `127.0.0.1:8180` |
| 环境区分 | 系统监控与登录页明确「开发期手工 Token + 会话存储」/「生产用服务端安全会话（HttpOnly Cookie / BFF）」 |

---

## 7. 数据统计一致性检查

- 唯一快照 `mock/stats.ts`，统一近 14 天口径：
  `任务总数 1104 = 成功 1053 + 失败 51 + 执行中 0`；`文件数 1286` 独立统计，不与任务数相加。
- 引擎分布 `712 + 306 + 86 = 1104`；成功 `689+286+78 = 1053`；失败 `23+20+8 = 51`。
- 成功率改为按分子分母计算（96.8% / 93.5% / 90.7%），不再是手写的矛盾值 91.2%。
- 趋势序列改为固定值（去掉 `Math.random()` 导致的刷新跳动），14 天 parsed 合计 1053、failed 合计 51。
- `statsConsistencyIssues()` 提供运行期自检，异常时工作台顶部显示红色告警。
- 首页「解析成功 1104 / 失败 23」的错误已消除。

---

## 8. 构建结果

| 项 | 结果 |
|---|---|
| `npm run build` | ✅ 通过，8.90s（Vite 4.5.14） |
| `npm run typecheck`（本轮新增 `tsc --noEmit`） | ✅ 0 错误 |
| 依赖 | **未新增、未升级任何依赖**（Vue 3.5 / Vite 4.5 / Element Plus 2.14 保持不变） |
| 已知非阻断告警 | ECharts 造成单 chunk >500KB；未做 manualChunks 拆分 |
| 类型检查覆盖 | `tsc --noEmit` 只覆盖 `.ts`；`.vue` 未纳入（需 `vue-tsc`，本轮未新增依赖，如实说明） |

---

## 9. 前端测试结果

| 项 | 结果 |
|---|---|
| 7 条业务路由 + 直接访问/刷新 | ✅ preview 下逐路由直访均 200 且正常渲染（history fallback 正常） |
| 1920×1080 截图 | ✅ 8 张（含登录页） |
| 1366×768 截图 | ✅ 4 张（工作台/文档/解析/审核），统计卡自动 3×2，无横向溢出 |
| DOM 渲染检查 | ✅ 7/7 页面渲染成功（审核页根为 `page review-page`，截图确认正常） |
| 控制台错误 | ✅ 7 个页面均无 uncaught / console error |
| 空数据 / 异常 / 加载态 | ✅ MrProTable 空态与加载态、检索空结果、入库阻断态、解析未探测态 |
| 重复提交防护 | ✅ `Idempotency-Key` + `submitting` 锁 + 批量数量限制 |
| 任务轮询 | ✅ 2s、终止态停止、150 次上限、`onBeforeUnmount` 清理 |
| 写操作禁用 | ✅ 审核 4 项、入库 1 项、检索 1 项、文档下载/重新解析 2 项 |
| 后端改动 | ✅ 零（`git status` 仅 `?? frontend/`） |

截图目录：`E:\WorkBuddy\基本工作\market-regulation-frontend-screenshots\`

---

## 10. 待完善事项（接口交付后）

1. **P0** `GET /api/parse/files/{file_id}/source` → 启用 `DocumentPreview` 真实渲染（需批准引入 `pdfjs-dist@4.10.38` Apache-2.0、`@vue-office/docx@1.6.3` MIT、`vue-demi` MIT）。
2. **P0** 审核读写接口 → 解除 4 个按钮禁用，实现修订版本追加与审计留痕。
3. **P0** 文档列表接口 → 把 `MrProTable` fetcher 从 DEMO 切到真实请求，无需改表格结构。
4. **P1** 统计 / 任务列表 / 引擎状态 / 入库批次 / 知识检索 / 健康检查 → 逐项把 `apiCapabilities` 置 `true` 并补适配实现。
5. 工程：如需 `.vue` 模板类型检查可新增 `vue-tsc`；ECharts 可用 `manualChunks` 拆包；可补 ESLint / 单元测试（本轮未引入以避免无关依赖）。
6. 前端目录整体 untracked，建议由用户确认后提交一次基线（本轮未自动提交）。
7. 后端 MVP 已通过有限范围 QA（2026-11-11 PASS），但不含独立前端全联调；全局警示改为「后端 QA PASS · 前端待联调」，仍不得对外宣称整套系统正式可用。

---

## 11. 追加更新：2026-11-11 QA PASS 后的接口复核

用户告知 v0.2.1 审查已通过并要求「对接口整体接入与更新」。核实后确认：**QA PASS 为真，但后端没有新增任何 HTTP 接口**，故本轮为状态与契约更新，不是新接口接入。

### 11.1 复核事实

- QA 裁决 `docs/qa/v0.2.1/final-release-decision.md`（`843c64d`）结论 PASS，范围明确排除「独立前端全部联调」与生产部署。
- 四个提交 `f4a0af8`（前端基线）、`3129479`（Fix 交接）、`843c64d`（QA）、`5dd44b9`（发布归档）的 `mineru_api.py` 路由定义**逐行一致，仍是 9 个 API**；diff 仅 3 处注释中文化，契约零变化。
- 全仓仅一个 `FastAPI(...)`；`deploy/local/entrypoint.py` 是 uvicorn 启动器，`qa_core/indexing/preview.py` 是非 HTTP 的只读切分预览。
- 在线 8180 探测：`/openapi.json`、`/api/documents`、`/api/system/health`、`/api/stats/overview`、`/api/parse/engines/status`、`/api/ingestion/batches`、`/api/knowledge/search`、`/api/review/*` 全部 404。

### 11.2 本轮改动

| 文件 | 改动 |
|---|---|
| `src/config/release.ts` | **新增**：发布状态唯一事实来源（QA 结论、日期、范围、短标签、告警文案、契约复核结论） |
| `src/layout/AppLayout.vue`、`src/views/DashboardView.vue` | 短标签由「v0.2.1 未验收」→ 统一常量 `后端 QA PASS · 前端待联调` |
| `src/views/LoginView.vue`、`src/views/SystemView.vue` | 告警改用统一常量，明确 PASS 范围不含前端全联调与生产部署 |
| `src/stores/app.ts`、`src/api/parse.ts`、`src/api/dataSource.ts` | 注释与基线标注更新；明确「QA PASS ≠ 接口交付」，11 个 false 能力开关不动 |
| `src/views/SystemView.vue` | **新增「接口接入状态总览」**：9 个已接入 / 11 组待交付，计数取自 `apiCapabilities`，列出方法、路径、使用页面、优先级与解锁能力；明确「仅反映源码事实，非运行期探测」 |
| 三份 docs | 新增复核章节 / 状态更新，详见 `frontend-api-mapping.md` §6、`backend-api-requirements.md` §0.1 |

### 11.3 数量与结论

| 指标 | 上轮 | 本轮 |
|---|---|---|
| 真实 API 接入数 | 9 | **9（无变化）** |
| Mock / 未接入能力 | 11 组 | **11 组（无变化）** |
| 已解除禁用的写操作 | 0 | **0（禁用原因是接口不存在，与 QA 无关）** |
| 页面上可自查的接口清单 | 无 | 系统监控页新增总览 |

**未做也不应做的事**：没有把任何 DEMO 标成 REAL、没有启用写按钮、没有伪造预览、没有把 QA PASS 写成「正式可用」、没有同步/合并后端分支、没有 commit / push / 部署。

**真正接入的前提**：后端交付 P0 三组（原始文件 `/source`、文档列表、审核读写 5 个）+ 提供 ≥32 位联调 Token；届时改适配层并置 `apiCapabilities`，页面无需重做。
