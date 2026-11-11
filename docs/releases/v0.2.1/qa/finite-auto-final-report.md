# v0.2.1 有限auto补证及当前裁决

**当前是否具备放行条件：NO。整体结论：BLOCKED。**

2026-11-11。仅一次获准公开合成场景，真实本地推理和官方调用均已执行。官方返回空识别产物，未形成有效的非空云端候选，未达到用户要求的完整有效双候选证据。系统保留本地结果并正确复核，风险处理PASS，云端该样本识别质量不合格。不能把风险处理PASS替代有效双候选验收。

## 版本、授权与执行边界

- 受测业务源码 `c91547d393ca6b049e216c0051e25271d06d7359`，Fix HEAD `4fea3064de4c699ab9de65c79f23a07b8c9e4a22`；执行前后干净，未改源码。
- 候选镜像 `market-regulation-workbench:candidate-v021-c91547d393ca`，ID `sha256:92bc163c15210ec0ea9f0373db4d020f0be792dea2e2be4dc3f089727d202c0e`；实际导入 `/app/qa_core/__init__.py`，未挂业务替代源码。
- QA分支 `codex/qa-v0.2.1`，运行基线 `f381da61c0f7652227bfc1f8a229b93398679652`；新增QA执行器 `tests/run_v021_finite_auto.py`。不复跑292方法、PG六项或已通过模块，不新增重叠PASS计数。
- 用户明确批准：仅“QA021”图最多新增6次HTTP（POST≤1、PUT≤1、GET≤4）；历史具体任务403移出硬门禁；Windows整机恢复另列上线前运维验收。
- 样本 `SYN-AUTO-FINAL-01`，公开合成白底图；SHA256 `4722ea9314889ce3e0607b1818e326f0531ee92e75e9ec38d7b42c8aa849370e`。未外传任何原始测试资料，未改真值或产品质量阈值，未连接数据库。
- 预检使用UTF-8读取Docker挂载信息，确认既有检测/识别权重文件、只读模型、可写worker日志及HOME。API transport在真实本地推理返回非空文本之前拒绝任何请求；每次请求发送前持久化预算占位。

## 唯一场景实测

| 阶段 | 结果与证据 |
| --- | --- |
| 本地推理 | 真实PP-OCRv5检测/识别模型加载，非空本地候选“QA021”，页面success |
| 自然质量判断 | 现有阈值产生 `short_page`，无人工修改阈值或模拟成功 |
| 授权回退 | 此SHA的短时FILE_SHA授权；真实OfficialMinerUClient，真实HTTP transport，自动上传/下载重试均0 |
| 官方调用 | POST、GET、PUT、GET、GET共5次，全部200；一个提交、一个上传，没有重发旧未决任务 |
| 官方原始产物 | 下载ZIP及原始JSON保留。官方content_list原始内容为 `[]`，full.md为0字节；不是标准化丢失文本，也不猜测供应商为何忽略短图 |
| 云端候选 | 原始远端候选保留在routing_trace，needs_review、pages为空；不能认定为有效非空候选 |
| 最终选择 | 保留非空本地候选，`route_reason=local_quality_requires_review`，`failure_reason=remote_quality_insufficient`；未选用空云候选 |
| 复核/来源/完整性 | requires_review=true；源文件ID与页码保留；原件SHA不变；未发布知识库或正式入库 |
| 状态与幂等 | 任务completed表示保留结果的处理完成，不表示识别质量达标。相同幂等键复用同任务，新增HTTP0，新增本地推理0 |

远端API成功和原始空输出都有真实证据。**链路执行成功、风险处理PASS；要求的有效双候选验收仍BLOCKED。** 不把外部模型对单个短图的质量失败升级为产品P1，也不因质量分级允许复核就改写该证据缺口。

## 预算审计与停止

| 账本 | 已用/上限 | 本轮处理 |
| --- | --- | --- |
| 原公开合成批次 | 8/8 | 文件SHA前后相同，未清零或重用 |
| 本次批准批次 | 5/6 | POST1、PUT1、GET3，余1，不再调用 |
| 两批合计 | 13/14 | 不隐匿历史调用，保留全部远端关联和产物 |

一份样本、一个新任务、一次执行。发现空官方输出后仅离线检查ZIP/JSON，不追加请求、不开新批次、不重新POST、不重跑模型以碰运气。执行器若发现本批账本已存在将拒绝再次启动，防止重放。

## 去重后的剩余事项

| ID | 唯一主类别 | 当前裁决 / 最小解除条件 |
| --- | --- | --- |
| EV-AUTO-01 | EVIDENCE_GAP | 当前要求的有效非空双候选未取得；仅此一项必要技术补证尚未关闭。若仍要求此具体能力，需另行批准不同公开合成样本的有限补证；本轮不自行追加预算。或由用户明确批准缩减该能力并验证禁用，QA不能自行决定 |
| EXT-CLOUD-EMPTY-01 | EXTERNAL_DEPENDENCY | 本次供应商原始空输出，是EV-AUTO-01未达成的原因，不另算一个代码阻断；系统安全处理已通过 |
| EXT-BUDGET-01 | EXTERNAL_DEPENDENCY | 原预算耗尽记录保留；本次新增授权已兑现，不再把“未获新增6次授权”当当前阻断。剩余1次不足构成新的端到端场景，不擅用 |
| EXT-403-01 | EXTERNAL_DEPENDENCY | 按用户明确批准移出当前版本硬门禁，保留旧任务未解决/403和全部账本，不标PASS、不再轮询 |
| OPS-REBOOT-01 | OPERATIONAL_ACCEPTANCE | 按用户批准另列上线前运维验收，NOT_TESTED；当前本地集成只承诺已测容器恢复，不声明整机恢复 |

核心安全、Schema、当前镜像HTTP/PG、原生/PaddleOCR、缓存和容器恢复均EVIDENCE_REUSED，依据 [正式边界文件](final-acceptance-scope.md) 和 [c915候选报告](candidate-c915-qa-report.md)。四项镜像ERROR保留NOT_APPLICABLE_TO_RUNTIME_IMAGE裁决和宿主原PASS，不改统计。

暂无未关闭真实RELEASE_BLOCKER，无新确认P0/P1。**当前不需要继续安排Fix修改代码。** 不扩展为新功能或全量重测。本轮已按停止条件结束。

## 证据路径

全部原始证据位于QA忽略目录 `local/v021-finite-close/`：`approved-plan.json`、`finite-http-ledger.json`、`local-inference-success.json`、`final-result.json`、`provider-empty-evidence.json`、`old-ledger-before.json`、`execution.log`、`tasks/` 中本地/云端检查点与原始ZIP。原始完整任务/授权/路径仅本机保存；Git仅提交脱敏报告和QA执行器。

本轮不修改旧报告事实、生产服务、数据库、模型或标准答案；未Push、未Merge、未部署。
