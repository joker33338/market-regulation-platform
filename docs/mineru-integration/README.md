# 本地可用版本

本轮目标已跑通：文件上传 → 官网精准解析 → PostgreSQL 现有审阅表。
真实验证只使用合成单页 PDF，未上传真实语料。服务器部署按用户要求暂停。

1. 复用已验证的现有环境；依赖统一维护在 requirements.txt，不升级原 OCR/BGE 环境。
2. 使用忽略的 local/parsing-runtime.json 配置官网 Key、工作台访问码和显式测试库。
3. 执行 `scripts/start_parsing_app.ps1 -Port 8180`，打开 http://127.0.0.1:8180。
4. 从本地 local/workbench-access-code.txt 读取工作台访问码。不要把官网 Key 当作页面访问码。
5. 选择获准的测试文件，点击上传；任务完成后查看数据库记录 ID。
6. 在 DBX 中打开 document_review.documents 查看正文、Markdown 和 JSON；pages/blocks 为分层明细。

页面显示当前 Provider、是否连接 PostgreSQL，以及文件是否发往官网。
同一页面选择内重试保留请求键；选新文件开始新任务。识别文本仍需复核。
只有完成结果保存和配置的数据库写入，任务才公布 completed。

当前结果库复用已有 schema，无迁移。任务管理另用本地 SQLite；不自动发布 public 法条知识库。
批量大文件、复杂表格质量、多用户部署和分布式队列仍需后续验收。

最新当前版本修复：`0cfb4f2`，解决本地批次隔离和 Windows 原始包覆盖问题。
完整回归：`scripts/run_fix_regressions.ps1`，118 项中 114 通过、4 条件跳过。
独立 QA 工作树可传入 `-Python` 与 `-ApiPackages` 复用已有依赖；不需要新建环境。
此前 PostgreSQL 幂等与回滚另行 2/2 通过、真实 HTTP 上传至 PostgreSQL PASS，属于历史 Fix 实测，未作为本次 QA 独立 PASS。
v0.1 已由 QA 在 `75c9c1c` 提交验收 PASS（120 个唯一核心用例）。
v0.2.0 双引擎实现见 [使用与验收说明](v0.2.0.md)，默认本地优先，云端回退需要逐文件授权。
原 requirements-api/local/ocr/lock 清单已统一为 requirements.txt，保留现有已验证版本；没有重新安装环境或模型。
双引擎及收尾变更等待 Agent A 对最终 Fix SHA 独立回归，不能把上一版 PASS 当作本版验收。
详见 [Fix 交接](../qa/round01/handoff-to-qa.md) 和本目录设计/测试记录。
