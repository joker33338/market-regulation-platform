# V022-F01 前端修复交接回执（WorkBuddy → QA）

日期：2026-11-11。对应 QA 交接说明：`docs/qa/v0.2.2/V022-F01-preview-pagination.md`（P1 / RELEASE_BLOCKER / FAIL）。

**结论**：已按「交 WorkBuddy 最小修复」完成组件修复与真实画面回归，提交新前端 SHA 与可核验证据；**不自行把 QA 的 FAIL 改判为 PASS**，请 QA 仅复测该组件与审核对照。未要求 Fix 改后端、未要求 Agent C 重建未变后端镜像。

## 1. 身份与受测边界（本轮重新只读复核）

| 项 | 本轮实读 |
| --- | --- |
| 前端业务源码 SHA（本次修复提交） | `63bbcc07a6b6d12a6be56fa7b0e81731c3917a45` |
| 交接 HEAD | 本回执及配套文档提交之后的 `feat/frontend-api-v0.2.2` HEAD；相对业务源码 SHA 仅文档变化 |
| 修复前受测业务源码 | `5d83b13f4132464ddb764501967bc50992778062`；QA 冻结的 `DocumentPreview.vue` SHA256 `73d7b7a512e1274e857745c2ddc86e609dec5f3e8be7663fde3c4d41aec51f5f` 已由本次提交改变 |
| 后端源码 / OCI revision | `4fc4cf124a120762593064676ea5f8dbe2394119`（镜像 label 只读复核一致） |
| 共享镜像 ID | `sha256:8f169cd82cc1bf55807eb48a9f75e0b5206ac4cb10ca27c38fe206a85e93d7a4` |
| 镜像标签 | `market-regulation-workbench:candidate-v022-4fc4cf124a12` |
| 运行容器 | `market-regulation-app-1`，ID `de1c0271a55eb579ef43073ad3f7109732bd409bb49259087451b6f32fe401af`，running / RestartCount=0 |
| 8180 实际服务身份 | 容器内带凭证请求 `/api/openapi.json` → 200、`0.2.2-api-candidate`、22 paths |
| 前端构建产物 | `npm run typecheck` 退出 0；`npm run build` 退出 0，入口 `dist/assets/index-e6009def.js` |
| 本轮未做 | 不构建/切换/重启镜像，不写 8180 数据，不部署，不 Push / Merge / 打 Tag |

「8180 根路径仍显示旧版页面」的静态产物部署问题，用户已明确交由 Agent C 处理，本回执不涉及、也未改动 8180。

## 2. 根因边界（区分已确认事实与机制推断）

**已确认事实**：修复前 `DocumentPreview.vue` 的 PDF 分支为单个 `<iframe :src="viewerUrl">`，`viewerUrl` 在同一 Blob URL 上拼接 `#page=N&zoom=Z`。QA 已用两张全景与两组相同特写证实：页码/缩略项/右侧按页对照切换到第 2 页时，左侧实际 PDF 画面仍是第 1 页。本轮修复前的基线截图 `f01-01-page1-full.png` 与 QA 报告的 `e01-14` / `e01-15` SHA256 完全相同（`e0c954d4…`），再次确认该画面未被改动或伪造。

**修复采用的机制**：浏览器内置 PDF viewer 只在文档首次加载时把 `#page` / `#zoom` 当作初始参数；同一 Blob URL 仅修改 fragment 不足以让已加载的 viewer 重新定位。因此分页或缩放时给 iframe 一个**全新文档**：从本次 `/source` 认证响应缓存的字节生成新 Blob URL，并递增 `:key` 重建 iframe。**不把这一机制表述为已经证明的浏览器规范结论**，只陈述本轮实测：新文档方式下 1→2→1、缩略项、直接页码、100%→150%→100% 的实际画面均按预期变化/还原。

## 3. 最小修复内容（业务源码仅 1 个文件）

`frontend/src/components/document/DocumentPreview.vue`（+62 / −11 行）：

