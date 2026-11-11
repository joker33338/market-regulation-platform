# v0.2.1 最终有限范围验收裁决

**当前是否具备放行条件：YES。最终结论：PASS。**

签发日期：2026-11-11。PASS范围为已确认的后端MVP及c915候选镜像的本地集成验收；不表示生产部署、活动旧实例切换、Windows整机自动恢复或独立前端全部联调通过。没有自动部署或进入下一版本开发。

## 身份与验收边界

- 唯一业务源码：`c91547d393ca6b049e216c0051e25271d06d7359`。
- 最新Fix正式交接HEAD：`3129479ef763f2d35758a68f514b7053aacdaec4`；与业务源码之间仅QA交接/审计文档变动，工作区干净。
- 候选：`market-regulation-workbench:candidate-v021-c91547d393ca`，实际镜像ID `sha256:92bc163c15210ec0ea9f0373db4d020f0be792dea2e2be4dc3f089727d202c0e`，OCI revision与源码相同。当前复读身份通过，既有57核心文件核验仍适用。
- QA分支 `codex/qa-v0.2.1`，本轮核验起点 `c3c9bbd23995603d5508ee4b0cadc658fd3851d8`；本报告与新增只读核验器的实际提交由Git记录，最终回复给出完整SHA。
- 交付范围依照 [正式边界文件](final-acceptance-scope.md)：现有文档解析、双引擎安全路由、任务/结果持久化、复核提示与审核桥、法规切分/父子关联/BGE、版本化构建/检索/授权发布/回滚、隔离及容器级恢复。预览或保存解析结果不等于正式发布知识库。

本次不改产品代码、阈值、标准答案或已有功能断言；没有重跑全量或新增云请求。以前的FAIL、BLOCKED、空官方输出及错误执行均保留为各自版本/时点的真实历史。

## 唯一剩余证据缺口的关闭依据

Fix在 `auto-reset-fix-verification.md` 提交了新公开合成短文的实际执行记录。新8次窗口的用户许可依据为该正式交接及其approved-plan；QA只复核已有产物，未自行批准额外调用或重置任何窗口。

样本SHA256：`0fd15b84e03f5c23a220d4f8d4e980c2c843f59a92dab9047507d63853eca536`。不使用原始测试资料。

独立核验不只读取Fix的PASS摘要：

1. 将Fix实际执行副本与QA已提交的有限执行器逐字符比对。仅样本SHA、授权标记、总量6→8、GET4→6、轮询上限、HOME准备和执行开关改变；原11项检查及真实本地成功前禁止HTTP的约束全部保留，没有Mock替代或阈值修改。
2. 重算9份关键证据SHA256；源样本、最终normalized摘要及原13次账本均匹配。两份旧账本仍为8次和5次，未删除或覆盖提交占位。
3. 核对真实检测/识别模型加载日志及本地原始候选。页面success、正文非空8字符；默认质量判断仅因short_page回退，没有engine_failed。
4. 核对实际5次HTTP（POST1、PUT1、GET3），均200；新窗口5/8，余3次停止，公开合成序列累计18次。没有重提旧未决任务。
5. 在当前候选镜像内，以network=none、证据只读挂载运行QA新增核验器，实际业务导入 `/app/qa_core`。用产品 `unpack` 检验原ZIP，再以 `normalize_artifacts` 重新标准化；原始content_list非空，重建正文与保存的远端候选逐字一致，最终正文也与远端一致。
6. 本地、远端候选均为非空8字符，源SHA、source_file_id和页码一致，双方候选保留，最终选用mineru_official、requires_review=true、无失败原因。父/子SQLite以只读方式核对均completed、各仅一份任务；执行器原记录证明相同幂等键无新增推理/HTTP，未重新写入这些检查点。

**EV-AUTO-01：PASS，关闭。** 本地成功→自然质量判断→获准真实云回退→有效双候选保留的证据链已成立。本次是QA独立原始证据审查及断网产物重建，不冒充QA再次执行了一次真实云任务。

