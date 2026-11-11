# v0.2.2 前端真实 API 联调交付报告

> 生成日期：2026-11-11（GMT+8）
> 交付角色：WorkBuddy（Vue 3 前端开发与真实 API 联调）
> 报告性质：按任务书要求生成的**正式交付入口**；逐页证据与浏览器联调记录见 `frontend/docs/frontend-api-integration-report.md`，接口矩阵见 `frontend/docs/frontend-api-mapping-v0.2.2.md`。
> 脱敏声明：本报告不含会话凭证、MinerU Key、数据库 DSN、绝对机器路径、原始语料名称与正文。

---

## 0. 最终结论

```
FRONTEND_INTEGRATION_READY
```

**结论范围（必须与范围一并引用）**：七个页面的**约定只读能力**已接入 Agent C 交付的真实 FastAPI 接口，并在真实运行服务、真实会话凭证下完成端到端请求验证；业务数据全部来自后端真实响应，无 Mock / DEMO 回退、无伪造成功、无随机生成记录。

此结论**不覆盖**：写链路端到端执行（上传 / 创建任务 / 恢复 / 取消）、正式审核写入、入库构建与正式发布 / 回滚、独立 QA 验收、生产部署、MinerU 云端推理与大规模性能验证。这些均按 §8、§9、§10 如实列出，不以 READY 名义掩盖。后端自评仍为 `BACKEND_API_PARTIAL`，本报告不代表 QA PASS 或生产可用。

> 2026-11-11 14:46 补充：按「全体 Agent 统一规则」新增 §1.3 **统一后端运行镜像身份**（后端源码 SHA / 镜像 ID / 标签 / OCI revision / 运行容器 / 8180 实际服务身份），供 Agent C、Fix、QA 与前端共用同一被测版本基线。本次补充只涉及文档，未改动业务源码、运行镜像或共享服务。

---

## 1. 基线与身份（完整 SHA）

### 1.1 Git / Worktree 关系（已核实）

前端与后端**共享同一 Git 仓库**，通过多个 worktree 并行开发；前端工作区是其中一个 worktree，前端工程位于该 worktree 的 `frontend/` 子目录（已被跟踪，不是未跟踪目录）。原有页面、前端备份与未提交成果均未覆盖或删除。

| 项 | 值 |
|---|---|
| 前端分支 | `feat/frontend-api-v0.2.2` |
| **前端完整 SHA（联调代码最终态）** | `5d83b13f4132464ddb764501967bc50992778062` |
| **前端完整 SHA（报告收口提交 / 本次镜像身份补记前 HEAD）** | `688b824213a4489e2f1ce1577677b341f2c10792` |
| 前端维护基线 | `5dd44b97710db0d3bdb84bcec6e1624dd70205dc` |
| 本轮前端提交数 | 14 个本地提交（13 个联调 + 1 个报告收口；本次镜像身份补记另计，均未 Push / 未 Merge / 未部署） |
| 前端工作区状态 | 干净；`node_modules`、`dist`、`.env`、备份均不入库 |
| **后端契约分支完整 SHA** | `20bfeef57e101f08a2f37bd4a73b6ed4237dcba5`（`feat/backend-api-v0.2.2`，原始工程 worktree） |
| **Agent C 接口实现分支完整 SHA** | `712521429bb39e10b00730e139ccb4889dd2e555`（`codex/backend-api-v0.2.2`，独立 worktree，作为阶段记录保留） |
| **8180 运行 revision（完整 SHA）** | `4fc4cf124a120762593064676ea5f8dbe2394119` |
| 运行镜像 / 容器 | `market-regulation-workbench:candidate-v022-4fc4cf124a12` / `market-regulation-app-1`（healthy，`127.0.0.1:8180->8180/tcp`）；**完整镜像身份见 §1.3** |
| 正式契约 | `docs/integration/frontend-api-contract.md`，契约版本 `frontend-api-v0.2.2-1` |
| 后端缺口自评 | `docs/integration/frontend-api-gap-report.md` → `BACKEND_API_PARTIAL` |
| 运行交接 | `docs/integration/v0.2.2-local-runtime-handoff.md`（28 项定向测试 + 9 项真实认证只读冒烟通过） |