| 改动 | 说明 |
| --- | --- |
| `<iframe :key="frameKey" :src="viewerUrl">` | 分页/缩放时受控重建，viewer 以新 fragment 重新初始化 |
| `viewerUrl` 由 computed 改为受控 ref | 每次重建生成新的 Blob URL + `#page/#zoom`，不再复用同一 URL 改 fragment |
| `sourceFile` 缓存 | 复用首次 `/source` 认证响应的 ArrayBuffer，重建不重复发请求、不改写字节 |
| `liveBlobUrls` + `releaseUrl()` | 集中管理 Blob URL；切换文件/组件卸载时全部 revoke |
| `nextTick` 后释放旧 Blob | 旧 iframe 卸载后再 revoke，避免销毁中的文档读取失败 |
| `watch([innerPage, zoom], rebuildViewer)` | 上一页/下一页、页码输入、缩略项、缩放下拉统一驱动实际画面 |
| PDF 首次加载也走同一路径 | 保证 `#page/#zoom` 从一开始就是文档初始参数 |

**未改动**：接口地址与请求方式、Token/owner 身份、`X-SHA256` 与 `expectedSha256` 完整性校验、下载原件、图片/DOCX 分支、审核页 `currentPage` 与按页对照计算、后端契约与任何后端代码；未引入 pdfjs-dist / vue-office 等新渲染依赖；未伪造页图、未隐藏控制、未关闭权限或摘要检查。

## 4. 验证方法

- 有头 Microsoft Edge 157 + CDP(9223)，视口 1440×1600；入口为本机构建产物预览 `http://127.0.0.1:4173/login → /review`，`/api` 同源代理到共享 8180。headless 不渲染内置 PDF viewer，故沿用 QA 已认可的有头入口。
- 在真实登录页输入既有会话凭证（凭证只在运行容器内读取并于内存使用，未打印、未落盘、未入库、未写入截图或 Git）；只调用既有只读接口，**未调用任何写接口**。
- 对象为共享库既有真实 10 页 PDF 审核记录（QA 脱敏案例 `BROWSER-PDF-01` 同类记录）；文件名、原文、人员与对象 ID 不进入报告。
- 证据：13 张 PNG / 1,842,686 B，另有 `local/frontend-evidence/f01-verification.json`（DOM 状态脱敏摘要、逐张 SHA256、像素差异）与 `f01-blob-balance.json`（Blob 生命周期）；完整 SHA256 清单已追加到该忽略目录的 `evidence-manifest.json`。

## 5. 回归用例结果

| # | 用例（QA 指定） | 前端状态 | 左侧实际 PDF 画面 | 判定 |
| --- | --- | --- | --- | --- |
| 1 | 初始 100% 第 1 页 | 第 1/10 页、缩略 1、`#page=1&zoom=100` | 中文正文可辨识；SHA `e0c954d4…`，与 QA 修复前基线完全相同 | PASS |
| 2 | 下一页 1→2 | 第 2/10 页、缩略 2、`#page=2&zoom=100` | SHA `c6009ef0…`，与第 1 页像素差异 **14.20%**；可辨识正文与页脚「- 2 -」 | PASS |
| 3 | 上一页 2→1 | 第 1/10 页、缩略 1 | SHA 回到 `e0c954d4…`，与初始帧差异 **0.0** | PASS |
| 4 | 缩略项直接跳第 3 页 | 第 3/10 页、缩略 3 | SHA `45600b2d…`，与第 1 页差异 **14.48%**，正文与 1/2 页均不同 | PASS |
| 5 | 页码输入跳第 2 页 | 第 2/10 页、缩略 2 | SHA `c6009ef0…`，与用例 2 差异 **0.0**（CDP 模拟 input/change 事件） | PASS |
| 6 | 100%→150%→100% | fragment `#page=2&zoom=150` → `100` | 150% SHA `2aa4bde8…`，差异 **30.40%**、灰度 std 33.7→47.4，字号明显放大且正文可辨；回 100% 与第 2 页差异 **0.0** | PASS |
| 7 | 页签切换（质量指标→OCR 文本） | 仍为第 2/10 页 | iframe **未重建**，`iframeRebuilt=false`，画面 SHA 与切换前一致、差异 **0.0** | PASS |
| 8 | 最终回到第 1 页 | 第 1/10 页、缩略 1 | 全景左右栏均为第 1 页内容；特写与基线差异 **0.0** | PASS |
| 9 | 按页对照同步 | 页码标签、缩略项、右侧「按页对照 · 当前第 N/10 页」一致 | 右侧文本长度/哈希随页变化（462 / 564 / 632），第 1 页与第 2 页全景均可目视核对 | PASS |
| 10 | 身份 / 原件 SHA / 权限 / Blob 释放 | 完整性条全程「与文档记录一致」、无「不一致」；`Runtime.exceptionThrown`=0、`Log` error=0、iframe 数恒为 1 | Blob：加载后 created=2/revoked=0，连续 3 次翻页每次 +1/−1，SPA 离开审核页卸载后 **created=5 / revoked=5、余额 0、iframe=0** | PASS |
| 11 | 下载原件 | 代码未改动、按钮保持可用 | 本轮**未点击下载**（避免复制真实原件到本机），留 QA 复测 | 未覆盖 |

