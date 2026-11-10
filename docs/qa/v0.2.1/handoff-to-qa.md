# v0.2.1 Fix → QA：QFA-001～004 独立复验交接

- 开发分支：`codex/fix-v0.2.1`。
- 最新代码及部署脚本 SHA：`8e80f7354195c969306852fe1d4dfce6917f5528`。
- 完整245项回归冻结 SHA：`a8f7031bfd3bdc6cc7df5f9adb190a75eee8a968`；后续业务与测试内容未改变。
- 四项业务修复冻结 SHA：`73c9f10a04b2d375b2aec542b29e9ef9a1112a4e`。
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

本次定向 49/49 PASS；新增部署后的完整测试并集 245 项，239 PASS、0 FAIL/ERROR、6 PostgreSQL 条件性 SKIP。
两者不能相加。原样本 S00016 表 0 的 257 个锚点、32 处纵向合并和文字全部匹配参考，文档两张表均保留；
S00022 已拒绝、S00025 待复核，三个原文件摘要不变。全部原始记录仅在 Fix 忽略目录。

QA 固定目录中可继续使用自己的源码绑定入口（`$FixRoot` 为已固定的相邻 Fix 工作区，`$Python` 为既有项目解释器）：

```powershell
& $Python -B tests/run_v021_final_acceptance.py `
  --source $FixRoot `
  --source-sha 8e80f7354195c969306852fe1d4dfce6917f5528 `
  --api-packages (Join-Path $FixRoot '.venv-api/Lib/site-packages') `
  --output local/v021-qfa-regression
```

最终报告提交只含 Fix 文档与交接 JSON，不改变上述代码。实际工作区 HEAD 若已包含文档传输提交，
应使用最终回复提供的完整 HEAD SHA 替换 `--source-sha`；先核验其与冻结 SHA 的业务/测试差异为空。
无需切换或覆盖对方工作区，入口会核验 HEAD 与干净状态。

请重点检查：全空白与混合空白页的区别、选页空白、原表 0 横纵合并与原第二表、普通/异常 DOCX、
所有 PDF 模式的内容类型拒绝、正常图片/扫描/文字/混合/加密/损坏输入，以及启动脚本角色保护。
PowerShell 入口测试只能使用替身，不启动新交互会话。

最新 QA 的 R-01～R-08 未决项保留：质量阈值、真实官方请求授权/既有账本与恢复、真实云端质量及自动回退、
整机重启、数据库生命周期 DDL/清理授权、S00019 意图冲突。不要重交已有扩展真值或改标注迎合结果。
历史数据库 5 项 PASS 不计入本轮；重新执行任何写库/DDL 均须满足原有明确授权范围。
未自动唤醒其他会话；本次通过正式 Git 文件交接，不声称已通知协调器。
未 Push、合并 main、生产部署或安装依赖。用户在四项修复之后追加了本地部署和服务检查授权，实际结果见下。

## 用户追加的本地部署与容器整理

当前只保留一个 `market-regulation` 项目：app、PostgreSQL、MySQL、Redis 四个容器；用户明确保留后两者。
实际入口 `http://127.0.0.1:8180`，旧8181和匿名QA入口已撤销。应用镜像为
`market-regulation-workbench:local-f6affa00a3702d5a`，镜像业务版本为 a8f7031 完整 SHA。
同一持久 state 目录已验证跨容器重启、项目合并后仍可读取原任务/结果；没有删卷或清理原数据。
已删除13个旧/临时容器、5份旧候选/QA镜像和2个重复标签；3个历史QA库卷及私密挂载记录均保留。
历史QA运行资源现已移除，后续恢复应读取保留清单并按原授权建立临时环境，不能假定旧容器/镜像仍存在。

本机实际验证：访问认证、合成两页原生PDF上传→本地解析→用户现有PostgreSQL入库→幂等，成功；
数据库仅新增1份合成记录，8份旧文档均保留，未做DDL/DELETE。非root容器合成图实际PaddleOCR成功，24字、仍需人工复核。
官方MinerU仅GET查询一条历史完成任务，HTTP200、code=0、关联匹配；未创建任务、上传文档、续期过期授权或清空预算。
工作台默认云端开关关闭，真实云端批次/自动回退的未决项仍保留。

请补充验收新入口、双引擎/表格本地模型挂载、数据库映射、权限、持久任务/结果和重启边界。
镜像沿用既有FastAPI0.162.0/uvicorn0.54.0，宿主完整回归API环境为0.115.12/0.34.2；未升级或混装依赖。
已有容器HTTP/入库/OCR实测不能代替镜像全套独立QA。数据库生命周期、真实云端质量与Windows整机恢复均不得虚构PASS。
使用与回滚说明见 `deploy/local/README.md`；记录在Fix忽略目录 `local/v021-qfa-fix/` 和 `local/docker-cleanup-20261110/`。