> **三者不可混同**：`4fc4cf1…` 是 8180 **正在运行的源码 revision**（镜像 tag 与运行交接文档双重确认）；`20bfeef…` 是契约分支**当前 HEAD**，仅比运行 revision 多一个文档交接提交，无契约变化；`7125214…` 是 Agent C 早期接口实现分支的 HEAD。上一版报告把「后端仓库 HEAD」直接写成 `4fc4cf1…`，本版已按上述口径拆分纠正。
>
> 另一处口径澄清：另一 worktree 的契约文档头部为 `frontend-api-v0.2.2-draft-1`（早期草稿）；8180 运行 revision 对应的正式契约为 `frontend-api-v0.2.2-1`。本报告统一采用后者。
>
> 本报告所在的收口提交不内嵌自身 SHA（报告无法自指）；最终交付 HEAD 由 `git log -1` 给出，并在交付说明中回报。

### 1.2 运行期契约探测

| 项 | 实测 |
|---|---|
| `GET /api/openapi.json`（带凭证） | **200**，`openapi=3.1.0`，`info.version=0.2.2-api-candidate`，**22 条路径** |
| `GET /api/openapi.json`（无凭证） | 401 `unauthorized`（鉴权中间件先拦截，说明路由已挂载） |
| `GET /openapi.json`、`/docs` | 404（后端 `openapi_url=None`，设计如此） |
| `GET /api/*`（无凭证） | 12 条关键路径一律 401，无一条 404，证明 v0.2.2 新路由已在运行实例加载 |

联调凭证复用本机 ignored 私有运行配置中的已有会话凭证，**仅在容器内使用于本地只读请求**，未写入源码、报告、截图或 Git；浏览器侧凭证只存内存 + sessionStorage。

### 1.3 统一后端运行镜像身份（全体 Agent 共享，2026-11-11 14:46 只读复核）

按「全体 Agent 统一规则」，本前端交付报告记录与 Agent C / Fix / QA **同一套 8180 运行后端**的完整身份。判定依据是**容器实际引用的镜像 ID** 与**该镜像的 OCI revision label**，不使用 `latest` 标签（本仓库无 `latest` 标签）。

| 必记项 | 值 | 证据 |
|---|---|---|
| **当前后端源码完整 SHA** | `4fc4cf124a120762593064676ea5f8dbe2394119` | 镜像 `org.opencontainers.image.revision` label，与运行交接文档一致 |
| **Docker 镜像 ID** | `sha256:8f169cd82cc1bf55807eb48a9f75e0b5206ac4cb10ca27c38fe206a85e93d7a4`（短 `8f169cd82cc1`） | 容器 `.Image` 与 `docker image inspect .Id` 完全一致；`RepoDigests` 同值（本地构建，无远端 registry digest） |
| **镜像标签** | `market-regulation-workbench:candidate-v022-4fc4cf124a12` | `RepoTags` 唯一标签；镜像创建于 `2026-11-11T03:55:28Z` |
| **OCI revision** | `org.opencontainers.image.revision=4fc4cf124a120762593064676ea5f8dbe2394119` | 镜像 label；**与运行源码 SHA 完全一致 → 镜像 ID ↔ 源码 SHA 对应关系成立**，非凭标签推断 |
| **当前运行容器** | `market-regulation-app-1`，容器 ID `de1c0271a55eb579ef43073ad3f7109732bd409bb49259087451b6f32fe401af` | `running` / `healthy` / `RestartCount=0`；启动于 `2026-11-11T05:49:06Z`；端口 `127.0.0.1:8180->8180/tcp` |
| **8180 实际服务身份** | uvicorn；`GET /api/openapi.json` → **200**，`openapi=3.1.0`、`info.version=0.2.2-api-candidate`、title `Document parsing`、**22 paths**；`GET /api/parse/info` → `provider=self_hosted, mode=local`，`enabled/database_enabled/dual_engine_enabled=true`；`GET /api/system/health` → `status=ok`、7 组件 | 容器内带凭证只读探测（凭证未输出、未落盘） |

**唯一活跃后端**：8180 端口仅一个 LISTENING；`docker ps` 中仅 `market-regulation-app-1` 提供 FastAPI，无第二套并行后端。另有已停止的历史 QA 容器 `qa-c915-2b6bfb37-app-1`（`Exited (143)`，v0.2.1 QA PASS 镜像），不占用 8180，按规则保留不动。

