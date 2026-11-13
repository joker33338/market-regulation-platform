# 审核中心放大对照 · 可拖动分隔条 · 全局滚动滑块

> 日期：2026-11-12　状态：**已实现并通过真实浏览器回归，代码已在原前端分支本地提交（见文末状态表）**
> 未改后端、未重建镜像、未重启 8180、未动数据库与数据卷、未 Push / Merge。

## 1. 需求与根因

用户依次提出四点：① 审核页窗口太小，要能放大看清完整内容；② **左右两栏一起放大**才便于对照；③ 分栏顶部要能**上下拖动**；④ **其他页面文件多的地方也要增加滑块**，方便滑动浏览。

只读核查发现三层原因：

1. **物理尺寸**：`.review-split` 是左右栅格，页面还要先容纳页头、告警与待复核队列，两栏实际高度仅约 479px，PDF 可视区 526×295，右侧结果区可视高度约 156px。
2. **布局缺陷**：`AsyncPanel` 根容器未撑成 flex 列，`.result-body { flex:1; overflow-y:auto }` 的父级不可伸缩，长 JSON（`scrollHeight` 达 42 万 px）无法在栏内正常滚动，内容被裁切。
3. **滑块不可抓**：Element Plus 自带 6px 细滚动条、自定义滚动条默认 hover 才显示；文件多时滑块太细、不好拖。

## 2. 实现内容

### 2.1 审核页放大与对照（`views/ReviewView.vue`）

| 能力 | 说明 |
|---|---|
| **对照放大（两栏）** | 主按钮让 `.review-split` 脱离栅格占满视口，左右保持并排（实测 622×1112 / 746×1112），左原文右解析结果同屏对比 |
| 常驻顶栏 | 放大态把分隔工具条提升为 fixed 顶栏（`z-index 2002`），「退出对照放大」始终可见可点；否则会被遮罩盖住 |
| 单独放大 | 左右栏各保留「单独放大」按钮，单栏占满视口（1400×1160），适合细看单侧 |
| 三种还原 | 再点按钮、按 **Esc**、点击遮罩空白；组件卸载移除键盘监听 |
| 不重建 DOM | 放大只切外层定位，**不销毁组件实例**；PDF iframe 与 Blob URL 连续，V022-F01 的分页/缩放机制不受影响，放大后仍可翻页、缩放、下载 |
| 上下拖动 | 队列卡片与对比区之间加 `row-resize` 分隔条，拖动改变队列高度，对比区自动拿剩余空间；**双击恢复默认**；放大态禁用拖动 |
| 布局修正 | `.pane` 改 flex 列、`el-card` body 改 `flex:1 1 auto; min-height:0`、`.async-panel` 撑成 flex 列、工具栏/关联条/元信息条/操作条 `flex-shrink:0`、`.result-tabs` 改 `flex:1; min-width:0` |

### 2.2 全局可拖动滚动滑块（`styles/index.css`，七个页面统一生效）

- 原生滚动条统一 `12px` 宽，滑块 `min-height: 48px`（超长内容里不会缩成细线），带 hover / active 反馈。
- 覆盖 Element Plus 自带的 6px 细条：`.el-table__body-wrapper`、`.el-scrollbar__wrap`、`.el-drawer__body` 同为 12px；自定义 `.el-scrollbar__bar` 改为**常显**（`opacity:1`）、12px 宽、滑块色 `#b9c9e2`。
- 给「文件多」的列表加表头固定、表体可滑动：`MrProTable` 主列表 `max-height=520`（文档管理、解析中心共用）、审核复核队列 `220`、文档上传队列 `200`、文档解析历史 `240`、解析详情文件列表 `240`、入库版本列表 `260`。分页保持不变。

**未改动**：`DocumentPreview.vue`、`src/api/**`、认证与权限、审核写入按钮（仍按契约禁用）、路由、后端契约与任何数据。

## 3. 真实浏览器验收

有头 Edge 157 + CDP(9223)，1440×1200，4173 独立预览；凭证在容器内读取后填入真实 `/login`，全程只调用既有只读接口。

### 3.1 七页面滑块巡检

| 页面 | 页面滚动容器 | 滑块实测 |
|---|---|---|
| 首页 / 解析中心 / 入库管理 / 系统监控 | 有滚动（溢出 587 / 204 / 143 / 1880 px） | 12px 滑块 |
| 文档管理 / 法规检索 / 审核中心 | 内容未溢出时不显示滚动条（正常） | 样式已就绪 |
| 审核中心（加载真实详情后） | 长 JSON 结果区溢出 | 12px 滑块 |

