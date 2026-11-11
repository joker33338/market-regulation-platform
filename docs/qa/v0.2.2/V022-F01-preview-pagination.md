# V022-F01：原文分页状态变化但PDF画面未切换

> 最新状态：修复63bbcc07a6b6d12a6be56fa7b0e81731c3917a45已独立回归PASS/关闭，见 [回归报告](V022-F01-regression.md)。以下保留初次FAIL的真实证据与原验收条件，不表示修复后仍失败。

日期：2026-11-11。优先级 **P1**，主类别 **RELEASE_BLOCKER**，结论 **FAIL**。交WorkBuddy最小修复；不要求Fix修改后端或Agent C重建未变后端镜像。

## 受测版本与承诺

- 前端业务源码：`5d83b13f4132464ddb764501967bc50992778062`；当前交接HEAD `b511f388def788fa1b07fdfeab9a93c7342f4cd3` 相对该源码仅文档变化。
- 后端源码/OCI revision：`4fc4cf124a120762593064676ea5f8dbe2394119`。
- 共享镜像：`market-regulation-workbench:candidate-v022-4fc4cf124a12`；ID `sha256:8f169cd82cc1bf55807eb48a9f75e0b5206ac4cb10ca27c38fe206a85e93d7a4`；容器 `market-regulation-app-1`，只读复查身份未变。
- 对应正式P0承诺：原文对照及审核结果只读展示。已经提供并启用的“上一页/下一页/缩略页/按页对照”不能只更新标签而显示旧页；这是当前功能，不是新增逐页OCR或Word转换需求。
- 脱敏案例：`BROWSER-PDF-01`，已有多页PDF，同一审核记录；真实文件名、原文、人物及对象ID不进入Git。

## 复现条件、预期与实际

WorkBuddy已在有头Edge157、真实认证与现有多页记录中执行操作；QA本轮只读核验原图/摘要并目视比较，**未重新启动浏览器或重演操作**。

1. 审核页选定该记录，第一页100%显示原文及对应解析文本。
2. 点击前端“下一页”或第2个页码，保持同一文件和100%缩放。
3. 观察前端页码、右侧按页对照和左侧实际PDF正文。

预期：第2/10页状态与左侧实际第2页、右侧第2页内容一致；回到第1页亦一致。

实际：前端页码/选中项及右侧文本切到第2页，但左侧PDF仍显示第一页标题和正文。不是只有空白，也不是只比较两个截图文件名：两张全景中右侧正文确实不同，左侧正文仍相同。

## 已确认的真实证据

用户指定的忽略目录新增18张截图，2,476,887字节；QA逐张重算SHA256和大小均匹配索引。

| 证据文件 | 观察 |
| --- | --- |
| e01-16-review-compare-full.png | 前端第1/10页，左右均有可辨识内容 |
| e01-17-review-page2-full.png | 前端第2/10页，右侧为第二页内容，左侧仍是上一张的第一页内容 |
| e01-14-pdf-page1-full.png / e01-15-pdf-page2-full.png | 两张特写完全相同，SHA256均 `e0c954d4ec219c69784ae1e79c06c1ed9e5db87bb793345b0e9900b2c16dc860` |
| e01-07-pdf-original-closeup.png / e01-12-pdf-page2-closeup.png | 另一视口重复出现同现象，SHA256均 `34101f4a376c86ad5224fa810cbae901d20627eaddf0f8771279bc0fbad63ded` |
| e01-13-review-pdf-zoom150.png | 前端缩放字段为150%；仅能证明字段变化，实际PDF缩放是否执行需修复后验证，不另立已确认缩放Bug |

原始CDP事件流未落盘，不伪造iframe.src实测日志；“fragment变为page=2”来自开发采集说明。QA直接读取源码确认其实现确实如此。未发现后端返回错误文件、原件损坏或未经授权写入证据。

## 源码定位与根因边界

`frontend/src/components/document/DocumentPreview.vue`：PDF分支仅 `<iframe :src="viewerUrl">`；`viewerUrl` 将同一sourceUrl拼接 `#page=${innerPage}&zoom=${zoom}`；changePage更新状态并发出update:page。该文件当前与QA已冻结副本SHA256均为 `73d7b7a512e1274e857745c2ddc86e609dec5f3e8be7663fde3c4d41aec51f5f`。

`frontend/src/views/ReviewView.vue`：currentPage同时驱动右侧currentPageRecord/pageText。因此父状态正确变化不能证明内嵌PDF已经跳页。

已确认：运行画面存在左右页错配；源码使用fragment导航且未确认实际viewer渲染页。待验证机制：当前浏览器内置viewer是否忽略同Blob fragment变化，或存在加载/导航时序问题。**不把候选根因当成已经证明的浏览器规范结论。**

## 影响与最小修复/验收

影响：审核员可能依据第二页解析文本对照第一页面原文，误判法律事实/金额/条款。虽然只读且未损坏文件，但破坏核心审核可信性，因此阻断当前前后端验收。headless空白与此有头分页错配是两件事：初始原文可见证据可通过，分页不可通过。

建议：让前端的分页/缩放控制可靠驱动实际viewer；可评估受控重建iframe等最小策略，但必须验证实际PDF画面，不能只断言URL、input或缩略项。不得通过伪造页图、关闭原件权限/摘要检查、悄悄改变原文或隐藏控制后仍宣称通过来修复。不要求引入新大型渲染依赖；若需要降级功能必须明确交付影响并重新确认范围。

回归用例：优先采用两页内容明显不同的公开合成PDF，仅在合规浏览器入口下验证1→2→1、缩略项/直接页码、100%→150%→100%，实际可辨识正文与预期页匹配，右侧按页对照同步；页签切换不得回到错误原文页。身份、原件SHA、权限、Blob释放及下载不回归。

WorkBuddy提交新的完整前端SHA和真实画面证据，QA只复测该组件与审核对照；未变后端API及28项不重复跑。写链路E01剩余段仍由QA在获准隔离状态/合成对象上另验，不由该修复代替。

QA证据摘要存于忽略目录 `local/v022-qa/e01-extra-review/integrity.json`。原截图留在用户指定位置，不提交原文/图片。没有访问敏感transcript、启动浏览器、重跑云OCR、写数据库或更改共享8180。