**依赖与数据保护现状（只读复核，未改动）**：共享 `market-regulation-db-1`（pgvector/pg16）、`market-regulation-redis-1`（redis:7.4-alpine）、`market-regulation-mysql-1`（mysql:8.4，历史保留容器，本轮业务未使用，既不引入也不删除）；模型只读挂载 `/models`、私有运行配置只读挂载 `/private/runtime.json`、可写状态 `/state` 与 `/app/reports` 均保持原样。历史镜像与 v0.2.1 QA PASS 镜像 `market-regulation-workbench:candidate-v021-c91547d393ca`（`92bc163c1521`，OCI revision `c91547d393ca6b049e216c0051e25271d06d7359`）均保留；另有未运行且无 OCI revision 的遗留镜像 `market-regulation-app:local`（`b4010953b65e`），不作为被测版本依据。

**WorkBuddy 权限边界（本轮）**：仅通过 `http://127.0.0.1:8180` 只读接入；**未**构建镜像、**未**重启或替换共享容器、**未**覆盖运行镜像、**未**删除数据卷或历史镜像、**未**清空 SQLite、**未**修改正式数据库、**未**更改 MinerU Token / 授权账本、**未**中断活动任务、**未** Push / Merge main / 部署。镜像统一构建与安全切换由 Agent C 负责；QA 执行期间镜像版本保持冻结，本角色不替换 8180 被测镜像。

> 供 QA 引用：本报告对应的被测组合为「后端源码 `4fc4cf124a120762593064676ea5f8dbe2394119` + 镜像 ID `sha256:8f169cd8…` + 前端源码 `688b824213a4489e2f1ce1577677b341f2c10792` 及其后的文档补记提交」。版本不一致时不得按本报告签发 PASS。

---

## 2. 七页面联调清单

| 优先级 | 页面 / 路由 | 真实接口 | 完成内容 | 提交 | 状态 |
|---|---|---|---|---|---|
| 基础 | 统一请求层 | 全部 `/api/*` | 唯一 Axios 实例、`ApiError` 归一化、`AsyncPanel`、`useAsyncData`、轮询可停止、请求取消 | `18e2f28` | ✅ |
| P0 | 文档管理 `/documents` | `documents`、`documents/{id}`、`parse-history`、`parse/files/{id}/source` | 上传接入、列表、分页筛选、详情、解析历史、原件预览（Blob + Range）、上传/解析错误提示；不伪造任务成功或文档记录 | `cf1d3d1` | ✅ |
| P0 | 智能解析 `/parsing` | `parse/tasks`、`/{id}`、`/errors`、`/results`、`/artifact`、`/info` | 任务查询、状态更新、OCR 引擎与回退原因、标准化结果、质量提示、失败原因、结果查看入口；2s 轮询在终止态与页面卸载时停止 | `d87b3a5` | ✅ |
| P0 | 文档审核 `/review` | `review`、`review/{parse_id}`、`/source` | 保留左右对照；左侧原始文件，右侧 OCR / 表格 / 质量异常 / 解析候选；四个写按钮全部 `disabled`（后端 `review_write_supported=false`） | `614d537` | ✅ 只读 |
| P1 | 知识库入库 `/knowledge/ingestion` | `knowledge/versions`、两类 `/preview` | 法规结构、Chunk、Parent-Child、版本信息、质量提示；严格区分预览（`write_performed=false`）/ 构建 / 正式发布，后两者禁用 | `7b8fe74` | ✅ 只读 |
| P1 | 法规检索 `/knowledge/search` | `knowledge/search` | 法规标题、条号、Chunk 内容、来源、版本信息渲染分支；无 ACTIVE 版本显示 `unpublished` 真实空态，不用测试法规伪造 | `15e40a1` | ✅ |
| P2 | 首页统计 `/dashboard` | `stats/overview`、`system/health` | 全部 DEMO 统计换真实 API；按来源分开展示，无数据显示「暂无数据」，不展示模拟图表 | `c8bad73` | ✅ |
| P2 | 系统监控 `/system` | `system/health`、`openapi.json`、`parse/info` | FastAPI / PostgreSQL / SQLite / OCR 等七组件真实状态；区分正常、异常、未检测、未配置，**未检测不显示为正常** | `cf28557` | ✅ |
| 修正 | 代理与联调后修正 | — | `preview.proxy` 补齐 `/api`、检索初始态、过时 DEMO 文案、favicon、发布状态标签 | `6ecb2ae` `96d4052` | ✅ |
| 报告 | 交接报告 | — | 先 `PARTIAL`（旧镜像阻塞），运行期联调后升级 `READY` | `d60f657` `5d83b13` | ✅ |

**页面数量核对**：任务书列出七个业务页面，全部完成；另含登录页（凭证入口）与运行期契约探测，共 9 个视图文件，无遗漏。

---

## 3. 真实请求结果（本轮复测，2026-11-11）

