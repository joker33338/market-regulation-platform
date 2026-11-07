# v0.1 独立回归报告：本地集成 PASS

日期：2026-11-07，Asia/Shanghai。本结论仅适用于下列精确提交及本地集成范围，不代表生产部署、真实云端识别质量或 GPU 验收通过。

## 版本与隔离

- 受测 Fix 交接提交：`d2a4c673c596945be14fa4d91a995fd8086e2b31`。
- 业务修复提交：`0cfb4f2f12d5fd87a57c0a2cacdc92a4cf54d2a4`；两提交间只有 Fix 报告变更。
- QA 测试提交：`4042a23c966c20f94eef17f3c3fc10d7d5f7702a`。
- 远程 fix/round1 只读核对仍为 `f7c4d75e1ff11e2d06d75f44336bf4b89f96aa57`，与本地不同。本次没有 Push。

分别检出修复提交和最终交接提交到 QA 的独立工作树；最终关卡证据绑定 d2a4c67，未使用旧提交的成功结果替代。原工作树、Fix 工作树和业务源码均未修改。现有解释器、API 依赖和 Docker 镜像只读复用，没有安装或升级依赖。

## 执行结果与计数方法

| 执行 | 用例数 | PASS | FAIL | SKIP |
| --- | ---: | ---: | ---: | ---: |
| Fix 正式脚本，精确修复提交 | 118 | 114 | 0 | 4 |
| 最终交接提交，Windows 全套及 QA 新测试 | 120 | 115 | 0 | 5 |
| 同一交接提交，独立 PostgreSQL 专项 | 5 | 5 | 0 | 0 |
| 按唯一用例 ID 合并后的关卡覆盖 | 120 | 120 | 0 | 0 |

最后一行是去重覆盖，不是把两次执行简单相加。数据库专项的五个 ID 与 Windows 阶段的五个 SKIP 完全一致；两个阶段的 source_commit、qa_test_commit 相同。只有已实际执行 PASS 的专项结果替代对应 SKIP，未覆盖的跳过不会被改写为通过。每个方法的结果均保存在忽略的执行 JSON 中。

正式脚本保留的四个跳过是历史占位及三个 PostgreSQL 条件测试。QA 没有删除旧用例：将自己的旧生产适配器占位改成真实 MinerUClient/MinerUService 的 Mock 生命周期、结果来源关联和请求幂等测试；该方法已实际 PASS。三个原数据库测试以及两个新增数据库用例均在专用实例实际 PASS，因此最终关卡没有遗留跳过或阻塞。

## 五个 Bug 的独立复测

| ID | 结果 | 验证范围 |
| --- | --- | --- |
| DOC-001 / R01-001 | PASS | 空文本与纯空白返回非成功；原有效文本、空白 PDF 行为未退化 |
| OCR-001 / R01-002 | PASS | 中文路径网格检测及相同像素正向对照 |
| DOC-002 / R01-003 | PASS | Docker COPY 资源预检；实际 Docker 构建仍未执行 |
| SEC-001 / R01-004 | PASS | Windows 大小写及路径变体不能覆盖原始 ZIP；保留文件与临时文件碰撞边界通过 |
| DOC-003 / R01-005 | PASS | 两种文件顺序、逐文件错误、partial 聚合、数据库重试复用原结果、中断恢复及已成功文件不重复处理 |

累计五个已确认 Bug 全部通过当前回归，修复率 100%；本次没有确认新的 P0/P1 问题。复现、根因及修复验收记录在 03-bug-list.md。

## PostgreSQL 真实执行

业务连接仅用于读取 document_review 五张表的列类型与主键，不读取正文、不写入业务库。使用本机已有 pgvector 镜像创建全新 QA 专用容器、独立内部网络和专用数据库，不映射主机端口、不连接现有 Compose 网络。

测试夹具按照已核对的列类型/主键建立 documents/pages/blocks/tables/cells；额外外键属于测试约束，不是对业务库的迁移。实际调用受测 PostgresResultSink、Database、检索与发布代码。覆盖：

1. 重复保存同一结果保持同一 parse_id、五级表各一条记录。
2. 相同身份但正文发生变化时返回 database_result_conflict，并保留原记录。
3. 页级失败、最深单元格失败使本次事务整体回滚，旧成功记录仍存在。
4. 原有 pgvector 入库、检索、向量复用、发布及版本回滚。
5. 本地任务/来源文件/远端文件 ID、正文、Markdown、表格和单元格映射。

