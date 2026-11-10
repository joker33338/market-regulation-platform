# v0.2.1 最终独立 QA 问题交接

版本闸门 **BLOCKED**，代码回归 **FAIL**。本交接不是发布放行或新版本开发授权。Fix 源码尚未被 QA 修改，全部修复应在 Fix 的指定分支完成，交回新完整 SHA 后再独立验收。

- 受测分支：`codex/fix-v0.2.1`。
- 受测 SHA：`a860abfa84bc2664bb119ae8f5b80c6794e6e23c`。
- QA 起始 SHA：`3bdcfdf007a30d29201760518263d12bca05924c`。
- 可直接核验的 QA 测试提交：`78b7e05e747656414badd8350c83d48b672ecc16`。
- QA 报告提交：以包含本文的实际 Git 提交为准，执行方最终回复提供完整 SHA；不在文件中伪造自身提交号。
- 方法级去重：232 个，228 PASS、3 FAIL、1 BLOCKED。PostgreSQL 5 项的补跑替换原 SKIP，不重复加总。HTTP、模型、语料、质量和容器探针单列。

## 公共复现入口

在 QA 固定目录中，使用已有 Python 与 API 依赖；不安装环境、不切换分支。命令会测试明确指定的 Fix，仅把证据写入 QA 忽略目录：

```powershell
$FixRoot = (Resolve-Path ../market-regulation-platform-fix).Path
# $Python 指向已有项目 Python，不使用 WindowsApps 的占位程序。
& $Python -B tests/run_v021_final_acceptance.py `
  --source $FixRoot `
  --source-sha a860abfa84bc2664bb119ae8f5b80c6794e6e23c `
  --api-packages (Join-Path $FixRoot '.venv-api/Lib/site-packages') `
  --output local/v021-final-followup
```

预期当前版本稳定复现 3 个新增失败；测试以合成最小样本复现，不需要真实语料或云端。完整导入来源和测试路径在结果 JSON 中，源码后续变化必须换成新的完整 SHA；入口不允许把脏源码称作旧提交测试。

## QFA-001：空白 PDF 负例仍报告成功

- 优先级：P2；样例：S00025。
- 需求依据：最新扩展包“样本意图与安全预期”的异常文件契约明确要求拒绝/报错，不允许成功。不是把合法混合文档中的空白页定义为错误。
- 模块：本地 PDF 解析状态聚合。
- 复现：公共入口中的 `FinalAcceptanceEdges.test_blank_negative_pdf_cannot_report_success`；原始场景结果 `S00025-parse-summary.json`。
- 预期：整份空白负例明确拒绝、失败或待复核状态，不能报告无正文 success；正常文档内空白页不加载模型的既有行为保留。
- 实际：document/page 状态 success，正文 0 字，质量含 empty_page，requires_review=true。
- 日志摘要：断言 `'success' == 'success'`。不是没有复核告警，也没有证据称其已绕过法律审核入库。
- 源码：`qa_core/document_parsing/document_router.py` 的 `_parse_pdf` 空白页分支与 `parse` 状态聚合。
- 已确认根因：空白分支生成默认 success 页面，聚合只将 failed/needs_review 页面提升状态，质量告警不回写该状态。
- 建议：区分整文无正文与混合文档空白页，保持 empty_page、来源和人工复核信息。
- 验收：最小回归通过；S00025 不再 success；既有空白页不加载 OCR、原生文本及混合文档测试不退化。

## QFA-002：DOCX 纵向合并缺少 rowspan 映射

- 优先级：P2；样例：S00016、TAB-DOCX-01。
- 需求依据：本轮 Word/复杂表格完整性和扩展参考的实际 OOXML 合并结构；不是因参考只覆盖表 0 而要求删除第二张表。
- 模块：DOCX 原生表格标准化。
- 复现：公共入口中的 `FinalAcceptanceEdges.test_native_docx_preserves_vertical_merge_span`。真实对照及计数见 `execution-summary.json` 的 docx_scope。
- 预期：`vMerge restart/continue` 对应同一逻辑单元格锚点和正确 rowspan，内容/行列/来源保留。
- 实际：两行最小合成被输出成两个 rowspan=1 单元格。真实表 0 为 330 格/0 个纵向合并；参考为 257 个锚点/32 个 rowspan>1。
- 日志摘要：`AssertionError: 2 != 1`。
- 源码：`qa_core/document_parsing/native.py:docx_document`。
- 已确认根因：读取 vMerge 后只设置警告，生成 HTML 时仅编码 gridSpan/colspan，没有追踪纵向合并及跳过延续格。
- 建议：按 OOXML 网格列追踪 restart/continue，保留混合横纵合并的锚点；不要改真值或摊平重复内容以提高匹配率。
- 验收：最小回归通过；原表 0 与参考单独对比跨度/文字，真实第二表继续保留；横向合并、普通 Word、异常 DOCX 及页面来源回归通过。