全部请求指向运行中的 8180，经真实认证；下表为**本轮实际发出的请求**与响应，非引用历史结论。

### 3.1 正常业务路径

| 方法 / 路径 | HTTP | 真实响应要点 |
|---|---|---|
| `GET /api/openapi.json` | 200 | `3.1.0` / `0.2.2-api-candidate` / 22 paths |
| `GET /api/parse/info` | 200 | `provider=self_hosted, mode=local, enabled=true` |
| `GET /api/documents?page=1&page_size=20` | 200 | `total=4`，`source=owner_upload_metadata+sqlite.parse_tasks` |
| `GET /api/documents/{file_id}` | 200 | `file_id/file_name/doc_type/size_bytes/sha256/uploaded_at/uploaded_at_source/status` |
| `GET /api/documents/{file_id}/parse-history` | 200 | `total=1`，`source=sqlite.parse_tasks` |
| `HEAD /api/parse/files/{file_id}/source` | 200 | 存在性确认 |
| `GET /api/parse/files/{file_id}/source` + `Range: bytes=0-15` | **206** | 16 B，`content-range: bytes 0-15/246331` |
| `GET /api/parse/tasks?page=1&page_size=20` | 200 | `total=3`，`source=sqlite.parse_tasks` |
| `GET /api/parse/tasks/{task_id}` | 200 | `status=completed`，`files=1` |
| `GET /api/parse/tasks/{task_id}/errors` | 200 | 真实错误结构 |
| `GET /api/parse/tasks/{task_id}/results` | 200 | `task_id/status/results` |
| `GET /api/review?requires_review=true` | 200 | `total=7`，`source=document_review.documents` |
| `GET /api/review/{parse_id}` | 200 | 含 `raw_text`、`quality`、`source_location`、`original_result` |
| `POST /api/parse/tasks/{t}/files/{f}/preview` | 200 | `write_performed=false`、`rag_index_written=false`、`chunks=1 / parents=1 / tables=0 / warnings=2` |
| `POST /api/review/{parse_id}/preview` | 200 | `write_performed=false` |
| `GET /api/knowledge/versions` | 200 | `total=0`，`source=public.mr_kb_versions`（**真实空态**） |
| `GET /api/stats/overview?days=14` | 200 | 三组 `source/scope` 分离，`available/total/requires_review` 真实值 |
| `GET /api/system/health` | 200 | `fastapi/task_store/postgresql=ONLINE`；`paddle_ocr/pp_structure/bge_m3/mineru=UNKNOWN` |
| `POST /api/knowledge/search`（keyword） | 200 | `status=unpublished, kb_version=null, count=0, source=public` |
| `POST /api/knowledge/search`（hybrid） | 200 | `status=unpublished, kb_version=null, count=0, source=public` |

### 3.2 空数据 / 异常态

| 场景 | 请求 | HTTP | 前端表现 |
|---|---|---|---|
| 空列表 | `keyword=__no_such_file__` | 200 `list:[]` | 正常空态，不显示 0 冒充统计 |
| 参数非法 | `page=0&page_size=999`、`days=999` | **422** `invalid_request` | `invalid` 错误态 |
| 对象不存在 | 不存在 `file_id` / 版本 | **404** `source_not_found` / `version_not_found` | `not-found`，不回退演示数据 |
| Range 越界 | `Range: bytes=99999999-…` | **416** | `limit` 错误态 |
| 产物缺失 | 历史任务 `artifact.bin` | **404** `artifact_not_found` | 「解析产物下载失败」，不假装成功 |
| 未认证 | 无凭证访问 `/api/documents` | **401** `unauthorized` | 页面零业务请求，`AsyncPanel` 显示无权限 + 重试 |
| 服务未发布 | `POST /api/knowledge/search` | 200 `unpublished` | 「知识库尚未发布」而非「未检索到相关依据」 |
| 契约未就绪 | 旧镜像时期探测 | — | `outdated` 异常态保留（本轮服务已就绪，未触发） |

> 浏览器侧联调证据（Edge headless + CDP，1440×900 七页面全量 + 1366/1920 抽查，`errors=[]` / `apiFails=[]`、无横向溢出）见 `frontend/docs/frontend-api-integration-report.md` §3–§4。
>
> QA 只读核验入口：仓库内 ignored 路径 `local/frontend-evidence/README.md`（本机截图目录、采集产物说明、采集结论出处）与 `local/frontend-evidence/evidence-manifest.json`（40 张截图 SHA256 清单）。该目录不入库、不提交；原始 CDP 事件流未落盘为 JSON，未补造或重新采集，详见索引内 `raw_cdp_capture` 字段。
>
> `409 / 413 / 415 / 429 / 503` 的真实触发需构造幂等冲突、超限文件或模型并发，可能改动业务数据或触发远程动作，本轮未执行；前端 `ApiError` 已按契约归一化这些状态码。