容器内以只读挂载运行精确 Fix 源码；现有应用镜像只提供依赖，不能据此声称已构建新镜像。测试后专用 PostgreSQL 容器已停止，数据库数据及资源清单保留；没有删除业务数据或启动默认 Compose。

## 其他核心验证

FastAPI 六项测试实际执行；认证、跨用户任务隔离、上传/结果、输入校验及幂等通过。参考和生产类 Mock、官方 API 独立适配、超时/断传/恢复、标准化、来源关联、法律人工复核闸门、SQLite RAG 和本地解析回归通过。模拟结果不会自动进入正式知识库。

本轮未向官方 API 传送任何文档，没有上传真实语料，没有下载模型。此前真实离线 OCR 两个样例及 BGE 1024 维输出是历史证据；本轮没有重新统计全库识别质量。真实官网/自建 Standard、GPU、浏览器视觉、生产性能、实际 Docker 构建和业务库迁移兼容性均未作为 PASS 范围。

## 复现与证据

使用既有解释器和 API 依赖，设置可写 TEMP/TMP。合成阶段清空真实连接与云端凭据；数据库专项由助手创建专用连接。

```text
./scripts/run_fix_regressions.ps1 -Python <configured-python> -ApiPackages <existing-api-packages>
python -B tests/run_round01_validation.py --source <isolated-checkout> --include-source-tests --result-json <ignored-windows-result>
python -B tests/round01_isolated_postgres.py --source <isolated-checkout> --output <qa-local-output>
```

忽略证据位于 local/round01 下的 Windows 执行结果、独立库执行结果、资源清单和去重覆盖 JSON。凭据、容器实际名称、机器路径和原始日志不提交。version-gate.json 记录两个阶段的摘要哈希及精确源码/测试 SHA；报告提交 SHA 在提交后通过 Git 输出，避免自引用。

## 结论与下一阶段

v0.1 本地集成 PASS，可按用户规定生成 v0.2.0 双引擎开发交接。该放行不允许自动部署、上传语料、修改正式数据库或跳过法律复核。下一版应复用既有本地路由、OCR/Structure、质量发现、OfficialMinerUClient、生命周期、结果存储和法律入库链路；仅补充质量驱动的策略与授权回退。

现有 Orchestrator 仍是准备层。QA 将发布可校验的 Git READY 数据并执行只读检查，不宣称已自动唤醒另一会话。


## QA增量独立执行：v0.2.0候选（2026-11-07）

正式结论：**BLOCKED**。受测源码 `8badb995592771ff099cf52570621ba29ad37533`；QA测试基线 `d3c538643b4114c9e99acee002d1db77cd7ccbc1`；正式Fix交接传输 `c7e56026b4669b4a8a0075369b873c393ed50efe`。

已独立核验真实提交、source是transport祖先、结构化Fix→QA ready身份、交接两份报告Git blob SHA256。transport只增加报告，因此不要求报告SHA与受测source相同；正式交接阻塞已解决。后续不重复执行同源码已有有效证据的测试。

### 当前证据与A–J

| 范围 | 当前完整源码结果 |
| --- | --- |
| A原生、B本地OCR、C复杂布局、D质量回退、E法律原文复核 | 独立QA业务适配器用例PASS |
| F超时/限流/预算、G默认/敏感未授权拒绝、H双端来源追踪 | 独立QA用例及新增边界PASS |
| I真实PostgreSQL重复/失败不覆盖 | 用户指定测试库实际执行PASS |
| J复核前不入库/复核后可检索 | 原标准规定的演示向量既有pipeline兼容用例PASS |
| 初始Mock与最新边界 | 100/100 PASS，0 FAIL、0 SKIP |
| 未覆盖旧功能回归增量 | 46方法中42初次PASS、4初次SKIP；随后仅补测Windows专项1项、专用库2项，均PASS |
| 当前源码149方法去重覆盖 | 148 PASS、0 FAIL、1必需方法BLOCKED |
| 辅助真实HTTP | 1/1 PASS，实际Uvicorn本地TCP页面、认证拒绝、合成上传 |

指定market_regulation是用户明确批准的测试库。本轮在其现有结构执行3项合成PG测试，另在既有QA专用库补齐2项独立映射/回滚，均未DDL或删除，成功记录保留；专用库恢复停止。只读快照、断网Mock、现有镜像、无依赖安装。source的Windows专项已在Windows实际执行。

