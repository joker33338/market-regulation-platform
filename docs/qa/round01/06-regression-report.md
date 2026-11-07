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
