# c915 候选镜像收尾独立验收

日期：2026-11-11。**整体结论 BLOCKED，无新确认P0/P1。** 已补齐候选入口、真实Schema对抗检查及真实本地OCR；当前源码的完整真实双引擎回退验证仍未完成，旧任务403和Windows整机恢复也未闭环。

## 版本身份

- Fix正式交接HEAD：`4fea3064de4c699ab9de65c79f23a07b8c9e4a22`，受测业务源码仍为 `c91547d393ca6b049e216c0051e25271d06d7359`；新增提交只有交接文档。
- QA分支 `codex/qa-v0.2.1`，本轮开始SHA `59574c0f16dd960fe034f9f4d0aca8f75fb116a4`。本报告提交由Git记录。
- 候选 `market-regulation-workbench:candidate-v021-c91547d393ca`，实际ID `sha256:92bc163c15210ec0ea9f0373db4d020f0be792dea2e2be4dc3f089727d202c0e`；OCI revision与受测业务源码一致。独立核对57个核心文件全部一致，无多余/不同文件。
- 本轮镜像业务模块实际导入 `/app/qa_core/...`，未挂载 `/source` 或替代业务代码。仅挂载QA测试/执行脚本、全新QA状态、只读模型和私有配置。实际依赖FastAPI 0.162.0、uvicorn 0.54.0、PaddlePaddle 3.2.2/PaddleOCR 3.3.2/PaddleX 3.3.10。

## 本轮执行与结论

| 项目 | 实际结果 | 边界 |
| --- | --- | --- |
| 镜像小范围回归 | 177方法：172 PASS、4 ERROR、1 SKIP | 四项ERROR均为宿主部署文件测试依赖镜像不包含的 `/app/deploy/local/prepare.py`、entrypoint源码路径或compose.yaml；不是业务代码运行失败，也不改写为PASS。一项Windows启动测试在Linux跳过。相同宿主测试在上轮292全量已通过 |
| QRC-001及缓存回归 | PASS | 候选中原四子场景及新增恢复测试通过，证明修复已打包 |
| 正式Compose隔离启动 | PASS | 独立项目、全新state、loopback独立端口，实际候选生产entrypoint，不接入活动任务SQLite |
| 真实HTTP/PG | PASS | 401、跨用户404、原生合成上传解析、同请求幂等、单条document_review记录；S00019本机安全拒绝、无入库且摘要不变 |
| 候选重启恢复 | PASS | task/result与请求幂等恢复，数据库仍仅一条记录；保留QA状态，不删除容器或卷 |
| 既有数据保护 | PASS | public各表与真实ACTIVE摘要不变；document_review已有记录全部保留，本次仅新增一份合成解析记录 |
| Schema真实对抗 | 四项PASS | 临时同名关系遮蔽、vector类型遮蔽、跨Schema FK、非当前角色拥有域均拒绝。全部仅使用新mvp_test随机域/会话临时关系，未改public表、既有角色权限；持久测试域保留 |
| 真实本地模型 | PASS | 修正挂载路径后，network=none下真实Paddle检测/识别模型加载，普通合成图completed、selected_engine=paddle_ocr、非空正文；原生PDF无OCR；低质短图保留本地候选并提示复核；重复请求无新处理/云请求 |
| 当前源码真实云回退 | 部分执行/BLOCKED | 一份公开合成图实际官方回退完成并保留两候选；但当时本地模型未成功加载，不能算完整有效双引擎验证。后续短图回退因全局8次预算耗尽而失败，计数未重置 |
| 旧任务403 / Windows整机 | BLOCKED / NOT_TESTED | 本轮未再次请求旧远端任务、未重启电脑；不把容器restart当整机通过 |

不重复执行或累加已通过的292项及PG六项；本轮177方法与既有方法有重叠。Schema四项是额外探针，不加成方法数量。QRC-001保持关闭；没有为取得通过而修改功能断言或标准答案。

## 失败执行及证据纠正

首轮云测试的QA执行脚本错误解码Docker返回的中文挂载路径，导致模型目录指向错误位置；本地predict入口被调用但模型校验失败。该轮共实际发送8次官方HTTP：普通图回退5次、短图回退3次；全局预算到达后拒绝继续。只有公开合成样本外传，旧真实批次账本未使用。此为QA执行环境问题，不据此认定新业务代码缺陷。

随后断网本地重测修正路径，增加可写worker日志及正确HOME。第一次本地脚本把“选中了paddle_ocr”错误作为成功条件，即使task failed也输出PASS。该自动摘要**无效，不作为通过证据**。最终改为同时要求task completed、正确引擎和零云请求，在新证据目录实际重跑，确认真实模型成功加载后才记录本地PASS。保留全部失败与错误摘要，不覆盖历史结果。

没有为了补齐云结果清空上述8次预算或更换请求键偷偷续试。当前仍缺“真实成功本地推理后，低质触发获准官方回退并保留有效两候选”的完整当前镜像证据；需要单独记录后续验证批次及总量决定，不能将现有不完整结果写PASS。

## 证据与后续

原始证据均位于QA忽略目录 `local/v021-c915-final/`：

- `candidate-tests-49ea0156/result.json`、`execution.log`、`image-identity.json`：177方法及镜像身份。
- `candidate-http-2b6bfb37/`：正式Compose入口、真实HTTP/PG及前后记录摘要；该项目app已停止，活动旧应用未切换。
- `schema-adversarial-result.json`、同名 `.log`、`schema_adversarial.py`：四项真实拒绝证据与新测试域标识。
- `real-auto/`、`real-auto-driver-retry.log`：首轮预算8次及不完整云链路，禁止重置重放。
- `real-local/`：错误挂载和无效PASS摘要，仅作诊断。
- `real-local-correct/`、`real-local-correct-driver.log`、`model-logs/`：最终断网真实本地模型证据。

受测源码的292全量、PG六项与前六项Schema探针沿用 [上轮独立报告](schema-and-security-qa-report.md)。识别质量数值沿用bf66标注评估，不外推为本轮新增测量；继续采用用户确认的安全门禁、质量分级与人工复核，不追求所有困难样本达到旧98%/95%硬指标。

剩余：受控补齐当前候选的有效双引擎完整证据、明确处置旧任务403、由用户安排Windows整机恢复窗口。当前无证据要求Fix再次改写已通过的缓存或Schema防护。未Push、未Merge、未部署活动实例、未修改原始资料或真值。
