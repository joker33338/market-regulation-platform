# 上传创建解析任务：防重复修复 + 一键解析

> 日期：2026-11-12　分支 `feat/frontend-api-v0.2.2`（仅本地提交）
> 范围：仅前端 `DocumentsView.vue` / `ParsingView.vue`；未改后端源码、数据库、镜像、正式 8180。

## 1. 问题与根因

用户反馈：文档管理页上传多个文件后，点某行「创建解析任务」，该行不消失、仍可重复点击；下方文档列表出现「解析次数 3」等重复任务。

| 层 | 事实 |
|---|---|
| 后端 | `POST /api/parse/tasks` 按 `(owner, Idempotency-Key)` + 请求指纹幂等：同键同 `file_ids` 返回原任务（仓储 `create()` 直接返回已存 payload），同键异请求 409；`max_files=20` 允许一次提交 1–20 个 `file_id` |
| 前端旧实现 | 每次点击都 `crypto.randomUUID()`；成功后只设置 `lastTask` 并刷新列表，**既不移除 `realUploads` 行，也不记录已创建状态** |
| 结果 | 连点 N 次 = N 个不同键 = 后端真实创建 N 个任务；按钮还在，用户误以为任务没有创建成功 |

契约依据：`qa_core/document_parsing/mineru_repository.py::create`、`mineru_api.py` 创建任务分支、`config.py` 的 `max_files=20`、`tests/test_mineru_api.py` 中「同键同请求返回同一 task_id」的既有断言。

## 2. 修复内容

| 位置 | 改动 |
|---|---|
| `RealUpload` | 上传成功时为每项生成一次 `idempotencyKey`，整个会话复用，不再每次点击换键 |
| `createTaskFor` | 固定键 + 固定 body；**只有拿到后端真实回执**才把该行从待创建列表移除；失败保留行与键，允许同键重试；409 单独提示并刷新详情 |
| 一键解析全部 | 卡片头部新增按钮，把当前待创建项（≤20）打包为**一个** `POST /api/parse/tasks`；`bulkRequest` 按 `file_ids` 列表签名复用键；成功后整批移除；超过 20 个 / 未登录 / 提交中禁用并给出原因 |
| 创建回执 | 提示条从卡片内移到卡片外，待创建列表清空后仍可见；显示任务 ID、状态、累计创建数与「到智能解析中心查看」入口 |
| `reparse` | 保持「显式新任务」语义（每次新键）+ 请求期防连点；成功后同样计数并刷新列表 |
| `ParsingView.submitTask` | 同一组 `file_id` 的未确认请求复用同一键；创建成功后清空输入框，避免连点重复提交；重新填写视为显式新任务 |

单行创建与一键解析共用 `submittingId` / `bulkSubmitting` 互斥，批量提交期间单行按钮同步禁用。整批提交期间新上传的文件不会被误移除（只按提交时快照的 `file_id` 集合过滤）。

## 3. 验证

| 项 | 结果 |
|---|---|
| `npm run typecheck` | 退出 0 |
| `npm run build` | 退出 0；`index-18e0e8cc.js`、`DocumentsView-45cc14a8.js`、`ParsingView-d791523d.js`（仅有既有 chunk >500 kB 告警） |
| `git diff --check` | 无错误 |
| 源码静态核查 | `createTaskFor` 不再每次随机键；成功分支移除 `realUploads` 行；批量键按列表签名复用；无硬编码凭证、DSN 或机器绝对路径 |
| 浏览器交互实测 | **未执行**：用户已取消 4173 预览后台任务并明确不重启，本轮未启动预览或浏览器。「上传 → 创建 → 行消失 → 连点不重复建任务」的真实交互待恢复预览或由 QA 在隔离环境验收 |

## 4. 边界与遗留

- 截图中已经产生的 3 个解析任务是**真实后端记录**，前端不删除、不伪造清理；如需处理须由获准的隔离环境或后端流程执行。
- 一键解析单任务上限 20 个 `file_id`（后端 `max_files`）；超过时按钮禁用并提示先逐个创建，本轮不做自动分批。
- 未 Push / Merge main / 打 Tag / 部署；未改后端源码、数据库、Docker 镜像、正式 8180 容器与数据卷；Token 仍只在内存 + `sessionStorage`。
- 状态：**源码修复 + 静态/构建验证通过，交互验收未执行**，不宣称 QA PASS。
