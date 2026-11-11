# v0.2.1 最终验收边界与有限收尾

**当前是否具备放行条件：NO。整体门禁：BLOCKED。**

2026-11-11。当前没有新确认的未关闭 RELEASE_BLOCKER，也没有证据要求继续安排 Fix 修改代码。用户已批准6次补证、旧具体任务移出门禁、整机恢复另列运维；补证已使用5次，官方原始产物为空，有效双候选证据仍未取得。最新执行和停止结论见 [有限补证报告](finite-auto-final-report.md)。下方方案保留审批前设计，并注明最新决定。

## 1. 本轮核验的版本

- 业务源码：`c91547d393ca6b049e216c0051e25271d06d7359`。
- Fix当前HEAD：`4fea3064de4c699ab9de65c79f23a07b8c9e4a22`，工作区干净；与受测源码的差异为交接/审计文档，无业务代码变化。
- QA起点：`f3178e79bc533d1db7828f6734d3e2172f235293`，分支 `codex/qa-v0.2.1`，执行前干净。
- 镜像：`market-regulation-workbench:candidate-v021-c91547d393ca`；实际ID `sha256:92bc163c15210ec0ea9f0373db4d020f0be792dea2e2be4dc3f089727d202c0e`，revision与源码一致。57文件比对证据仍适用。
- 本轮仅只读核对版本、源码布局、既有报告和私有账本，并准备公开合成样本；**未重跑全量、未请求云API、未启动服务、未写库或改变模型/配置。**

## 2. 正式交付范围

按本轮用户任务，交付对象是后端MVP和上述候选镜像。

1. PDF/DOCX/图片既有解析、原生文本、本地PaddleOCR、PP-StructureV3、既有MinerU云解析、安全约束下的auto、任务状态/幂等/持久化、低质风险处理、复核提示、原件及来源追溯。
2. 法规结构/清洗/切分、父子Chunk、BGE-M3、PostgreSQL版本化存储，以及已实现的构建、检索、发布授权、发布/回滚、离线预览与质量提示。不承诺自动发布每份解析文档；document_review保存和预览不等于正式知识库发布。
3. 数据/Schema隔离、授权/预算/资源限额、超时及异常处理、已有容器恢复。独立前端、多实例、外部源迁移不自动纳入。

质量按已确认分级：识别达标、识别不合格但风险处理正确、严重安全/数据缺陷分别记录。低质转复核不能改写OCR准确率；关键错误不得自动发布。S00019保持SAFE_REJECT。标准答案和断言不变。

## 3. 可复用证据（全部标记 EVIDENCE_REUSED）

| 证据 | 源码/环境与原报告 | 有效范围 |
| --- | --- | --- |
| 292方法：285 PASS、7 SKIP；PG六项同ID补跑后291 PASS、1 SKIP | c915；[安全与Schema复测](schema-and-security-qa-report.md)；`local/v021-security-retest/full-valid-fixtures/`及`pg-six-final/` | 当前业务源码未变；不叠加重复方法，不将最后Windows symlink跳过涂绿 |
| QRC-001、合法缓存恢复、限额、幂等 | c915宿主及当前镜像；上述报告与[c915候选报告](candidate-c915-qa-report.md) | 原缺陷关闭，不要求Fix再次修改 |
| 真实PG六项、Schema六探针及四对抗检查 | c915；同上两报告 | 正常生命周期、路径/缺表拒绝、临时遮蔽/vector/FK/所有者拒绝；仅合成和新测试域；无真实ACTIVE误写 |
| Compose入口、HTTP鉴权/跨用户、入库与容器恢复 | c915镜像；候选报告；`local/v021-c915-final/candidate-http-2b6bfb37/` | 独立QA state、真实入口与PG；不能外推整机恢复 |
| 真实本地OCR、原生优先、短图复核与幂等 | c915镜像、断网、真实模型；候选报告；`real-local-correct/` | 普通图完成且有真实文字；不外推当前有效双引擎链路已测 |
| PP-StructureV3、已标注识别质量、真实BGE及离线专项 | [收尾报告](release-closure-qa-report.md)、[离线专项](offline-ingestion-final-qa-report.md) | Structure真实质量为bf66证据、BGE为离线专项8ecff886证据；相关模型封装/切分/向量代码未由本轮c915安全修复改写，保留原SHA，不称当前重新推理。新安全helper的真实OCR/原生路径已有当前补证 |

旧报告、失败日志与错误摘要均原样保留。本轮没有新增测试方法通过数。

## 4. 唯一问题登记及六类归属

每行一个主类别；R-01～R-08是验收视角别名，不再创建重复问题。已关闭缺陷的 RELEASE_BLOCKER 类别表示缺陷原本性质，不表示仍阻塞。