## QFA-003：伪造 PDF 扩展名未被内容校验拒绝

- 优先级：P2；样例：S00022。
- 需求依据：最新异常文件契约，以及文件类型识别/输入验证要求。
- 模块：本地文件类型识别、PDF 路由。
- 复现：公共入口中的 `FinalAcceptanceEdges.test_png_disguised_as_pdf_is_rejected`。原场景的 PNG 魔数、`is_pdf=False`、`format=Image` 见 `type-mismatch.json`。
- 预期：内容不是 PDF 的 .pdf 负例拒绝或明确 failed；正常图片仍从图片入口处理。
- 实际：PyMuPDF 接受 PNG 内容并包装成可读页面，随后 OCR，结果 success。合成 PNG 改扩展名同样 success。
- 日志摘要：`'success' != 'failed'`。未发现内存限额绕过或远程外传，不能无证据升级为 P0/P1 安全漏洞。
- 源码：`document_router.py` 的 `_check_path`、`parse`、`_parse_pdf`。
- 已确认根因：按扩展名选择分支后未检查真实文档类型；把 fitz.open 成功当成 PDF 类型已验证。
- 建议：在昂贵推理之前核验真实类型；合法格式与资源限额保持一致，拒绝与扩展名不符的输入。
- 验收：最小回归通过；S00022 拒绝/失败；扫描/文字/混合 PDF、正常图片、加密及损坏负例不退化。

## QFA-004：固定分支与旧启动脚本守卫不兼容

- 优先级：P2；样例：合成环境案例 ENV-START-01，不涉及真实文件。
- 需求依据：当前已明确采用 codex/fix-v0.2.1、codex/qa-v0.2.1 固定分支，既有入口应与之兼容。
- 模块：工作区启动脚本。
- 复现（修复前已实际执行）：`pwsh -NoProfile -File ../market-regulation-platform-fix/scripts/start_agent_workspace.ps1 -Role Fix`。
- 预期：正确角色的固定分支通过守卫，错误角色/未知分支继续被拒绝。
- 实际：在配置加载和交互会话启动之前即报 `Expected branch fix/round1; found codex/fix-v0.2.1`。
- 源码/根因：`scripts/start_agent_workspace.ps1` 的 `$expected` 仅写旧 round1 分支。
- 建议：最小兼容当前角色分支映射；不改名分支或迁移目录，不移除角色保护。
- 验收：用隔离测试覆盖当前两角色、错误角色与未知分支；不要为测试自动启动新的交互会话。PowerShell 语法检查通过，现有入口不被覆盖。

## 质量观测与边界（不得擅改标准）

三栏 LAYOUT-01 当前 CER 89.60689%，无线表 auto 未提取、强制 Structure 精确，均应工程分析；业务质量阈值尚未由用户确定，不能把这些单独称作已确认根因的代码 Bug，也不能宣布质量 PASS。DOCX 原始评估按一份参考对两张输出表会有作用域差异，另有明确 vMerge 缺陷证据，必须分开解释。

R-04 归因材料已纳入，R-02 扩展真值已完成全部新任务评估。不要让用户重交已交付的真值，不要修改 labels.csv、原真值、冻结包或失败样本。

原官方批次授权已经过期，旧 SHA 预检与账本全部保留；真实官方请求本轮为 0。恢复已有任务、续期、当前 SHA 的预检、固定地址隔离和预算必须正式审阅，不能盲目重 POST、清账本或新建批次绕过历史占位。

数据库只复用现有 QA Schema，5 项 PASS；不得为使生命周期用例通过擅自 CREATE/DROP Schema、DELETE 或操作生产库。Windows 重启的完整验收和业务质量阈值仍需用户确认，不自动重启电脑或关闭安全策略。

完整报告见 `final-acceptance-report.md`，机器闸门见 `version-gate.json`。等待协调器接收本 Git 交接；本轮没有自动唤醒其他会话或启动 Fix 开发。