历史匿名真实样本S00001(JPG)与S00002(PDF首页)仅本地OCR：分别174与137字符、状态success、源哈希不变；结果仅证明解析可执行与非空，不冒充准确率评估。此历史结果不因后续语料配置变更而改写。后续语料位置只读取共享本地配置及MARKET_REGULATION_TEST_CORPUS，真实路径/文件名/正文不进入跟踪报告。

### 唯一剩余必需回归缺口

`test_postgres_integration.PostgreSQLIntegration.test_isolated_schema_build_publish_query_rollback` 尚无当前环境有效PASS。该旧方法会CREATE SCHEMA、初始化结构并最终DROP SCHEMA CASCADE，当前明确禁止结构修改/删除，因此未执行；这不是测试失败，也不能把SKIP改为PASS。旧v0.1成功证据存在，但缺少能够独立验证且匹配当前变更源码/依赖/配置/运行镜像的完整缓存指纹，不能按现有保守缓存策略直接复用。

最小后续路径：由用户明确批准独立新建空测试环境中的该用例DDL生命周期，或由QA审查一条使用预先初始化独立schema、保留全部测试记录且不执行DDL/删除的等价验收入口。两种路径均不能触碰现有资料或擅自削弱断言；批准/环境未满足前保持该项BLOCKED。

全语料质量无既定新准确率阈值，不是本轮新增门槛；真实BGE不属于J既定演示向量兼容标准，不作为额外阻塞；不把Fix附注的新安装/构建未测擅自提升为新增必需验收条件。旧round01 version-gate.json继续表示v0.1，未把本候选标成PASS。云端实际识别、生产部署不在本次结论内。

### 可复现入口与消毒证据

既有unittest用例经QA本地封装分阶段执行：六组Mock+独立v0.2.0+最新边界；真实HTTP；指定库两项持久化+DE-I；其余方法按case_id排除当前已PASS集合后增量执行；仅Windows专项与两项专用库再按完整方法ID补测。使用冻结源码和QA快照，不切换Fix工作树。机器路径、凭据、原始日志、执行封装保留在忽略目录。

原始字节SHA256：

- `summary.json`: `5d0ab09bd7d923895a69166da9831b71391c3d56d3d6872f66ff0c9aed5e408b`
- `real-corpus.json`: `f92577a0c867b02b985f57d414645bef20ff54027303d93744a7c272a6500e80`
- `handoff-verified.json`: `d6497ac14513ae7be834102e7c875d249335545a631adc4b708901a53cb95e47`
- `coverage-final.json`: `aea8cbf752f424ba7c12814aba159a7aa48c8be7da7aec14f6d85841d08a4025`
- `output/mock.json`: `b2c49e3dbbd6a71a180bffa5410126e405f167ce1056c6ab85260db6e96df3e3`
- `output/http.json`: `9461685fdc12b8fcabcc698cbba1145182a4dcaaaddd56d9d47230494da910c1`
- `output/postgres.json`: `59617129996f1c468fe365ce98ffa72ae1865813206249eab0012320b2c99639`
- `output/delta.json`: `310fe455420b07b8b1e900a0195d9bd450be67979e6f3113c3706d57ac0f73de`
- `output/windows-specific.json`: `d401e85f3c0665775c63c0756f4967be139f808f9d2d046d844a34d125ddacee`
- `output/qa-isolated-pg.json`: `df38b7ee280f6a74fe939e77ffde6c176962f771a2ba78fa63ca963b0ea0e67e`


### legacy缺口的最小待审批方案（仅准备，未执行）

已只读审阅Database.initialize：除随机测试schema外，还会创建law_chunks表/索引与VERSION_SCHEMA中的mr_*表/索引，并含CREATE EXTENSION IF NOT EXISTS vector。建议仅在既有独立qa_round01库创建新的随机mvp_test_<hex> schema，所有测试表/索引限定在新schema，预先确认public.vector已存在，禁止安装扩展、ALTER既有表和DROP。运行原方法全部业务断言，唯一替换为抑制finally清理的DROP并保留schema及合成记录，SET search_path仍正常复位。既有表与用户资料不改动。测试业务本身的版本发布/回滚仅作用于新schema内的合成数据。

已在忽略目录准备默认拒绝执行的qa_legacy_preserve_review.py，需显式审批参数及MVP_TEST_PG_DSN，并核验数据库名、QA隔离标记和既有vector扩展；仅对原test模块注入保留清理的Database子类，不修改原断言。当前未执行该入口或任何DDL，仍保持该方法BLOCKED。149是源码唯一方法的去重范围；辅助HTTP和匿名OCR不加入149重复计数。新语料配置仅适用于后续任务，本次历史OCR不得解释为新数据集已测。
