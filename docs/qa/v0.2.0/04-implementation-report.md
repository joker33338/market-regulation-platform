# v0.2.0 实现与验证报告

## 基线与交接

- 角色：Agent B / Fix；沿用独立 Fix 工作树。
- 正式交接分支：`feat/ocr-dual-engine-v0.2`，在已有 Fix 提交上创建；`fix/round1` 历史全部保留。
- 已验收 v0.1 基线：`d2a4c673c596945be14fa4d91a995fd8086e2b31`。
- QA 测试提交：`4042a23c966c20f94eef17f3c3fc10d7d5f7702a`。
- QA PASS 提交：`75c9c1c5e1c263ddc563e8d73ac09ab091789986`。
- v0.2.0 READY 测试/需求提交：`a0c20a9e698d53ce06cd97dceaa1aa188dd042f3`；补充说明：`d3c538643b4114c9e99acee002d1db77cd7ccbc1`。
- 安全审查后分别接收为 `9c8fa64`、`5011b39`、`18f72bd`、`e6c409e`，无冲突，报告摘要已核验。用户明确授权本会话按 Git 交接开发，协调器保持只读。
- 最终受测代码提交：`8badb995592771ff099cf52570621ba29ad37533`。本报告后的交接提交只包含文档，其完整 SHA 由 Git 和会话交接提供，避免文档自引用。

## 功能完成情况

| ID | 实现及涉及位置 | 验证 |
| --- | --- | --- |
| DUAL-001 | 新增 `dual_engine.py::DualEngineRouter.parse`，组合原有 DocumentParser；`document_router.py` 增加 PDF 网格/复杂布局提示；原生、PaddleOCR、PP-StructureV3 保留 | QA A、B、C；本地策略不调用远程 |
| DUAL-002 | `quality.py::assess_document` / `RoutingThresholds` 增加空/短页、字符比例、非法日期、金额复核及回退原因；不修改原文 | QA D、E；原有质量回归 |
| DUAL-003 | `DualEngineRouter.authorization` 校验开关、请求意图、用户+哈希许可、期限及敏感标记；每次传输前复查；API 新增可选策略字段 | QA G；请求标志伪授权、混合批次、过期/非有限期限、语料禁止、撤销许可及旧客户端兼容 |
| DUAL-004 | `_remote` 复用 OfficialMinerUClient 与独立 MinerUService 子任务；`MinerUClient.before_request` 计入每次请求/重定向；持久化预算、限流、有界重试和未知 POST 保护 | QA F；调用/文件/页预算；创建后中断复用同一任务；失败保留本地 |
| DUAL-005 | 两端候选及最终选择保存在 `quality.routing_trace`；`MinerUService._local` 保存最终快照后调用原 PostgresResultSink；API 返回来源/复核摘要及失败诊断；原 RAG 闸门保持 | QA H、I、J；数据库提交后断连、幂等/冲突/回滚、复核后检索 |

使用现有 metadata/quality JSON 字段，无 PostgreSQL 迁移，无现有响应字段删除。旧请求未带新增参数时仍可提交；双引擎开关开启后默认本地处理，云端回退默认关闭。

其他变更：上传页面增加策略选择和需复核状态；启动脚本支持复用已有 Python/API 依赖路径；数据库测试工具增加 `--include-v02`；全回归脚本增加 `-DualEngine` 并输出方法级结果 JSON。配置和入口详见 `docs/mineru-integration/v0.2.0.md`。

## 本地提交

| 完整 SHA | 内容 |
| --- | --- |
| `943f942c55aad331a97bf8e6ce32c96c3692c73d` | DUAL-001 至 DUAL-005 实现、API/页面、质量及验收适配器 |
| `a5065d7b4fcf68caeb54c376f1eea7bf1db5a4eb` | 追加许可撤销、文件/页预算和 OCR 故障边界测试 |
| `8badb995592771ff099cf52570621ba29ad37533` | requirements 合并、Docker/引用更新及全回归入口 |

## 实际测试

先执行 QA 基线：15 项中 5 通过、10 项新策略未绑定而跳过；没有把这些跳过计作通过。随后绑定 `tests.dual_engine_adapter:run_scenario`，其不按 case_id 返回预设结论，只替换 OCR/HTTP 输入并读取真实业务结果。