独立核验器调试的两个离线错误（可选failure_reason字段按缺省None处理、官方解包配置需合法api_url）已按源码契约纠正，原错误日志保留。它们不涉及产品改动、真实请求重放或降低11项业务检查。

## 核心证据复用与最终登记

| 项目 | 裁决 | 证据范围 |
| --- | --- | --- |
| 源码与镜像身份 | PASS | 当前镜像复读，原57文件一致性复用 |
| 核心自动化及PG | PASS | EVIDENCE_REUSED：c915的292方法，原285 PASS/7 SKIP；六个相同ID的真实PG补测通过后合并291 PASS/1环境SKIP，不叠加重复方法 |
| QRC-001及已有安全缺陷 | PASS | EVIDENCE_REUSED：原四安全子场景、缓存合法复用、资源/授权/预算/审核门禁；无未关闭确认P0/P1 |
| 数据库隔离及数据保护 | PASS | EVIDENCE_REUSED：PG六项、Schema六项及四对抗探针，既有数据/真实ACTIVE保护 |
| 镜像HTTP及任务恢复 | PASS | EVIDENCE_REUSED：隔离Compose、鉴权/跨用户、入库/幂等、容器restart及状态保留 |
| 当前真实PaddleOCR | PASS | EVIDENCE_REUSED：当前镜像真实断网模型成功，不将之前错误挂载结果算通过 |
| 真实auto有效双候选 | PASS | 本次独立证据核验及ZIP重建，关闭最后证据缺口；无新增HTTP |
| PP-Structure、法律切分、BGE、知识库基础生命周期 | PASS | 依正式边界逐项复用原SHA证据，相关实现未变化，不重新宣称本轮推理或发布真实ACTIVE |
| 业务识别质量 | 分级保留 | 困难样本仍有不合格项；复核成功不改成识别准确，不声称复杂文档100%识别 |
| 四项镜像ERROR | 环境不适用 | 原177=172 PASS/4 ERROR/1 SKIP原样保留；NOT_APPLICABLE_TO_RUNTIME_IMAGE，适用宿主的原PASS复用 |
| 旧具体任务403 | 未解决，非当前硬门禁 | 用户已批准移出；无重复轮询、重提或清账 |
| Windows整机恢复 | NOT_TESTED | 用户批准另列上线前运维；仅容器恢复已验收 |

旧R01、QFA及QRC缺陷保持各自已关闭登记；历史扩展真值已交付，不要求重复补充。S00019保持SAFE_REJECT，不因本次PASS开放缩放或绕过。无未关闭RELEASE_BLOCKER或当前必需EVIDENCE_GAP。

v_review_queue仍为finding级视图，不能代表全部历史待审documents；当前上传任务页不依赖该视图，全局审核队列未纳入当前交付承诺。外部来源迁移、多Worker、MySQL任务迁移、独立前端全联调、大规模效果优化继续是后续范围，不要求Fix为本次放行再开发。

## 证据、停止及交接

QA原始核验证据：忽略目录 `local/v021-final-evidence-audit/` 的 `independent-audit.json`、`independent-host-check.json` 和三次离线execution日志。新增可复核执行器：`tests/verify_v021_auto_handoff.py`。

Fix原始真实运行：其忽略目录 `local/auto-reset-20261111-01/`；正式交接 `docs/qa/v0.2.1/auto-reset-fix-verification.md` 位于Fix分支，QA不复制或修改Fix所有的报告。通过Fix提交 `3129479ef763f2d35758a68f514b7053aacdaec4` 可核验；私密token文件未读取、复制或提交。

早期证据见 [c915候选报告](candidate-c915-qa-report.md)、[安全与Schema报告](schema-and-security-qa-report.md)、[有限补证历史报告](finite-auto-final-report.md)。不重写旧报告的当时结论。

**当前不需要继续安排Fix修改代码。本轮QA收尾结束。** 未Push、Merge、切换活动应用、部署生产或启动下一版本；活动旧实例不是本次PASS镜像。上线前仍需按真实部署安排整机恢复等运维验收，不因此自动扩大本地集成承诺。
