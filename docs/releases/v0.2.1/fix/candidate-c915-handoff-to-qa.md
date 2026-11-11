# c915 最终候选镜像与剩余集成交接

日期：2026-11-11。Fix 工程交付：**READY_FOR_QA**；整体版本仍 **BLOCKED**，由独立 QA 裁决。此次无业务源码修改，没有重复开发已关闭缺陷，没有修改 QA 报告或门禁。

## 最新 QA 与冻结身份

| 项目 | 身份／结论 |
| --- | --- |
| Fix 分支／本轮开始 HEAD | codex/fix-v0.2.1 / `6aedddf057a68c0a7e08abb78add97c407292f07` |
| 唯一业务源码 | `c91547d393ca6b049e216c0051e25271d06d7359` |
| 最新 QA 报告提交 | `59574c0f16dd960fe034f9f4d0aca8f75fb116a4` |
| QA 测试／夹具提交 | `40014200e15e6abb1b811a99eb66b8fa55b009ed` |
| 最新 QA 报告 | QA 分支 docs/qa/v0.2.1/schema-and-security-qa-report.md |
| 当前技术结果 | QRC-001 PASS/关闭；没有新确认 P0/P1；292 方法中 285 PASS、7 SKIP，合并同 ID 的六项 PG 补测后 291 PASS、1 Windows symlink SKIP |

Schema 六项真实探针是额外证据，不累加进 292。既有正常生命周期、真实 PG 六项和只读预览结果沿用，不机械再跑；Mock 未覆盖的真实对抗边界仍未签发完整 PASS。本轮不改质量分级，也不把审核／复核机制通过写成 OCR 准确率全部合格。

## 新候选（已完成）

| 项目 | 实读值 |
| --- | --- |
| 镜像标签 | `market-regulation-workbench:candidate-v021-c91547d393ca` |
| Docker image inspect ID | `sha256:92bc163c15210ec0ea9f0373db4d020f0be792dea2e2be4dc3f089727d202c0e` |
| OCI revision | `c91547d393ca6b049e216c0051e25271d06d7359` |
| 基础镜像 | market-regulation-app:local |
| 基础镜像 ID | `sha256:b4010953b65e06c2d1000fdcd129f6fcceeed9b9a5d48a12266d3365a610a2b1` |
| Python | 3.12.16 |
| FastAPI / uvicorn | 0.162.0 / 0.54.0；宿主旧 API 环境仍为 0.115.12 / 0.34.2 |
| PyMuPDF / httpx | 1.26.7 / 0.28.1 |
| PaddlePaddle / PaddleOCR / PaddleX | 3.2.2 / 3.3.2 / 3.3.10 |
| sentence-transformers / torch / transformers | 4.1.0 / 2.7.1+cpu / 4.57.6 |
| psycopg2-binary / numpy / pillow | 2.9.13 / 2.5.4 / 13.0.0 |

使用现有 deploy/local/Dockerfile、--pull=false 和固定 SOURCE_COMMIT 构建，没有安装／升级依赖或下载模型。构建时 HEAD 与 c915 仅两份文档差异；复制进镜像的核心文件无差异。

Fix 在 network=none、只读根文件系统、cap-drop ALL、no-new-privileges 的一次性容器中读取文件与包元数据：57 个核心 Python、HTML、SQL、脚本及 entrypoint 的换行规范化 SHA256 全部一致，额外核心文件 0；模型仅只读检查目录存在。没有挂载任务状态或私密配置，没有启动服务、模型或数据库调用。**构建及身份检查不等于新镜像集成 PASS。**

私有证据位于 Fix 忽略目录 `local/candidate-c915/`：build.log、image-inventory.json、inspection.log、inspect_candidate.py。所有历史证据和镜像保留，没有覆盖前轮归因或测试日志。

## 当前服务与隔离启动材料

现有 market-regulation 项目的 app、PostgreSQL、MySQL、Redis 均运行且健康。活动 app 仍为 local-4ecd995cb4be8ee4、revision `350f5ad3d8d0859e6dbbb2a879367e901913b556`；本轮未切换。state、logs、数据库卷保留；模型与私密配置仍只读，runtime.json 和 deployment.json 摘要与前轮盘点相同。

QA 实际入口验收应复用 **compose.local.yaml + 独立项目名 + 全新 QA state + 新候选镜像**，不能让第二个 worker 访问活动 state；不运行会改写部署选择的 scripts/local-workbench.ps1 -Action start。

前置条件（由 QA 准备，Fix 本轮未启动）：

1. 在 QA 忽略目录创建新的 QaRoot，包含 runtime.json、空 state 和 state/logs；runtime 只含 entrypoint 允许的三个键，使用既有批准的合成测试连接和访问码，绝不提交凭据。
2. QaRoot 必须与活动 local/docker-workbench 不同。不得复制活动任务 SQLite 来启动，否则可能恢复旧队列；不要把真实资料带进合成验证。
3. QaModels 使用已有完整模型目录，只读挂载。复用已核数据库网络，不重建 db、mysql 或 redis。
4. 确认本机 8182 空闲，测试端口只绑定 127.0.0.1。代码、entrypoint 必须从候选镜像导入，不挂载 `/app/qa_core` 或旧 `/source` 替代业务代码。