### 3.3 真实性边界（本轮实测值）

- 统计三组数据**不相加**：`uploads`（全量上传元数据）、`tasks`（近 14 天 SQLite）、`parsed_documents`（document_review 全历史）来源与范围不同。
- 健康：`model_ready=true` 仅表示模型文件存在，本地模型与 MinerU 一律标 `UNKNOWN`，**不把未检测显示为正常**。
- 检索 `raw_score` 的 `keyword_match` 只表示匹配、`rrf` 为融合排序分，**不是法律准确率**；不编造发布机关、法效日期、历史版本。
- Chunk 预览成功 ≠ 正式入库成功；`write_performed=false` 全链路保持。

---

## 4. Mock / DEMO 替换情况

| 检查项 | 结果 |
|---|---|
| 固定文档列表 | 已移除，改 `GET /api/documents` |
| 模拟任务 / `setTimeout` 模拟完成 | 已移除，改 `GET /api/parse/tasks` + 可停止轮询 |
| 虚假成功率 | 已移除，统计改 `GET /api/stats/overview`，`available=false` 显示「暂无数据」 |
| 模拟 OCR 结果 | 已移除，改 `results` / `review/{parse_id}` 真实响应 |
| 固定法规检索结果 | 已移除，改 `POST /api/knowledge/search`，无 ACTIVE 显示真实空态 |
| 假健康状态 | 已移除，七组件只按后端 `state` 归一化 |
| 页面对 `api/mock` 的引用 | **0**（全量 grep 仅命中 `src/api/dataSource.ts` 的一句说明性注释） |
| `src/api/mock/**` | 8 个历史模块**隔离保留**，不参与任何页面数据流；未用于正式业务模式 |
| `DemoBadge` / `v-html` | 七个页面零引用；Markdown / 表格 / JSON 按纯文本 `<pre>` 展示，不执行 HTML |
| 硬编码后端地址 | `src/**` 无 `127.0.0.1:8180`；生产 `dist/` 不含本地地址 |
| 写操作假成功 | 审核 4 按钮、入库批次 / 发布 / 回滚均 `disabled`，无「已记入待办」等假提示 |

---

## 5. 统一请求层与 API 接入规范

- 全站唯一 Axios 实例 `src/api/client.ts`，`baseURL='/'`；Bearer 凭证内存优先 + sessionStorage，清理历史 localStorage 值，错误文案对敏感词掩码。
- `ApiError` 归一化 401 / 403 / 404 / 409 / 413 / 415 / 416 / 422 / 429 / 500 / 502 / 503 / 504、取消与超时；新接口 404 识别为 `outdated`（旧镜像）而非「对象不存在」。
- `useAsyncData` 统一契约探测、`AbortSignal` 取消、页面卸载中止；`AsyncPanel` 统一 Loading / Empty / Error / Retry / No Permission / Service Unavailable / Outdated。
- `MrProTable` 受控模式，页面负责真实 API 调用；创建任务强制 `Idempotency-Key`。
- `vite.config.ts`：`server.proxy` 与 `preview.proxy` 均转发 `/api` 到 8180，支持 `VITE_API_PROXY_TARGET` 覆盖；本轮实测 `4173/api/parse/info` 返回 401，与直连 8180 一致，证明代理生效。
- 不在页面硬编码地址；不暴露 MinerU Key、数据库 DSN、密码、内部路径。

---

## 6. 构建与检查结果（本轮重跑）

| 项 | 命令 | 结果 |
|---|---|---|
| TypeScript 类型检查 | `npm run typecheck`（`tsc --noEmit`） | ✅ **0 错误**，退出码 0 |
| Vite 生产构建 | `npm run build` | ✅ **10.00s** 完成，退出码 0 |
| 构建提示 | — | 仅既存 `chunk > 500 kB` 体积警告（ECharts / Element Plus 主包），非错误 |
| 预览服务 | `npm run preview` @ 4173 | ✅ `/`、`/dashboard`、`/documents` 均 200；history fallback 正常 |
| 同源代理 | 4173 → 8180 | ✅ `/api/parse/info` 401，与直连一致 |
| 组件测试 | 项目未配置独立测试运行器；以真实 API 请求验证 + 浏览器七页面联调替代 | 见 §3 与详细证据卷 |
| Git 差异检查 | `git status --short` | ✅ 干净（收口提交前）；无 `node_modules` / `dist` / 凭证 / 业务原始文件 / 备份入库 |

