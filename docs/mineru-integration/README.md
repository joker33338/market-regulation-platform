# 本地验收版本 v0.2.0

文件上传 → 本地优先解析 → 获准时官网增强 → PostgreSQL 现有审阅表。
开启双引擎需设置 `DUAL_OCR_ENABLED=1`；云端回退默认关闭，服务器部署按用户要求暂停。

1. 复用已验证的现有环境；依赖统一维护在 requirements.txt，不升级原 OCR/BGE 环境。
2. 使用忽略的 local/parsing-runtime.json 配置官网 Key、工作台访问码和显式测试库。
3. 执行 `scripts/start_parsing_app.ps1 -Port 8180`，打开 http://127.0.0.1:8180。
4. 从本地 local/workbench-access-code.txt 读取工作台访问码。不要把官网 Key 当作页面访问码。
5. 选择测试文件，点击上传；双引擎默认本地处理，只有逐文件许可适用时才能云端回退。
6. 在 DBX 中打开 document_review.documents 查看正文、Markdown 和 JSON；pages/blocks 为分层明细。

页面显示当前 Provider、是否连接 PostgreSQL，以及文件是否发往官网。
同一页面选择内重试保留请求键；选新文件开始新任务。识别文本仍需复核。
只有完成结果保存和配置的数据库写入，任务才公布 completed。

当前结果库复用已有 schema，无迁移。任务管理另用本地 SQLite；不自动发布 public 法条知识库。
批量大文件、复杂表格质量、多用户部署和分布式队列仍需后续验收。

当前已验收代码：`8badb995592771ff099cf52570621ba29ad37533`。
Agent A 已于 2026-11-07 独立验收 PASS：149 个唯一源码测试方法全部通过，0 失败、0 跳过、0 阻塞。
正式 QA 提交：`0490c9562cdaf85ac1c0731d0a4b77bed08986f8`；已接收到开发分支，报告摘要与方法清单核验通过。
验收按阶段补齐并按方法 ID 去重，包含 A–J、已有回归、获准 PostgreSQL 集成；辅助真实本地 HTTP 不重复计入 149。
早期 Fix 自测的数据库条件跳过不再代表最终 QA 状态；原始阶段结果保留在实现报告中。
独立 QA 工作树可传入 `-Python` 与 `-ApiPackages` 复用已有依赖；不需要新建环境。
v0.1 已由 QA 在 `75c9c1c` 提交验收 PASS（120 个唯一核心用例）。
v0.2.0 双引擎实现见 [使用与验收说明](v0.2.0.md)，默认本地优先，云端回退需要逐文件授权。
原 requirements-api/local/ocr/lock 清单已统一为 requirements.txt，保留现有已验证版本；没有重新安装环境或模型。
正式结论见 [v0.2.0 QA 闸门](../qa/v0.2.0/version-gate.json)、[唯一方法覆盖](../qa/v0.2.0/qa-coverage.json) 和 [QA 回归报告末尾结论](../qa/round01/06-regression-report.md)。
该 PASS 限定本地开发、Mock 及获准集成兼容范围；真实官网识别质量、全语料准确率、全新依赖安装/镜像构建和生产部署仍未验收。不自动开启下一版本、Push 或部署。
此前的 [Fix 交接](../qa/v0.2.0/handoff-to-qa.md) 与结构化交接保留为历史记录，其待验收状态已由上述 QA 闸门更新。