```powershell
# 在已有 QA 工作区执行，QaRoot/QaModels 均为已核验的本机位置。
$env:LOCAL_WORKBENCH_ROOT = $QaRoot
$env:LOCAL_MODELS_ROOT = $QaModels
$env:LOCAL_APP_IMAGE = 'market-regulation-workbench:candidate-v021-c91547d393ca'
$env:LOCAL_APP_PORT = '8182'
$env:LOCAL_DATABASE_NETWORK = 'market-regulation_default'
docker compose --project-name market-regulation-qa-c915 -f compose.local.yaml config --quiet
docker compose --project-name market-regulation-qa-c915 -f compose.local.yaml up -d --no-build --pull never --wait
# 保存实际容器 image ID、revision 和实际导入文件路径，切勿输出完整 Env/DSN。
docker compose --project-name market-regulation-qa-c915 -f compose.local.yaml ps
# 验收后只停止这个项目的 app；保留证据和状态，不使用 down -v/prune。
docker compose --project-name market-regulation-qa-c915 -f compose.local.yaml stop app
```

这套入口验证生产默认行为：云开关关闭，TEST DSN 清除，访问码鉴权生效。真实 auto 的获准外传场景应在单独批准测试 harness 中设置授权／预算，不为此开启活动工作台外传或放宽生产 entrypoint。普通桥接数据库网络也不能当作云出口隔离已验证的证据。

## QA 下一批必要检查

| 批次 | 当前事实 | 下一步验收及边界 |
| --- | --- | --- |
| A 新候选实际入口 | 已构建身份正确，未进行 HTTP 启动 | 新镜像真实入口、401、跨用户隔离、合成上传→解析→原批准 document_review 记录、重复请求幂等、容器 restart 后任务/结果/权限/预算保持；保护已有记录和 public ACTIVE |
| B 安全 helper 的真实本地／auto 集成 | c915 的单元及 PG 已通过；真实 OCR/auto 是旧 bf66 证据 | 复用既有公开合成样本，确认当前镜像内的真实本地优先、正常 OCR、超限拒绝、敏感阻断、低质量后受控官方回退和两候选保留；不要重复全量模型性能测试或上传真语料 |
| C SCA-001 余下真实对抗场景 | 六项真实正常／拒绝探针已通过 | 在批准的独立测试域／环境补非当前角色拥有域、临时同名关系遮蔽、跨域关系/FK、vector 类型遮蔽。只使用合成结构，不能改 public 表或已有角色权限；若现有批准环境无法安全表达某项，记录边界，另行决定环境，不在业务库制造破坏 |
| D QRC-001 与缓存幂等 | 已独立 PASS | 不重新开发；新镜像可运行同一小范围回归证明打包无遗漏，不再要求全部 292 方法从头重跑 |
| E 旧任务恢复 | 一次官方 API GET 返回 http_403，来源／账户或服务端状态原因未证明 | 先核对原收据、任务与账号关联及已保存错误；无需用户重复逐次批准 API。不得清账、换 ID 重提或把新合成成功当作旧任务恢复成功 |
| F Windows 整机恢复 | NOT_TESTED | 由用户安排窗口，再用正式清单取重启前后证据；不以本机容器 uptime 或 restart 推断整机验证通过 |

Schema 追加检查只属于 QA 的独立验证，不要求 Fix 再改已经通过的代码或复制 QA 数据到 public。对既有脚本中 sys.path.insert('/source') 等历史绑定，QA 必须检查实际导入：本次镜像验收不能靠挂新源码快照修正旧镜像；只挂单个 QA harness／tests，业务导入需确认来自候选 `/app/qa_core`。

## 旧 403 与仍需明确处置的事项

只读核对 QA 的旧任务恢复 summary：原远端 ID 被复用，GET=1、POST=0、上传=0；父任务调用从 6→7，总 canonical 账本 12→13，错误码 http_403。每文件原预算为 8，S00010 只余 1 次请求；如果先 GET 又下载，已不能简单假定仍有两次额度。

Fix 本轮没有再请求 API、修改清单、重置账本或执行恢复。现有材料不能证明 403 是客户端代码错误，也不能证明是 Token 全局失效。先用保存的收据及账户资料核对，再由 QA 记录：可恢复、服务端不可恢复或证据不足；若今后需调整该任务预算，单独记录决定并保留原计数，不能偷偷续试。用户此前的 API 许可继续有效，不需要重复询问是否允许每次调用；这不代表可以删除预算审计。

SCA-003 的全局审核队列仍待需求确认，SCA-004 外部源契约仍未验证，本轮不扩展。Windows 恢复清单沿用 [收尾交接第 10 节](release-closure-fix-handoff.md)，但实际镜像身份必须更新为本文件的候选；如果验证的是旧活动实例，只能记录旧实例结果，不宣称新候选整机 PASS。

## 工程交付结果

本轮新增的是 c915 独立候选及本交接文档；业务源码、QA 报告、门禁、真实数据库和运行实例均未改变。没有新增测试通过数，只有镜像构建／57 文件身份及依赖读取证据。不 Push、Merge、生产部署、删镜像／卷或自动重启 Windows。

本文件单独本地提交，其完整 SHA 由 Git 和会话提供。交接载体是此 Git 文档，没有声称已经自动唤醒其他会话。独立 QA 接收新镜像后裁决剩余集成，整体仍为 BLOCKED；Fix 的工程准备为 READY_FOR_QA。