---

## 7. 前端提交记录

基线 `5dd44b97710db0d3bdb84bcec6e1624dd70205dc`，本轮 14 个本地提交（按时间正序，均为本地提交，未 Push / 未 Merge / 未打 Tag）：

| # | 短 SHA | 完整 SHA | 内容 |
|---|---|---|---|
| 1 | `c23f011` | `c23f0115b60b7bec8a835882876d770ce0891c1e` | 归档 v0.2.1 前端基线，建立 v0.2.2 联调起点 |
| 2 | `18e2f28` | `18e2f2863ab034cc549f4f826c0811056b217c42` | 统一请求层、ApiError、类型契约、运行期探测、AsyncPanel / useAsyncData |
| 3 | `cf1d3d1` | `cf1d3d1f4edd2dec393cf0b3e1d5d17f4425ef2d` | 文档管理真实接口对接（P0） |
| 4 | `d87b3a5` | `d87b3a5f6ea4bd7806ba7c92932575828c5329be` | 智能解析 / OCR 任务联调（P0） |
| 5 | `614d537` | `614d537ef4054be5f629e934c78c28f9fc6527f2` | 文档审核中心真实接口对接（只读，P0） |
| 6 | `7b8fe74` | `7b8fe74b07a72599db7dc28aedfe783b5b5ee8f0` | 知识库入库（预览与版本只读，P1） |
| 7 | `15e40a1` | `15e40a155fdd92a633971824a3f7d525c55a2a4f` | 法规检索真实接口对接（P1） |
| 8 | `c8bad73` | `c8bad73ed3de989a9afaefb9e09ab2bce9f92ca0` | 首页工作台真实统计与健康状态（P2） |
| 9 | `cf28557` | `cf28557bc55e3294dcf9fbf28f9a7288c4ad64c9` | 系统监控五态与运行期契约总览（P2） |
| 10 | `6ecb2ae` | `6ecb2aecae4c52baa2b7dc9bcc8a49506ebb4dd4` | `preview.proxy` 补齐、校准发布状态文案 |
| 11 | `d60f657` | `d60f657244259be8950422c668730a2df9b35246` | 上一版 `FRONTEND_INTEGRATION_PARTIAL` 报告（旧镜像阻塞期） |
| 12 | `96d4052` | `96d40521c49ee9e88a171cafd8541bd321f21827` | 运行期联调后修正检索初始态、过时 DEMO 文案、favicon、发布标签 |
| 13 | `5d83b13` | `5d83b13f4132464ddb764501967bc50992778062` | 运行期浏览器联调通过，详细证据卷更新为 READY |
| 14 | `688b824` | `688b824213a4489e2f1ce1577677b341f2c10792` | 按任务书收口：新增正式交付报告、修正历史标注与脱敏 |

**对应后端 SHA 记录**：联调全程绑定 8180 运行 revision `4fc4cf124a120762593064676ea5f8dbe2394119`（镜像 ID `sha256:8f169cd8…`、OCI revision 同值，见 §1.3）；契约分支 `20bfeef57e101f08a2f37bd4a73b6ed4237dcba5`；Agent C 接口分支 `712521429bb39e10b00730e139ccb4889dd2e555`。

> 第 15 个提交为「统一后端运行镜像身份补记」，仅改文档、不改动任何业务源码或运行服务；该提交不内嵌自身 SHA，最终 HEAD 由 `git log -1` 给出并在交付说明中回报。

---

## 8. 未完成接口（后端契约明确不支持，非前端未完成项）

| 组 | 缺失接口 | 前端处理 |
|---|---|---|
| 1–4 | `POST /api/review/{parse_id}/approve`、`/reject`、`/mark-error`、`/save-revision` | 审核通过 / 驳回 / 标记错误 / 保存修订 4 个按钮 `disabled`；`review_write_supported=false` 实测确认 |
| 5 | `POST /api/ingestion/batches` + `precheck` + `version-check` | 发起入库批次禁用 |
| 6 | `POST /api/ingestion/publish`、`/rollback` | 不开放正式发布 / 回滚 |
| 7 | 结构化引擎运行日志 `/logs` | 日志抽屉只展示后端 `public(task)` 真实字段 |
| 8 | 资源监控、审计 / 操作日志 | 系统页显示未接入空态，不伪造指标 |

