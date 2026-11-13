# 文档管理空态新增「返回」按钮（2026-11-12）

## 1. 变更依据

按用户截图反馈：文档管理页筛选后列表为空时，空态里只有「刷新」，无法就地退回到全部文档。本轮只在空态「刷新」右侧补一个「返回」按钮，不重建页面、不动筛选区与表格结构。

## 2. 空态为什么会挡住筛选区

`AsyncPanel` 在 `state === 'empty'` 时用 `#empty` 插槽**整体替换**默认内容，因此空态下 MrProTable 的搜索表单（查询 / 重置 / 刷新）与高级筛选条都不再渲染——用户此时既改不了筛选条件，也只能靠「刷新」重复同一组空结果。这正是本轮需要「返回」的原因：它是空态里唯一的退出通道。

## 3. 改动范围

仅 `frontend/src/views/DocumentsView.vue` 一个源码文件（+37 / −2）。

| 位置 | 内容 |
|---|---|
| 模板 `#empty` | 「刷新」右侧新增「返回」，包在 `el-tooltip` 内说明行为；外层 `.empty-actions` 让两按钮居中并排 |
| 脚本 | 新增 `hasActiveFilter` 计算属性（keyword / status / docType，以及 v0.2.3 契约就绪时的 dateFrom / dateTo / sortBy / order）；新增 `backToAll()`：清空搜索表单、高级筛选、排序与页码后重新请求真实接口 |
| 类型 | `tableRef` 类型补 `reset: () => void`，用于复用 MrProTable 已暴露的重置能力 |
| 样式 | 新增 `.empty-actions`（flex 居中、间距 8px） |

行为约定：

- **返回 = 清空筛选，回到全部文档**：`backToAll()` 先清空 `query` 与高级筛选的本地状态，再调用 `tableRef.reset()`（清空搜索表单、排序、页码并重新查询）；组件未挂载时退回 `list.load()`，不本地补数据、不伪造结果。
- **没有生效筛选条件时按钮禁用**，tooltip 明确「当前没有生效的筛选条件，后端返回的就是全部文档，无需返回」——避免用户误以为点一下就能凭空出现数据。
- 每次返回都重新走 `GET /api/documents`，以真实响应决定列表与空态。

## 4. 验证结果（真实浏览器，只读）

方法：4173 生产构建预览（`/api` 同源代理 8180）+ 无头 Edge 157 / CDP 9223，注入容器内既有会话凭证，仅调用只读 `GET /api/documents`。脚本 `local/frontend-evidence/empty-back-button-check.mjs`，结论 `local/frontend-evidence/screenshots/empty-back/empty-back-button-verification.json`。

| 步骤 | 实测 |
|---|---|
| 进入 `/documents` | 标题「文档管理」，列表 20 行 |
| 搜索词填 `zzz-no-such-document-zzz` 后点「查询」 | 命中真实空态，描述为「当前筛选条件下没有文档记录（后端返回空列表，非演示数据）」 |
| 空态按钮 | `刷新`（可用）、`返回`（可用），横向并排 |
| 点击「返回」 | 搜索词清空为 `''`、状态筛选清空、空态消失、列表恢复 20 行、页码回到 1 |

- `npm run typecheck` 退出 0；`npm run build` 退出 0（`DocumentsView-10f3a871.js` 22.07 kB；仅有既有 >500 kB chunk 告警）。
- 截图：`screenshots/empty-back/empty-back-01-filtered-empty.png`（筛选后空态，刷新 / 返回并排）、`empty-back-02-returned-all.png`（返回后列表恢复）。截图与 JSON 位于 ignored 的 `local/` 目录，不入库。
- `git diff --check` 无错误；本文件敏感词扫描 0 命中；未把会话凭证写入源码、报告、截图或 Git。

## 5. 与「正式版本」的关系

- 改动落在前端源码与 4173 预览。**正式 8180 容器内的前端 `dist` 是镜像内冻结产物**，前端源码提交不会自动反映到 8180。
- 只读复核：`market-regulation-app-1` 仍 healthy，v0.2.2 冻结镜像；本轮未重建镜像、未重启/覆盖容器、未改数据卷、未写入任何业务数据。
- 需由 **Agent C 在构建 v0.2.3 联合候选时带入本轮最新 dist**，并在交接六项中记录本次提交后的最终前端 HEAD。
- v0.2.3 的 7 项隔离联调仍为 `NOT_TESTED`，整体状态仍为 `ADAPTATION_PREPARED / NOT_LIVE_VERIFIED`；本轮 UI 变更不改变该状态，不签发 QA_PASS 或发布结论。

## 6. 提交与边界

- 分支 `feat/frontend-api-v0.2.2`，仅本地提交，未 Push / Merge main / 打 Tag / 部署生产。
- 未改后端源码、OpenAPI 契约、数据库、ACTIVE 版本、正式角色/runtime、镜像与数据卷。
