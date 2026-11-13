# 注释性文字默认收起、点击展开（2026-11-12）

## 1. 变更依据

按用户截图反馈：审核中心顶部「身份口径：frontend-api-v0.2.3-draft-2 / principal-v1」等长篇注释性文字默认平铺，占用大量首屏空间。要求各类注释性文字默认隐藏，点击可查看。

## 2. 实现方式

采用**全局样式 + document 级事件委托**，不改任何页面模板：

- 默认只显示一个「说明 ▾」入口（`el-alert` 显示为标题后的「 · 说明 ▾」），点击展开原文，再点收起；
- 展开态只添加 `is-note-open` class，不写 `localStorage` / `sessionStorage`，刷新或切换页面后恢复默认收起；
- 折叠样式用 `#app` 前缀提高特异性，覆盖各组件 scoped 样式，避免与页面局部字号冲突；
- 事件委托在 `src/utils/noteToggle.ts` 中注册一次，兼容 Vue 重渲染与路由切换，七个页面无需各自维护展开状态。

## 3. 覆盖范围

| 类型 | 选择器 | 默认表现 |
|---|---|---|
| 提示条描述 | `.el-alert__description`（非 error、且不含按钮/链接/输入） | 标题后「 · 说明 ▾」，点击展开 |
| 页面副标题 | `.page-desc` | 「说明 ▾」，点击展开 |
| 禁用 / 接口提示 | `.mr-disabled-hint` | 「说明 ▾」，点击展开 |
| 结果区说明 | `.hint-text` | 「说明 ▾」，点击展开 |
| 写入门控提示 | `.action-hint` | 「说明 ▾」，点击展开 |
| 卡片头接口标签 | `.card-sub`、`.source-hint` | 「说明 ▾」，点击展开 |
| 文件预览说明 | `.dp-note` | 「说明 ▾」，点击展开 |

**明确保留、不折叠**：

- `el-alert--error` 错误提示（请求失败、提交失败、数据不一致）始终展开；
- 含按钮 / 链接 / 输入框的 `el-alert` 与说明块（「重试」「配置后重试」「刷新」等）不折叠，避免把真实操作入口一起藏掉；
- `el-empty` 空态说明、表格真实数据、状态标签、身份条字段值均不受影响。

## 4. 验证结果

- `npm run typecheck` 退出 0；`npm run build` 退出 0，产物 `index-fee0395a.js`、`index-3d077f89.css`。
- **CDP 实测**（无头 Edge 157，4173 真实页面，只读）：
  - 默认：身份口径描述 `display=none`、标题后内容为「 · 说明 ▾」、页面副标题 `font-size: 0px`；
  - 点击标题 / 副标题后：描述 `display=block`、标题后变「 · 收起 ▴」、副标题恢复 `13px`；
  - 再次点击：恢复 `display=none` / `0px`；
  - 含按钮的「未认证 / 无权限」提示：操作按钮 `display=inline-flex`，仍可见可点。
- **七页面覆盖检查**（`/dashboard`、`/documents`、`/parsing`、`/review`、`/knowledge/ingestion`、`/knowledge/search`、`/system`）：页面副标题全部为 `0px`（默认收起）；各页说明按上述规则收起，错误提示与含按钮说明块保持可见。
- 截图：`local/frontend-evidence/screenshots/note-collapse/review-default-v2.png`（ignored 证据目录）。
- **未验证**：配置真实 Token、加载长业务数据后展开说明的完整视觉排版；本轮验证覆盖默认收起、点击展开、再次收起与按钮可见性，不宣称所有长文本排版细节 PASS。

## 5. 与正式版本 / 交付的关系

- 改动只在前端源码与 4173 预览。**正式 8180 容器内的前端 `dist` 是镜像内冻结产物**，源码提交不会自动更新 8180。
- 只读复核：`market-regulation-app-1` healthy，镜像 ID `sha256:e2a94f67…52a3`、OCI revision `30c4663…bfb4`（v0.2.2），本轮未重建镜像、未重启/覆盖容器、未改数据卷。
- 需由 Agent C 在构建 v0.2.3 联合候选时带入本轮最新 `dist`，并记录本次文档提交后的最终前端 HEAD；8180 页面才会显示折叠后的版本。不覆盖旧候选标签。
- v0.2.3 的 7 项隔离联调仍为 `NOT_TESTED`，整体状态保持 `ADAPTATION_PREPARED / NOT_LIVE_VERIFIED`；本轮 UI 变更不改变该状态，不签发 QA_PASS 或发布结论。

## 6. 提交

- 源码提交 `033420612785dc1e873f83d3e6f2e9469f778205`（分支 `feat/frontend-api-v0.2.2`，仅本地）。
- 未改后端源码、OpenAPI 契约、数据库、ACTIVE 版本、正式角色/runtime、镜像、数据卷、正式 8180；未 Push / Merge main / 打 Tag / 部署生产。