| 唯一ID/别名 | 主类别 | 当前事实及门禁处理 |
| --- | --- | --- |
| R01-001/DOC-001 | RELEASE_BLOCKER | 空文本状态旧缺陷已关闭；历史清单及当前回归复用 |
| R01-002/OCR-001 | RELEASE_BLOCKER | 中文路径网格旧缺陷已关闭 |
| R01-003/DOC-002/GAP-007 | RELEASE_BLOCKER | Docker资源缺失旧缺陷关闭；不是本次四个宿主测试ERROR |
| R01-004/SEC-001 | RELEASE_BLOCKER | ZIP产物保护旧缺陷已关闭 |
| R01-005/DOC-003 | RELEASE_BLOCKER | 批次隔离/恢复旧缺陷已关闭 |
| QFA-001 | RELEASE_BLOCKER | 空PDF状态旧缺陷已关闭 |
| QFA-002 | RELEASE_BLOCKER | DOCX合并旧缺陷已关闭 |
| QFA-003 | RELEASE_BLOCKER | 扩展名/内容校验旧缺陷已关闭 |
| QFA-004 | RELEASE_BLOCKER | 启动脚本旧缺陷已关闭 |
| QRC-001/R-08安全部分 | RELEASE_BLOCKER | 最终缓存绕过已关闭，四子场景通过 |
| SAFE-001 | RELEASE_BLOCKER | 新输入/候选缓存资源门禁已有证据，最终缓存遗漏另以QRC-001登记并已关闭 |
| ROUTE-001 | RELEASE_BLOCKER | 无线表启用时的结构路由修复已有真实证据；不要求所有路由95%匹配 |
| REVIEW-001 | RELEASE_BLOCKER | 顶层复核信号修复已验证，不等同模型识别准确 |
| SCA-001/R-07隔离部分 | RELEASE_BLOCKER | 预防性防护已测通过；无证据证明此前已经发生跨域污染 |
| SCA-002 | RELEASE_BLOCKER | 预防性启动DSN隔离已测通过，无新事故声明 |
| EV-AUTO-01/R-05 | EVIDENCE_GAP | 真实链路已执行，但官方原始内容为空，有效双候选仍缺证；正式仍承诺此能力，解除前整体BLOCKED |
| ENV-IMAGE-01 | ENVIRONMENT_LIMITATION | 四个镜像ERROR见下一节，宿主证据复用；不作为业务缺陷 |
| ENV-SYMLINK-01 | ENVIRONMENT_LIMITATION | Windows symlink跳过保留；既有Linux覆盖不改写本次SKIP |
| ENV-HARNESS-01 | ENVIRONMENT_LIMITATION | 中文路径解码、挂载与宽松摘要条件的QA执行错误；有效本地证据已纠正，错误记录保留 |
| EXT-403-01/R-03 | EXTERNAL_DEPENDENCY | 单个旧任务GET403；未证明影响当前新任务。用户已批准移出当前硬门禁，原未解决状态和账本保留 |
| EXT-BUDGET-01 | EXTERNAL_DEPENDENCY | 原公开合成8/8保留；新增6次已批准，实际5次。预算不再是本次未执行原因，不算独立代码阻断 |
| OPS-REBOOT-01/R-06 | OPERATIONAL_ACCEPTANCE | 容器恢复已通过；整机NOT_TESTED，用户已批准另列上线前项目 |
| QUALITY-01/R-04 | DEFERRED_ENHANCEMENT | 高误差/阅读顺序改善为模型质量优化；已分级和提示复核，不因此单独否决。若发现静默丢失并自动发布则新建真实阻断，不套用此延期 |
| SCA-003/全局待审清单 | DEFERRED_ENHANCEMENT | finding级v_review_queue不覆盖全部requires_review，限制保留；当前上传任务页不依赖该视图。若另正式要求完整历史待审队列，则重新审查，不能无条件认定已交付 |
| SCA-004/外部来源/GAP-008部分 | DEFERRED_ENHANCEMENT | 未授权外部SOURCE_PG_DSN及Excel/普通表格自动入库不扩展当前范围 |
| GAP-006/自部署GPU Standard | DEFERRED_ENHANCEMENT | 不能用官网API成功宣称自部署生产GPU验收；不纳入本轮后端候选放行声明 |
| GAP-001/002/003/004/005既有MVP部分 | EVIDENCE_GAP | 旧缺失已由当前客户端、任务API、持久化与审核桥证据覆盖；真实auto未闭环只追踪EV-AUTO-01，不重复要求研发 |
| FUTURE-01 | DEFERRED_ENHANCEMENT | SQLite→MySQL/PG队列、多Worker、复杂大图自动缩放、前端七页、历史QA域/Worktree清理、大规模效果优化不纳入当前门禁 |

R-01质量标准和R-02扩展真值为已完成前置条件，不是剩余问题；不得再要求用户补交已交付真值。

## 5. 四项镜像ERROR的正式适用性裁决

依据 `tests/test_local_workbench_config.py` 的 ROOT路径及 `deploy/local/Dockerfile`：镜像只将entrypoint复制到 `/opt/workbench/entrypoint.py`，该路径和内容已经过身份核验和实际Compose启动；部署准备脚本与根compose不属于容器执行时必需文件。

