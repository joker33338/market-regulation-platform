# v0.2.1 安全与 Schema 修复独立复测

> 后续候选入口、真实OCR及余下Schema对抗验证见 [c915候选收尾报告](candidate-c915-qa-report.md)。整体仍BLOCKED，但本文当时列出的候选缺失与四项Schema证据缺口已补齐，不继续当成待Fix开发项。

日期：2026-11-11。**QRC-001 PASS，当前整体版本仍 BLOCKED。** 沿用用户确认的质量分级及人工复核机制，不恢复旧的质量一票否决标准。

## 身份及绑定

- 正式交接：Fix `6aedddf057a68c0a7e08abb78add97c407292f07`。
- 唯一受测业务源码：`c91547d393ca6b049e216c0051e25271d06d7359`。该源码至交接HEAD仅两份文档变化，未再次修改业务源码。
- QA 分支 `codex/qa-v0.2.1`；运行起点 `28aece1ececdd02768cb327951b55e7be631e8fb`；本轮夹具和辅助入口提交 `40014200e15e6abb1b811a99eb66b8fa55b009ed`。报告提交使用包含本报告的Git提交识别，不伪造自引用SHA。
- 精确快照202个Git blob均核验。宿主实际业务模块从独立Fix工作区导入，路径记录于忽略目录suite-result.json；测试来自QA与经同名严格核对的Fix测试。运行期间Fix HEAD未变且工作区干净。
- PostgreSQL运行使用既有候选镜像的Python依赖，但**只作为执行环境**，通过只读快照导入 `/source/qa_core/...`。未将旧镜像 `/app` 代码当本轮修复代码，也未构建、替换活动服务。

## 真实执行结果

| 项目 | 结果 | 说明 |
| --- | --- | --- |
| 全量方法 | 292：285 PASS、7 SKIP | 无FAIL/ERROR。原QRC四个子场景均通过，拒绝超限且sink/cloud零调用，原件及历史缓存字节不变 |
| 合法缓存恢复及损坏缓存边界 | PASS | 新增缓存恢复测试与既有幂等测试通过；未删除断言 |
| 真实PG独立六项 | 6 PASS | 包含解析写入、冲突/回滚、重复批次、生命周期构建/发布/检索/回滚；仅合成记录及独立测试Schema，不修改真实ACTIVE |
| 真实库只读预览 | PASS | requires_review=true、rag_index_written=false，正文roundtrip一致 |
| 真实Schema补充探针 | 6项检查PASS | public只读身份、空测试域不回退、全新自有域初始化、路径改变后的下条业务语句拒绝、部分域初始化拒绝、拒绝后未补建其他表 |
| SCA-002 | 自动化PASS | 普通启动拒绝/清理测试DSN的既有与新增测试通过；不等于新镜像启动已验证 |
| 当前源码真实OCR/云/候选HTTP | NOT_TESTED | 前轮有bf66真实证据，本轮未重复模型推理、外传、启动或镜像构建，不将旧SHA证据冒充本轮执行 |

统计不叠加：六项PG补跑对应全量中六个SKIP，所以方法级合并为291 PASS、1 SKIP；Schema六项是额外探针，不加进292个方法。最后一个SKIP为Windows symlink环境限制，保留此前Linux覆盖记录但不改写本次SKIP。

首次全量有一个旧测试失败：`test_database_retry_reuses_exact_result_and_skips_successful_sibling` 使用不可解析的伪PDF，新增安全校验正确拒绝。只将两份输入换成合法合成PDF，全部原断言逐字符保留，独立执行器严格约束允许的夹具替换后重跑全量通过。不是新确认业务缺陷，不降低测试标准。另将PG夹具显式传入同一随机 `kb_schema`，未改生命周期断言。

首次宿主PG连接因容器地址变化超时，未写入。核对实际数据库容器网络身份后，从同网络临时QA容器执行；首次六项通过，但CLI预览因输出目录不在允许范围而终止，保留日志与数据。改为允许的 `/state`、新证据目录重跑六项与完整审计，全部通过；两次测试数据及Schema均保留，没有清理。前后摘要比较证明两次PG运行均未改变已有public记录/真实ACTIVE，原document_review记录全部保留。没有重新安装vector或修改业务Schema。

## 关闭与剩余项

- **QRC-001 PASS/关闭**：四子场景已在新源码独立验证；正常最终缓存复用、旧候选安全校验及幂等回归继续通过。
- **SCA-001 部分验收通过**：真实正常域与上述拒绝边界已通过；非当前角色拥有域、临时同名关系、跨域FK/OID、vector类型遮蔽等当前主要为Mock覆盖，尚无本轮真实PG完整证据。不能宣称全部隔离对抗场景已验收。
- **SCA-002 自动化通过，部署集成待测**：新候选尚未包含修复，需Fix交付与c91547d绑定的镜像身份及安全启动材料，QA独立验证实际入口/权限/持久化。不得自动切换旧活动实例。
- **SCA-003 待确认需求**：上传任务页提示与审核桥有已有证据；不能据此声称全局历史待审清单已实现。是否新增全局队列另行确认，不擅自将未计划功能当Bug。
- **SCA-004 NOT_VERIFIED**：未连接外部来源库，不猜测来源Schema契约，不要求为通过本轮擅自扩展功能。
- 旧任务GET403仍BLOCKED；未重试、清空预算或重传原文。Windows整机重启仍待用户安排，不能以容器restart代替。

现无本轮新复现P0/P1，未据此直接签发整体PASS。前轮识别质量测量值保持不变，复核机制通过不等于识别准确。本轮没有新增质量预测，不把历史预测重标为本轮MEASURED。

## 证据与复现

原始证据只存QA忽略目录 `local/v021-security-retest/`：

- `source-exact/snapshot-identity.json`：冻结源码202文件身份。
- `full/suite-result.json`、`full.log`：首次未调整伪PDF夹具的原始失败，保留。
- `full-valid-fixtures/suite-result.json`、同名`.log`：最终292方法，业务实际导入路径与每项结果。
- `pg-six/run.log`：宿主连接超时；`pg-six-docker/`：六项通过但预览路径错误；`pg-six-final/`：六项、只读预览及数据库前后快照完整审计。
- `schema_probe.py`、`schema-probe.log`、`schema-probe-result.json`：真实Schema六项探针，两个新增测试Schema保留。

复现入口仍为 `tests/run_v021_final_acceptance.py`，绑定交接完整SHA，使用三份受严格文本约束的合成图片/PDF夹具；PG入口 `tests/run_offline_business_postgres.py --source-sha c91547d393ca6b049e216c0051e25271d06d7359 --run-user-authorized-business-tests`，需原已批准的私有scope与连接配置，不将密钥或实际路径写入报告。

未修改Fix业务源码、原始测试集、标准答案、模型或生产服务；未Push、未Merge、未部署。下一步为补齐新候选及剩余必要集成证据，不能要求Fix重复开发已经通过的缓存修复或既有数据库生命周期。