后端补齐并通过契约验收、且保留原始解析结果与审计留痕后，方可逐项解除禁用；每解除一项需单独提交与验收。

---

## 9. 未验证 / 不在本轮范围（如实列出）

1. **写链路未在真实 8180 触发**：`POST /api/parse/files`（上传）、`POST /api/parse/tasks`、`resume` / `cancel`。前端实现与 `Idempotency-Key` 已就绪，但这些请求会改动业务数据与历史任务，本轮未获明确授权、也不使用真实业务资料做上传。`§3` 的全部实测均为只读或安全错误态。
2. **`GET /api/knowledge/versions/{version}` 成功态未覆盖**：public 当前无版本记录，只验证 404 `version_not_found`；版本列表为空是后端真实状态。
3. **有法条命中的检索结果未覆盖**：public 无 ACTIVE 版本，`status=unpublished` / `count=0`；`SearchHit` 渲染分支只做静态契约核对，未用真实命中数据渲染，不伪造法条。
4. **409 / 413 / 415 / 429 / 503 真实触发**：见 §3 说明，仅验证请求层归一化逻辑。
5. **独立 QA 验收、跨 owner 隔离对抗测试、生产部署、MinerU 云端推理、大规模分页性能**：均不在本轮；后端自评 `BACKEND_API_PARTIAL`，明确未达到合并 main 门禁。
6. **PDF 逐页渲染 / Word 转换**：PDF 用浏览器内置 viewer（认证 ArrayBuffer → Blob URL），图片用 `<img>`，DOCX 按 `attachment` 契约只提供授权下载；未引入 `pdfjs-dist` / `@vue-office/docx`，不做 Word→PDF 转换。
7. **回滚演练**：后端交接明确「已准备但未实际演练」，不由前端代为宣称。

---

## 10. 待 QA 验收项目

| # | 验收项 | 绑定身份 |
|---|---|---|
| 1 | 认证与跨 owner 隔离：凭证缺失 / 越权访问源文件与任务均返回 404，页面零业务请求 | 前端 `5d83b13` + 8180 revision `4fc4cf1` |
| 2 | 原件身份：`/source` 的 `x-sha256`、`content-disposition`、`accept-ranges`、`Range` 206 / 416；不得用 `artifact.bin` 冒充原件 | 同上 |
| 3 | 任务恢复 / 取消、源文件身份映射（`file_id` ≠ 任务内 `files[].file_id`，映射取自 `file_mappings` / 解析历史） | 同上 |
| 4 | PostgreSQL `requires_review` 与审核候选对照；四个写按钮始终 `disabled`，无本地状态假成功 | 同上 |
| 5 | Chunk 预览门禁、`write_performed=false` / `rag_index_written=false`；预览成功不得宣称入库成功 | 同上 |
| 6 | public 空知识库：`unpublished` 空态、版本列表空态、统计按来源分离且不相加 | 同上 |
| 7 | 健康五态：模型文件存在不得标为 ONLINE；`UNKNOWN` / `NOT_CONFIGURED` 正确区分 | 同上 |
| 8 | 七页面 401 / 404 / 416 / 422 / 200 空列表全错误态、刷新与 history fallback、控制台零错误 | 同上 |
| 9 | 在隔离合成对象上补做写链路与 409 / 413 / 415 / 429 / 503 触发（需另行授权，不触碰正式 ACTIVE 与历史任务） | 需 QA / 用户授权 |
| 10 | public 按既有授权流程发布 ACTIVE 版本后，复验检索命中态与版本详情成功态 | 需后端 / QA 执行 |

### 10.1 QA 回执 `V022-E01`：证据缺口，非代码缺陷（2026-11-11 15:2x）

QA 复核后仍为 **BLOCKED**，理由为验收证据不足；**未确认新的代码缺陷**，Fix 保持待命、不修改业务代码。已有截图已审查完毕，不重复提供；「单帧 PDF 空白」不认定为产品 Bug。本角色认同该判定。