运行期直接读伪元素样式确认：原生滚动条 `12px`、滑块 `min-height 48px`、Element Plus 自定义条 `12px / opacity 1 / rgb(185,201,226)`。

### 3.2 审核页交互回归（11 个状态）

| 步骤 | 结果 |
|---|---|
| 基线 | 左 527×479 / 右 633×479，队列 403px |
| 两栏对照放大 | 左 622×1112 / 右 746×1112 并排，顶栏 `y=0` 常驻、按钮「退出对照放大」，`iframeSame=true`（未重建） |
| 放大态翻到第 2 页 | 左侧画面按 V022-F01 受控重建，右侧按页对照同步 |
| 点顶栏按钮还原 / Esc 还原 | 尺寸、遮罩、按钮文字全部回到基线 |
| 上下拖动 +140px | 队列 403→543px，对比区 479→339px，PDF 526×155，布局无重叠 |
| 拖回 / 双击 | 恢复 403px / 内联高度清空 |
| 单栏放大（左 / 右） | 各 1400×1160，可用 |
| 遮罩点击还原 | 与基线一致 |

**JS 异常 0、Log error 0、写接口调用 0**；20 张截图与逐张 SHA256、脱敏 DOM 尺寸写入忽略目录 `local/frontend-evidence/` 的 `review-expand-verification.json`、`global-scrollbar-check.json` 与 `evidence-manifest.json`。

> 说明：现有真实数据量小（文档 6 条、任务 3 条、复核 8 条），列表默认不溢出，故截图无法呈现「文件很多」的画面；已用 DOM 层验证滑块样式与可滚动机制，未伪造业务数据。

## 4. 构建结果

| 项 | 结果 |
|---|---|
| `npm run typecheck` | 退出 0 |
| `npm run build` | 退出 0，最终产物 `index-9b0881f5.js`（仅有既有 chunk 体积告警） |
| `git diff --check` | 通过 |
| 4173 独立预览 | 返回新产物，全部交互可用 |
| 8180 正式入口 | **未改动**，仍为冻结产物 `index-4a01157b.js`，容器 healthy |

## 5. 为什么 8180 上还看不到

正式容器的前端 `dist` 固化在镜像内部，没有挂载静态目录；按保护条款不重建镜像、不 `docker cp`、不重启容器。

- **现在体验**：4173 独立开发预览（需重新配置一次 Token，与 8180 的 `sessionStorage` 不共享）。
- **要让 8180 生效**：由 Agent C 在下次正式镜像更新时带入新 `dist`，已列入 `docs/agent-c-backend-improvement-handoff-2026-11-12.md` 的 C-2 项。

## 6. 修改文件清单与状态

| 文件 | 改动 |
|---|---|
| `frontend/src/views/ReviewView.vue` | 两栏对照放大、单栏放大、常驻顶栏、上下拖动、Esc/遮罩还原、分栏 flex 布局修正 |
| `frontend/src/styles/index.css` | 全局 12px 可拖动滚动滑块 + Element Plus 自定义滚动条覆盖 |
| `frontend/src/components/MrProTable.vue` | 主列表 `max-height=520`（表头固定、表体可滑动） |
| `frontend/src/views/DocumentsView.vue` | 上传队列 / 解析历史 `max-height` |
| `frontend/src/views/ParsingView.vue` | 详情文件列表 `max-height` |
| `frontend/src/views/IngestionView.vue` | 版本列表 `max-height` |
| `frontend/src/config/release.ts` | 上一轮「只读」静态文案纠偏（与本次改动同批提交） |

| 状态项 | 结论 |
|---|---|
| 代码提交 | 已沿用原前端工作树 / 原分支 `feat/frontend-api-v0.2.2` 本地提交；业务源码 SHA `0cbb7b5b96c3e8e5c58b7a974b22140087017caa`。未 Push / Merge / 部署 |
| 浏览器写链路点击验收 | 未执行，不冒充 PASS |
| 审核写入按钮 | 仍按后端契约禁用，未伪造成功 |
| 后端 / 镜像 / 数据库 / 数据卷 | 零改动 |
| Push / Merge / 部署 / 独立 QA | 未进行，不宣称 `READY_FOR_FINAL_QA` |