| 阶段与受测 SHA | 命令 | 实际结果 |
| --- | --- | --- |
| 双引擎目标验证，943f942 对应实现 | `python -B -m unittest tests.test_v02_dual_engine tests.test_dual_engine_policy -v` | 当时 26 项：25 通过，I 因无独立库跳过 |
| 专用 PostgreSQL，`943f942c55aad331a97bf8e6ce32c96c3692c73d` | `python -B tests/round01_isolated_postgres.py --source . --output local/v02-postgres --include-v02` | 20/20 通过，0 跳过；包含完整 A–J 和原有 5 项数据库回归 |
| 新增边界验证，a5065d7 对应测试 | 三个新增 `test_dual_engine_policy` 方法 | 3/3 通过 |
| 最后一次完整回归，`8badb995592771ff099cf52570621ba29ad37533` | `./scripts/run_fix_regressions.ps1 -DualEngine` | 149 项：143 通过、6 条件跳过、0 失败 |

完整回归的 6 项均为数据库条件用例，全部已在前述独立 PostgreSQL 阶段实际通过。按方法 ID 合并两阶段证据，149 个唯一用例均有 PASS 记录；**不是同一 SHA 下单次 149 项无跳过执行**。独立数据库之后，解析业务代码仅修改缺依赖提示文字；其余为新增测试、依赖清单和文档。QA 仍需对最终交接 SHA 独立复验，未修改 QA 的版本闸门或宣称 v0.2.0 已验收 PASS。

独立数据库：只用本地已有镜像、内部网络，无宿主映射端口；执行后已停止，数据保留。没有连接业务库、生产库或执行生产迁移。数据库场景真实注入提交后断连，恢复后行数与原记录摘要一致。

附加检查：页面 JavaScript 和启动 PowerShell 语法通过；`git diff --check` 通过；43 条唯一依赖约束与实际已有环境版本全部匹配。没有重新安装依赖、重建环境或下载模型。

## 依赖整理

仅保留 `requirements.txt`，合并原 API/local/OCR/lock 的条目并去重，保留已验证核心版本。PyYAML 采用实际 OCR 环境 `6.0.2`，解决旧环境快照 `6.0.3` 冲突；`torch==2.7.1` 接受现有 `2.7.1+cpu`。Docker 保留先安装指定 CPU wheel 的方式，再安装统一清单。没有清理现有环境中的任何包。

## 证据摘要

原日志及数据库环境文件保持忽略，不纳入 Git。可用以下 SHA256 核对 Fix 本地原始证据：

| 文件 | SHA256 |
| --- | --- |
| `reports/fix-regression.log` | `0601e5983a4290b44c8d2dc1cacce11995189a0e65b830f1806d80100075e4d4` |
| `reports/fix-regression.json` | `e299443b5055d193451d2ef1160dd4e4ffcdff5780ae9340b0383bfbfbc9927b` |
| `local/v02-postgres/database-tests.log` | `93b47d8a92dca4145763832b657af6d1d60d19b4852b4a052edeb532695d8047` |
| `local/v02-postgres/database-execution.json` | `d1d0af076177d7d5fd299fa62b8c9063fddb9249ebf48cbda872d6a18ef3dd29` |

## 剩余限制与风险

- 本轮 OCR 输入和官网 HTTP 使用合成替身/Mock，未重复运行实际模型性能或云端准确率测试。GPU、真实复杂文档质量、批量成本和生产部署未验证。
- 未执行统一清单的全新安装或新 Docker 镜像构建；现有环境匹配不能替代跨平台依赖解析/镜像验收。
- DOCX 无可信物理页数时保留原生结果，不绕过云端页预算。质量阈值仍需公开标注样本校准。
- 已持久化的最终结果按不可变快照重试；若需修复输入/模型后重新解析，应提交新任务。许可文件更新需受控重启，过期检查在请求前执行。
- 本地模型运行周期沿用原实现，未宣称完成跨任务模型常驻/性能优化。
- 没有自动 Push、部署或通知协调器。通过本分支和正式文档交给 Agent A，等待其独立验收。
