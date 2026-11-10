# v0.2.1 Fix → QA：QFA-001～004 独立复验交接

- 开发分支：`codex/fix-v0.2.1`。
- 冻结代码 SHA：`73c9f10a04b2d375b2aec542b29e9ef9a1112a4e`。
- 修复起点：`a860abfa84bc2664bb119ae8f5b80c6794e6e23c`。
- QA 测试提交：`78b7e05e747656414badd8350c83d48b672ecc16`，已安全接收为 `509f823ae8217855e3a4ea6ed1b98cfdd62f0fac`。
- 接收的 QA 报告提交：`0881807ee0524503c54b0f08fcca96c922f9828e`。
- 当前状态：Fix 自测完成，等待 QA 独立复验；版本闸门仍 BLOCKED，不构成发布放行。

| 问题 | 修复 | 修改文件 |
| --- | --- | --- |
| QFA-001 | 整文空白 PDF 改为 needs_review，混合文档空白页仍保留 | qa_core/document_parsing/document_router.py |
| QFA-002 | DOCX vMerge 映射 rowspan，保留锚点、文字、来源与第二表 | qa_core/document_parsing/native.py |
| QFA-003 | 在渲染/OCR 前拒绝实际不是 PDF 的 .pdf 文件 | qa_core/document_parsing/document_router.py |
| QFA-004 | 兼容当前与旧角色分支，继续拒绝错误角色/未知分支 | scripts/start_agent_workspace.ps1 |

新增测试为 `tests/test_v021_qfa_pdf.py`、`tests/test_v021_qfa_docx.py`、`tests/test_v021_agent_launcher.py`；
QA 原有三项失败用例的断言未修改。精确修复提交及函数见 `fix-report.md` 最新批次。

本次定向 49/49 PASS；完整测试并集 243 项，237 PASS、0 FAIL/ERROR、6 PostgreSQL 条件性 SKIP。
两者不能相加。原样本 S00016 表 0 的 257 个锚点、32 处纵向合并和文字全部匹配参考，文档两张表均保留；
S00022 已拒绝、S00025 待复核，三个原文件摘要不变。全部原始记录仅在 Fix 忽略目录。

QA 固定目录中可继续使用自己的源码绑定入口（`$FixRoot` 为已固定的相邻 Fix 工作区，`$Python` 为既有项目解释器）：

```powershell
& $Python -B tests/run_v021_final_acceptance.py `
  --source $FixRoot `
  --source-sha 73c9f10a04b2d375b2aec542b29e9ef9a1112a4e `
  --api-packages (Join-Path $FixRoot '.venv-api/Lib/site-packages') `
  --output local/v021-qfa-regression
```

报告提交只含 Fix 文档与交接 JSON，不改变上述代码。实际工作区 HEAD 若已包含文档传输提交，
应使用最终回复提供的完整 HEAD SHA 替换 `--source-sha`；先核验其与冻结 SHA 的业务/测试差异为空。
无需切换或覆盖对方工作区，入口会核验 HEAD 与干净状态。

请重点检查：全空白与混合空白页的区别、选页空白、原表 0 横纵合并与原第二表、普通/异常 DOCX、
所有 PDF 模式的内容类型拒绝、正常图片/扫描/文字/混合/加密/损坏输入，以及启动脚本角色保护。
PowerShell 入口测试只能使用替身，不启动新交互会话。

最新 QA 的 R-01～R-08 未决项保留：质量阈值、真实官方请求授权/既有账本与恢复、真实云端质量及自动回退、
整机重启、数据库生命周期 DDL/清理授权、S00019 意图冲突。不要重交已有扩展真值或改标注迎合结果。
历史数据库 5 项 PASS 不计入本轮；重新执行任何写库/DDL 均须满足原有明确授权范围。
未自动唤醒其他会话；本次通过正式 Git 文件交接，不声称已通知协调器。
未 Push、合并 main、部署、更新运行服务、安装依赖、写数据库或调用真实外部 OCR API。