| 测试方法（LocalWorkbenchConfigTests） | 原执行意图/适用环境 | 复用证据 |
| --- | --- | --- |
| test_database_rebinding_preserves_credentials_and_drops_old_authorization | 宿主prepare.py生成配置、entrypoint源码单测 | c915宿主全量PASS |
| test_docker_entrypoint_clears_inherited_test_connections | 宿主定位entrypoint源码的单测；镜像实际入口路径不同 | c915宿主PASS；候选实际entrypoint运行另有HTTP证据 |
| test_normal_compose_does_not_inject_test_dsn | 宿主根compose配置检查 | c915宿主PASS |
| test_remote_database_and_untrusted_runtime_fields_are_rejected | 宿主prepare/entrypoint配置约束单测 | c915宿主PASS |

四项适用性均 **NOT_APPLICABLE_TO_RUNTIME_IMAGE**，原 `177=172 PASS+4 ERROR+1 SKIP` 保留，绝不重写为176 PASS。未向镜像补拷这些脚本，未修改测试。原日志 `local/v021-c915-final/candidate-tests-49ea0156/`；宿主逐项PASS `local/v021-security-retest/full-valid-fixtures/suite-result.json`。

## 6. 最小auto补证方案（已批准并执行，保留方案）

已读取原公开合成账本：8次实际HTTP，其中POST2、PUT2、GET4，响应均200；短图任务后续结果因预算耗尽未取得。原账本、远端关联和全部检查点保留，未决任务禁止重新POST。

计划仅一个场景 `SYN-AUTO-FINAL-01`：公开合成白底短图文字“QA021”，1400×180。样本SHA256 `4722ea9314889ce3e0607b1818e326f0531ee92e75e9ec38d7b42c8aa849370e`。样本已在QA忽略目录准备，未外传。此前短图与未决任务可能同SHA，为避免重复不确定任务，本次选择不同内容的新公开合成样本，而非修改或重提交旧任务。

请求的新增预算：**最多6次真实HTTP，仅一个新提交，POST≤1、PUT≤1、GET≤4，自动重试0**；只授权此SHA、当前c915镜像和短时FILE_SHA授权。原8次继续保留，新旧合计上限14次，不修改产品阈值、不重置任何旧计数。若6次不足完成，保留新远端ID和准确计数后停止，不自动续额或另开批次。

具体执行：先本机只读校验镜像/模型文件/UTF-8挂载与日志路径；在同一有效auto任务内要求真实本地模型推理成功、非空本地候选、现有质量逻辑触发回退，再使用新授权调用官方API；记录双方候选、来源/原件摘要、复核、任务状态及同幂等键零新增请求。任一前提失败先定位，未成功本地推理不得发送云请求；不得用Mock或选中引擎字段代替真实推理成功。

方案提交时尚无新增预算，因此当时未调用；用户随后明确批准上述6次，已执行5次，原始官方内容为空，结果见有限补证报告。若用户选择禁用并排除真实auto，则仍属于需明确批准且需验证配置的范围缩减，QA不会自行处理。

## 7. 403与整机恢复的范围决定

旧任务403：保留 `local/v021-release-final/old-task-recovery/` 中原收据/任务关联和403。上次仅GET1、POST0、PUT0，父计数6→7、总账12→13，每文件余1。任务授权执行清单只续有效期，未改任务/源摘要；403根因仍未证实，不猜测token失效。新公开任务实际官方200说明并非所有新任务都不可用，但不证明旧任务能恢复。

用户已明确确认：该具体历史任务列外部未解决事项，不要求v0.2.1保证恢复，移出当前硬门禁；不改变403事实，不无意义轮询。

整机恢复：当前实际已支持并验证容器级恢复，尚未验证Windows重启/Docker Desktop自启动。用户已明确批准整机恢复放到上线前独立运维清单，不属于本次后端候选本地集成PASS承诺；NOT_TESTED不改成PASS。

## 8. 放行条件及停止规则

已批准：用户当前后端MVP范围、质量分级、S00019拒绝、安全/授权不降低、环境错误不冒充代码Bug、复用有效证据、未来增强不自动加门禁。

随后已获用户明确批准：新增6次合成API预算、旧具体任务移出版本硬门禁、整机恢复改为上线前运维项。尚未批准：任何超过本批6次的调用，或禁用并排除当前真实auto交付能力；不视沉默为同意。

整体PASS必要条件：身份保持一致、无未关闭真实关键缺陷、EV-AUTO-01取得上述完整证据（或用户明确批准缩减并验证该功能禁用）、历史任务/整机承诺得到明确处置、报告如实保留全部未测/失败和不适用项。不承诺生产部署、全前端、GPU自部署或全自动知识库发布。

当前真正阻塞技术声明的是EV-AUTO-01：本轮已执行且本地成功，但云端原始内容为空，未取得有效双候选。旧任务/整机承诺已按用户批准处置，不再列为当前硬门禁。没有待Fix修改的已确认缺陷。本批停止，不再增加无关测试、不复跑全量、不清理数据、不Push或切换服务。