| QA 要求补齐 | 现状与可行性 | 责任边界 |
|---|---|---|
| ① 上传 → 创建任务 → 真实 OCR → 查询结果 → 原文对照 → 质量提示的**前端闭环** | 后端 `POST /api/parse/files`、`POST /api/parse/tasks` 存在且前端已接好；但共享库里已有 **3 个 `completed` 的真实 `self_hosted` OCR 任务**、7 条 review 记录（含 `raw_text`、`quality` 多维度、`source_location`、`source_file_id`）。**后四段只读即可补采**；前两段「上传 / 创建任务」会写入共享 PostgreSQL + SQLite，属写链路 | 只读段由本角色补采；写段需按统一规则使用**获得批准的隔离状态与测试数据**，不得由本角色擅自在共享 8180 触发 |
| ② 可辨识的 PDF 原文画面及必要只读交互证据 | 已定位为**采集环境限制，非产品缺陷**：`GET /api/parse/files/{source_file_id}/source` 返回 `206` / `%PDF-1.7` / `application/pdf` / `inline` / 246331 B / `x-sha256`；既有审核页截图显示 SHA256「与文档记录一致」、页码「第 1/10 页」、右侧 OCR 文本与质量指标正常，仅 `<iframe>` 内画面空白。根因是 headless Edge 不渲染浏览器内置 PDF viewer（`DocumentPreview.vue` 用认证 ArrayBuffer → Blob URL → iframe） | 需改用可渲染 PDF viewer 的采集方式重截前端页面；**不改产品代码**（无确认缺陷、Fix 待命） |

**本轮已完成的只读核实**：8180 六项身份重新复核无变化（源码 `4fc4cf1…` / 镜像 ID `sha256:8f169cd8…` / 容器 `market-regulation-app-1` healthy）；OpenAPI 22 路径中写方法仅 7 个；任务内 `files[].file_id` 与上传 `file_id` **不同**，直接拿任务文件 ID 请求 `/source` 会 404，前端审核页使用 `review/{parse_id}` 返回的 `source_file_id`，映射正确。详细诊断见 ignored 本地文件 `local/frontend-evidence/V022-E01-gap-analysis.md`。

**状态**：报告结论 `FRONTEND_INTEGRATION_READY` 是前端自评（限定七页面约定只读能力），**不代表 QA 已 PASS**；QA 仍为 BLOCKED。本轮未改业务源码、未重启浏览器与预览服务、未执行任何写接口、未触碰后端镜像 / 数据库 / 授权账本。

---

## 11. 安全与合规

- 会话凭证仅在容器内用于本地只读请求，浏览器侧只存内存 + sessionStorage；未写入源码、报告、截图或 Git。未接触 MinerU Key、PG DSN 或私有 `.env` 的值。
- 所有请求同源 `/api`，不硬编码后端地址；原始文件按 owner 隔离，跨用户 / 不存在返回 404。
- 生产 `dist/` 无本地地址与过时 DEMO 文案；`git ls-files` 无 `node_modules` / `dist` / `.env` / 数据库 / 日志 / 模型 / 凭证文件。
- 不可信内容按纯文本展示，不执行 HTML / 脚本；Blob URL 在切换与卸载时撤销。
- 未 Push、未 Merge main、未打 Tag、未部署生产、未切换 Docker、未改后端源码 / 数据库 / 模型 / OCR 流程、未删除原有页面与备份。
- 前端 Bug 由本角色自行修复（见 §2 修正提交）；本轮未发现需反馈 Agent C / Fix 的后端接口 Bug——`artifact_not_found`、`version_not_found`、`unpublished` 均为契约预期行为，不通过前端隐藏错误伪造成功。

---

## 12. 交付物与状态复现

| 文件 | 说明 |
|---|---|
| `docs/frontend-api-integration-report.md` | **本文件**：任务书指定的正式交付入口 |
| `frontend/docs/frontend-api-integration-report.md` | 逐页证据卷、浏览器联调方法、状态/错误态矩阵（历史轮次保留，已修正过时 SHA 标注） |
| `frontend/docs/frontend-api-mapping-v0.2.2.md` | 22 条真实路径的接口映射矩阵、契约要点 |
| `frontend/src/**` | 七页面 + 唯一请求层 + 共享组件 + 类型契约 |
| `frontend/vite.config.ts` | 开发 / 预览双代理配置 |

**状态复现提示**：`releaseStatus.shortLabel` 是本次构建的静态联调结论；运行期能力仍以页面上的 `GET /api/openapi.json` 契约探测标签为准。若服务回退到旧镜像，页面会显示「后端服务未加载 v0.2.2 契约」异常态，**不会回退 DEMO**。

---

## 13. 最终状态标记

```
FRONTEND_INTEGRATION_READY
```

范围限定：七个页面的约定只读能力已完成真实 API 接入与真实运行验证；不含写链路端到端、正式审核写入 / 入库发布、独立 QA 验收与生产部署。完整未完成项见 §8、§9，待验收项见 §10。
