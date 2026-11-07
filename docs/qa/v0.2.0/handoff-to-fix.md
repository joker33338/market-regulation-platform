# v0.2.0 正式开发交接：READY

当前版本 v0.1 已独立通过本地集成验收。

- 受测业务源：fix/round1，`d2a4c673c596945be14fa4d91a995fd8086e2b31`。
- v0.1 PASS 的真实 QA 提交：`75c9c1c5e1c263ddc563e8d73ac09ab091789986`。
- 已执行的 v0.1 测试提交：`4042a23c966c20f94eef17f3c3fc10d7d5f7702a`。
- 结论：120 个唯一核心用例全部 PASS，五个 Bug 全部复测关闭；没有已确认的未解决 P0/P1。
- 本交接最终传输 SHA 在提交后由 Git/QA 回复提供，不能在文件中自引用。

## 交付任务

实现 DUAL-001 至 DUAL-005：本地优先、质量/法律复核信号、逐文件外传授权、有界官方兜底、双结果来源/数据库/RAG兼容。需求、计划及可执行验收分别见 01/02/03。

复用现有 DocumentParser、PaddleOCRService、PaddleStructureService、quality.py、OfficialMinerUClient、MinerUService、PostgresResultSink 和法律 pipeline，不重复开发。最小策略层编排即可；不要简单改变旧任务 mode 绕过恢复校验，不要用相同 parse_id 覆盖先前结果。

默认沿用现有独立 Fix 工作树和 `fix/round1` 角色分支，已验收的 v0.1 提交必须保留。协调器如需使用新的版本分支，应先明确角色及基线关系，不重写现有历史、不移除工作树。数据库/接口增量先解释兼容性和复用边界，不能默认迁移或启动服务。

## 测试交付

QA 已提供 A–J：现有能力五项实际 PASS，新策略十项待实现 SKIP。Fix 实现后提供调用真实策略的测试适配器及映射说明，由 QA 绑定复验；不能把参考替身、预设结果或 SKIP 称为功能通过。

交回完整 Fix SHA、实现清单、配置、实际入口/接口变更、测试适配器、命令及未验证事项。QA 将执行新旧解析、云端授权/故障/预算、PostgreSQL 和复核后 RAG，失败则继续交接。

## 不随 READY 放行的事项

不允许原语料外传；Mock/公开合成样本优先；默认禁止云端回退，只有适用的明确授权才可候选。不得自动部署生产、下载本地 MinerU 模型、修改正式数据库、Push 或合并。泛文档/Excel/通用表格语义继续待确认。

机器协议见 handoff.json：gate_status=PASS 是前一版已验收，handoff_status=READY 是下一版可开发，不是下一版已验收。现有 Orchestrator 仍缺完整写调度适配器；QA 通过 Git 发布并做只读校验，等待协调器接收，不声称已自动唤醒 Fix。
