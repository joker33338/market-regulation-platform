# 空态「返回」升级为通用能力（2026-11-12）

## 1. 变更依据

上一轮在文档管理页加了空态「返回」，用户确认把这个能力做成通用：其余列表页筛选为空时也能一键返回，并且不用再靠「返回」退出——空态下搜索条应保持可见，能直接改条件重查。

## 2. 根因（两条，一起解决）

1. **搜索条被状态面板吞掉**：`MrProTable` 原先把搜索区放在 `AsyncPanel` 内部，而 `AsyncPanel` 在 `empty` 态用 `#empty` 插槽整体替换默认内容，于是空态下搜索框、查询/重置/刷新全部消失，用户无法就地改条件。
2. **能力写在页面里会重复**：上一版的 `hasActiveFilter` / `backToAll` 是 `DocumentsView` 私有实现，`ParsingView` 等页面要用就得复制一遍，容易出现「搜索框清了、日期区间还留着」这类不一致。

## 3. 改动范围（4 个文件，+109 / −90）

| 文件 | 改动 |
|---|---|
| `components/MrProTable.vue` | 搜索区移到 `AsyncPanel` 之外（外层新增 `.mr-pro-table` 容器），空态/错误态下常驻；空态统一渲染「刷新 + 返回」；新增 `emptyText` prop；新增 `filter-reset` 事件；新增 `hasActiveFilter` 计算；`reset()` 改为先广播 `filter-reset` 再查询 |
| `views/DocumentsView.vue` | 删掉页面级 `#empty` 槽与 `backToAll` / `hasActiveFilter` / `.empty-actions`（−42 行），改为 `empty-text` + `@filter-reset="onFilterReset"`，由 `onFilterReset` 清日期区间与排序 |
| `views/ParsingView.vue` | 删掉只带「刷新」的自定义空态，改用 `empty-text="当前筛选条件下没有解析任务（后端返回空列表）"` |
| `styles/index.css` | 新增 `.mr-empty-actions`（两个按钮居中并排） |

行为约定：

- **返回 = 清空全部筛选回到全部数据**：`reset()` → `initModel()` 清搜索表单 → 清排序 → `emit('filter-reset')` 让页面清自己持有的高级筛选（日期区间 / 排序字段）→ `search()`（页码归 1 并发起真实查询）。
- **没有生效筛选条件时按钮禁用**：`hasActiveFilter` 覆盖搜索模型（字符串 / 日期范围数组）与排序；无筛选时 tooltip 直说「后端返回的就是全部数据，无需返回」，避免误导成点一下就能凭空出数据。
- **仍以真实响应为准**：返回后重新走 `GET /api/documents`、`GET /api/parse/tasks`，不本地补行、不伪造结果；页面可继续用 `#empty` 槽完全自定义（向后兼容）。

## 4. 验证结果（真实浏览器，只读）

方法：4173 生产构建预览（`/api` 同源代理 8180）+ 无头 Edge 157 / CDP 9223，注入容器内既有会话凭证，仅只读 GET。脚本 `local/frontend-evidence/empty-back-generic-check.mjs`，结论 `screenshots/empty-back/generic-empty-back-verification.json`。

| 页面 | 筛空后搜索条 | 空态按钮 | 点「返回」后 |
|---|---|---|---|
| 文档管理（keyword=`zzz-no-such-document-zzz`） | **可见**（查询按钮同样可见） | `刷新` 可用、`返回` 可用 | keyword 清空、空态消失、列表恢复 20 行 |
| 智能解析中心（engine=`zzz-no-such-engine`） | **可见** | `刷新` 可用、`返回` 可用 | engine 清空、空态消失、列表恢复 15 行 |

- 两个页面全程 `Runtime.exceptionThrown` 0 条。
- `npm run typecheck` 退出 0；`npm run build` 退出 0（`index-da679bff.js`、`DocumentsView` / `ParsingView` chunk 重新生成；仅有既有 >500 kB chunk 告警）。
- 截图：`screenshots/empty-back/generic-empty-01-documents.png`、`generic-empty-03-parsing.png`（空态下搜索条仍在）、`generic-empty-02/04`（返回后列表恢复）。截图与 JSON 位于 ignored 的 `local/` 目录，不入库。
- **未实测**：无任何筛选条件时的禁用分支——当前 8180 有 20 条文档、15 个任务，真实数据下无法自然得到「无筛选 + 空列表」，该分支为代码保证，不宣称实测。也未用请求拦截伪造空列表来“验证”。

## 5. 与「正式版本」的关系

- 改动落在前端源码与 4173 预览。**正式 8180 容器内的前端 `dist` 是镜像内冻结产物**，前端源码提交不会自动反映到 8180。
- 只读复核：`market-regulation-app-1` 仍 healthy，v0.2.2 冻结镜像；本轮未重建镜像、未重启/覆盖容器、未改数据卷、未写入任何业务数据。
- 需由 **Agent C 在构建 v0.2.3 联合候选时带入本轮最新 dist**，并在交接六项中记录本次提交后的最终前端 HEAD。
- v0.2.3 的 7 项隔离联调仍为 `NOT_TESTED`，整体状态仍为 `ADAPTATION_PREPARED / NOT_LIVE_VERIFIED`；本轮 UI 变更不改变该状态，不签发 QA_PASS 或发布结论。

## 6. 提交与边界

- 分支 `feat/frontend-api-v0.2.2`，仅本地提交，未 Push / Merge main / 打 Tag / 部署生产。
- 未改后端源码、OpenAPI 契约、数据库、ACTIVE 版本、正式角色/runtime、镜像与数据卷。
- 上一轮的页面级实现见 `docs/frontend-documents-empty-back-2026-11-12.md`，本轮已由通用能力取代（该文档保留为过程记录）。