## 6. 关键客观数据（可直接复算）

| 截图 | SHA256 | 字节 |
| --- | --- | --- |
| `f01-01-page1-full.png`（修复前同画面基线） | `e0c954d4ec219c69784ae1e79c06c1ed9e5db87bb793345b0e9900b2c16dc860` | 80,705 |
| `f01-02-page2-full.png` / `f01-05` / `f01-07` / `f01-08` | `c6009ef09edc628f069e9e5b9602650a74bf6f092d8790c63c59065c46c9b294` | 91,889 |
| `f01-03-back-page1-full.png` / `f01-09-final-page1-frame.png` | `e0c954d4ec219c69784ae1e79c06c1ed9e5db87bb793345b0e9900b2c16dc860` | 80,705 |
| `f01-04-thumb-page3-full.png` | `45600b2d3858e58d344fc70e0862b95bf09bfca0f79261aedf4dd675f7433ae2` | 91,467 |
| `f01-06-zoom150-full.png` | `2aa4bde819b12df10d434ec3e8d1ec49916edd7176940c8d8c8e0c8f14f80c8b` | 122,970 |

像素差异按两张同尺寸 iframe 特写灰度图非零差异像素占比计算；数值与 DOM 状态、Blob 生命周期均来自本轮实际采集，不是事后推断或补造的 CDP 事件流。

## 7. 边界与未覆盖范围

- 未重复跑后端 28 项定向测试、未重跑七页面全量、未改后端 API；按 QA 交接要求，请只复测 `DocumentPreview.vue` 组件与审核左右对照。
- 未执行上传 / 创建任务 / resume / cancel 写链路、正式审核写入、入库构建与发布回滚；V022-E01 剩余写闭环仍由 QA 在获准隔离状态与合成对象上验收，本修复不替代。
- QA 建议的「两页内容明显不同的公开合成 PDF」留作 QA 复测用例；本轮使用的是共享库既有真实 10 页 PDF，各页实际正文明显不同且可辨识，足以判定本组件是否跳页。
- 下载原件、无凭证 401 态、跨 owner 权限等能力代码未改动，本轮未重复取证（既有权属证据仍有效），由 QA 按需复测。
- 未新建长期后端环境，未切换 8180 被测镜像；8180 静态页面部署已由用户交 Agent C，本轮未实施任何部署动作。

## 8. QA 复测入口

1. `frontend/`：执行 `npm run typecheck`、`npm run build`，用 `npm run preview -- --host 127.0.0.1 --port 4173 --strictPort` 预览构建产物（`/api` 同源代理到 8180）。
2. 真实 `/login` 页配置凭证，进入「文档审核中心」，从待复核队列选择多页 PDF 记录。
3. 执行上一页/下一页、缩略项、页码输入、缩放下拉及页签切换，比较**左侧实际 PDF 画面**而非仅比较页码、input 或缩略项。
4. 证据索引（均在本机忽略目录、不入库）：`local/frontend-evidence/evidence-manifest.json` 的 `v022_f01_evidence` 段、`f01-verification.json`、`f01-blob-balance.json`；截图在用户指定的本机临时截图目录 `mrp-screenshots/v022-f01/`。

---

本回执不改写 QA 原判定：V022-F01 的关闭与否由 QA 独立复测后决定。
