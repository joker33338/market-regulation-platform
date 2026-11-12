# 审核中心移除「上下拖动」分隔条（2026-11-12）

## 1. 变更依据

按用户截图反馈：审核中心「待复核队列」与「左右对照区」之间那条淡蓝色拖动条（文案「上下拖动调整对比区高度（双击恢复默认）」）在正式交付版本中不再需要。本轮只移除上下拖动这一交互与其 UI，不重建页面、不改其它功能。

## 2. 改动范围

仅 `frontend/src/views/ReviewView.vue` 一个源码文件（+7 / −47）。

| 层 | 移除 | 保留 / 新增 |
|---|---|---|
| 模板 | `.v-resizer` 整条 DOM：`@mousedown` / `@dblclick`、`⋮⋮` 手柄、拖动文案；`queue-card` 的 `:class="{ resizable }"` 与 `:style="queueStyle"` | 队列注释改为「高度由内容自适应」；工具条新增仅放大态可见的静态提示 `对照放大中 · 按 Esc 或点击空白区域还原` |
| 脚本 | `queueHeight` / `queueStyle` / `startResize` / `onResize` / `stopResize` / `resetResize`，以及 `onBeforeUnmount` 中的 `stopResize()` | `togglePane` 双栏放大、`onKeydown` 的 Esc 还原 |
| 样式 | `.queue-card.resizable`、`.v-resizer*`、`cursor: row-resize` 与 hover 态 | `.split-toolbar` 改为右对齐 + 新增 `.expand-hint`；`.split-toolbar.on-top` 放大态常驻顶栏 |

**完整保留**：单栏放大、双栏对照放大、Esc / 遮罩 / 「退出对照放大」按钮三种还原、V022-F01 的 PDF iframe 与 Blob URL 生命周期（放大不重建 DOM）、`.result-body` 内部滚动、全局 12px 滚动滑块、其它六个页面布局，以及 v0.2.3 draft-2 身份/RBAC 双门控与默认目标写入保护。

## 3. 验证结果

- `npm run typecheck` 退出 0；`npm run build` 退出 0，产物 `index-b8c54b0b.js`、`ReviewView-639fb434.js`、`ReviewView-43c1a34d.css`（仅有既有 >500 kB chunk 告警）。
- 4173 生产构建预览持续运行并已服务新产物（preview 从磁盘读 dist，无需重启）：`/review` 200、首页引用 `index-b8c54b0b.js`、新 JS/CSS 均 200；新 `ReviewView` chunk 中「上下拖动」「双击恢复默认」**0 命中**，「对照放大（两栏）」与放大态还原提示各 1 命中。
- `git diff --check` 无错误；改动仅 1 个文件；本文件敏感词扫描 0 命中；`src` 全量扫描已无 `v-resizer` / `queueHeight` / `startResize` 残留（`ChartBox.vue` 的同名 `onResize` 是图表 resize，无关）。
- **浏览器鼠标交互实测未执行**：本轮是静态源码与产物核对，不宣称 UI 交互 PASS。

## 4. 与「正式版本」的关系

- 改动落在前端源码与 4173 预览。**正式 8180 容器内的前端 `dist` 是镜像内冻结产物**，前端源码提交不会自动反映到 8180。
- 只读复核：`market-regulation-app-1` healthy，镜像 ID `sha256:e2a94f67…52a3`、OCI revision `30c4663…bfb4`（v0.2.2），本轮未重建镜像、未重启/覆盖容器、未改数据卷。
- 需由 **Agent C 在构建 v0.2.3 联合候选时带入本轮最新 dist**，并在交接六项中记录本次文档提交后的最终前端 HEAD；8180 页面才会显示去掉拖动条后的版本。不覆盖旧候选标签。
- v0.2.3 的 7 项隔离联调仍为 `NOT_TESTED`，整体状态仍为 `ADAPTATION_PREPARED / NOT_LIVE_VERIFIED`；本轮 UI 变更不改变该状态，不签发 QA_PASS 或发布结论。

## 5. 提交与边界

- 源码提交 `5d84797e54d6457b770eb2bade141b36081de7e4`（分支 `feat/frontend-api-v0.2.2`，仅本地）。
- 未改后端源码、OpenAPI 契约、数据库、ACTIVE 版本、正式角色/runtime、镜像、数据卷、正式 8180；未 Push / Merge main / 打 Tag / 部署生产。
