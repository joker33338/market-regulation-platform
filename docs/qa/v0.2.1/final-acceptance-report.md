# v0.2.1 最终独立验收报告

本轮结论：**BLOCKED**。代码回归存在 **FAIL** 项，不能发布 PASS。真实本地 OCR 已恢复可测且完成推理；旧的 Windows 模型阻塞结论不适用于本轮。标准答案扩展已交付并完成本轮评估，不再以“仅有两页全文参考”作为阻塞理由。

## 1. 版本、路径与执行身份

执行日期：2026-11-10，北京时间约 09:35—10:10。所有结果均为本轮执行；明确标注的历史证据不计入本轮通过数。

| 项目 | 本轮身份 |
| --- | --- |
| 唯一受测 Fix 分支 | `codex/fix-v0.2.1` |
| 唯一受测 Fix SHA | `a860abfa84bc2664bb119ae8f5b80c6794e6e23c` |
| QA 起始 SHA | `3bdcfdf007a30d29201760518263d12bca05924c` |
| QA 测试代码提交 | `78b7e05e747656414badd8350c83d48b672ecc16` |
| 业务源码根目录 | QA 固定目录同级的 `market-regulation-platform-fix` |
| QA 测试根目录 | `market-regulation-platform-qa/tests` |
| 原始绝对路径记录 | QA 忽略目录 `local/v021-final-a860abf/` 内的导入、盘点及执行证据；不将实际语料路径写入 Git |
| 测试集绑定 | 进程变量 `MARKET_REGULATION_TEST_CORPUS`，本轮绑定用户最新指定的主测试集；实际值见私有 `inventory.json` |

开始及结束均重新读取 Fix HEAD，保持指定 SHA，Fix 的 Git 工作区干净。QA 只新增测试、测试入口和本角色报告，没有修改业务代码、切换分支、覆盖目录、创建或删除 Worktree、Push、合并或部署生产。

独立入口为 `tests/run_v021_final_acceptance.py`。入口拒绝 QA 自测自身、错误 Fix SHA 或脏 Fix 工作区；显式绑定业务模块到 Fix，并核验所有实际加载的 `qa_core.*` 和 `query` 的 `__file__`。其中 `document_router`、`runtime`、`mineru_api`、`mineru_service`、`quality` 均来自 Fix 目录。完整绝对路径见 `committed-suite/suite-result.json` 的 `initial_bindings` 与 `imported_business_modules`。

共有测试从 Fix 文件位置加载，以便其相对路径夹具读取 Fix 的 `scenarios` 和 Dockerfile；入口先逐文件核验与 QA 的断言源码一致，仅允许 CRLF/CR 转 LF 差异，记录双方原始摘要与统一换行摘要。QA 独有测试仍从 QA 加载；`test_paths` 逐模块记录真实位置，没有删去失败用例。

初跑曾因测试子进程缺少 PYTHONPATH、QA 夹具指向自身缺少 scenarios、中文 TEMP 导致 ASCII 缓存校验失败而产生 4 个测试入口失败。修正入口后完整重跑，初跑记录保留于 `suite.log`，不将其冒充业务缺陷。最终执行使用已提交的 QA 测试版本。

## 2. 环境、差异和基础检查

- Windows、Python 3.12.16；复用已有 Python 环境和 Fix 的现有 API 包目录，未安装或升级依赖。FastAPI 0.115.12、httpx 0.28.1、uvicorn 0.34.2。
- 实际本地模型包：paddleocr 3.3.2、paddlex 3.3.10、paddlepaddle 3.2.2。使用已有离线模型，禁止下载与联网，模型推理单进程串行执行；仅把日志位置重定向至 QA 忽略目录，未替换预测函数或结果。
- `qa_core/`、`query.py`、Dockerfile、requirements.txt 的已提交内容与 QA 基线一致。但这些相同内容不能代替实际导入路径验证。
- **两边均没有 requirements-api.txt**，不能把双方缺失说成已存在且一致的依赖文件。
- 审计时的 66 个文件差异包括角色报告、QA 独有测试、QA 历史依赖拆分、Fix 的 scenarios 和 gateway/Compose/入口脚本。测试使用 Fix 的部署资源和现有实际环境，未从 QA 覆盖 Fix。部署、挂载及模型能力另行实测，没有仅凭业务文件相同外推。
- 68 个业务/脚本 Python 文件 AST 语法检查通过；PowerShell 脚本语法检查 0 错误。此项不是 Python 类型检查。
- Fix 内无 TypeScript 文件，该工作区 TypeScript 检查为 NOT_APPLICABLE。已有环境没有 pytest，实际执行 `python -B -m pytest --version` 返回 `No module named pytest`；pytest 入口 BLOCKED，使用项目已有 unittest 全量执行，不声称 pytest 通过。
- 两份 Docker Compose 均以进程内合成配置变量完成 `config --quiet`，退出码 0；未用其启动或更改原有项目服务。未设置变量时的前检失败也保留。
- `scripts/start_agent_workspace.ps1 -Role Fix` 实际返回旧分支守卫错误，见 QFA-004；语法通过不代表脚本可在当前分支启动。

## 3. 自动化、真实 HTTP 与容器

| 层次 | 本轮结果 | 边界 |
| --- | --- | --- |
| 已有完整测试 | 229 项：223 PASS、6 SKIP | 包含原有回归、MinerU Mock 契约、权限、恢复、路由与法律链路 |
| 加入本轮最小合成回归后的完整测试 | 232 项：223 PASS、3 FAIL、6 SKIP | 3 FAIL 对应 QFA-001～003；不是有意排除的用例 |
| 既有隔离 PostgreSQL 补跑 | 5/5 PASS | 替换上述 6 SKIP 中的 5 个相同方法 ID |
| 去重后的方法级验收 | **232 个唯一方法：228 PASS、3 FAIL、1 BLOCKED** | 剩余方法为需新 Schema 与清理的 PostgreSQL MVP 生命周期；原始 unittest 状态仍为 SKIP |
| 本机真实 TCP HTTP | PASS | 直接加载 Fix；上传、认证、跨用户隔离、任务完成、结果、幂等和应用重启后 SQLite 状态保持；远端为匿名 Mock |
| 独立 QA 容器启动及 restart | PASS | `/source` 只读挂载指定 Fix 目录；network=none、无宿主映射、非 root、cap-drop=ALL；重启后任务、结果、幂等、权限保持；远端 Mock |
| 已有持久入口 | 本轮 HTTP 200 | 仅 127.0.0.1:8180；原入口和容器未被重建、重启或替换 |

本轮开始 Docker 管道短时不可连接；复查 Docker Desktop 4.71.0 / Engine 29.4.1 已可用，持久入口返回 200。不能继续把“Docker 不可用”列为最终阻塞，也不能否定昨天的通过证据。

现有持久服务挂载 `source.commit` 为 `67709c4989781594dd6c4723666fdb2c21caaa7b` 的历史快照。显式 `/source` 上下文导入检查支持该挂载；普通 `docker exec python` 的默认导入上下文与应用启动的 cwd/PYTHONPATH 不同，不能用其默认 `/app` 推断服务实际来源。未获取受限的实时进程环境，不以静态检查冒充进程内观测。**现有入口 200 仅证明基础设施可用**；指定 Fix 的 HTTP/容器结论来自本轮另建的明确绑定运行实例。

测试结束停止新建 QA 运行容器，保留容器和状态数据；未删除卷、历史镜像、语料、模型或既有任务。

## 4. 场景集覆盖与真实 OCR

场景 01～12 全量 25 份，含 19 份正常场景、6 份异常负例，全部执行，没有删除失败样本。共输出 62 个逻辑页记录：native_pdf 33、ocr 18、structure 8、native_docx 3。文档逻辑页不等同于 Word 的物理排版页。

- 正常场景：18 份返回 success，1 份超像素安全限制被拒绝；其中 12 份带复核要求。success 是解析状态，绝不等同于文字、金额、表格或法律质量 PASS。
- 异常场景：2 REJECTED、2 failed、2 success。后两份为 S00022 伪造扩展名和 S00025 空白 PDF，属于已确认的负例契约失败。
- 25/25 语料执行前后 SHA-256 一致。所有原始输出、路径映射和全文仅在忽略目录。
- 文本 PDF、扫描件、混合 PDF、有线框/无线框、三栏、跨页表、隐藏 OCR 层、低质量扫描、Word、图片和异常文件均有本轮执行记录。没有标准答案的页只报告运行状态、路由与告警。
- PaddleOCR 与启用真实表格模型的 PP-StructureV3 均实际完成合成及语料推理；不存在以 FakeRuntime 代替本轮真实模型的情况。全量 auto 路由后，另对两个表格参考页强制 Structure 补测，单列结果，不把强制模式当作 auto 路由。

真实 PaddleOCR 对合成空白图片识别为空后，实际 DualEngineRouter 触发质量告警和官方客户端适配链；云端使用 MockTransport，共 5 次 Mock 请求，真实云请求 0。敏感标记的控制样本保留本地候选与复核信号，Mock 云请求为 0。既有 Mock 覆盖超时、限流、有界预算、未知 POST 不重发、撤销及权限隔离。此处验证真实本地结果与 Mock 云端的连接，不能替代真实双引擎云端验收。

## 5. v0.2.2 扩展真值及实际评估

已读取实际扩展包 README、覆盖矩阵 CSV/Markdown、全部 references、R-04 归因、样本意图、装配器与扩展评估器。矩阵实读 **66 条唯一记录：60 页级、6 文件级**。全文参考已由 2 页增至 4 页，表格参考由 2 份增至 4 份；本轮接受新增交付，不要求用户重复提供。

为保持主测试集及冻结包只读，把装配脚本与参考原字节复制到 QA 忽略目录，仅将运行时 ROOT 绑定回原测试集。第一次执行原装配器生成空映射模板；按当前实际预测文件填写路径和 Fix 完整 SHA；第二次执行原装配器及扩展评估器。没有修改算法、人工真值、原包映射或 labels.csv。附带的旧四项参考也重新绑定本轮预测评估，未拿历史预测冒充当前结果。

| 任务 | 实际路径/模式 | 状态 | 本轮结果 |
| --- | --- | --- | --- |
| CER-01 | auto，真实 OCR | MEASURED | 9/486，CER 1.85185% |
| CER-02 | auto，Native | MEASURED | 47/250，CER 18.8% |
| CER-02 补测 | 强制真实 Structure | MEASURED | 44/250，CER 17.6% |
| CER-03 新参考 | auto，真实 OCR | MEASURED | 16/648，CER 2.46914% |
| LAYOUT-01 新参考 | auto，真实 Structure | MEASURED | 1664/1857，CER 89.60689%；包含阅读顺序与内容差异，不宣称是纯错字率 |
| TABLE-WIRED | auto Native / 强制 Structure | MEASURED | auto 结构与全文均不精确；强制 Structure 结构及单元格全文精确 |
| TABLE-WIRELESS | auto Native / 强制 Structure | MEASURED | auto 未提取表格；强制 Structure 结构及单元格全文精确 |
| TAB-DOCX-01 新参考 | Native DOCX | MEASURED | 原评估器报表数 1 对 2 且不精确；参考仅表 0，不能据此把文档第二张表认定为多余。表 0 的纵向合并丢失另有真实与合成证据 |
| TAB-CROSS-01 新参考 | auto，真实 Structure | MEASURED | 结构及单元格全文精确 |

全文 CER 按交付脚本仅归一化换行，保留空白、标点及表格串行化差异，不混合不同引擎结果。业务阈值仍未约定，MEASURED 不是质量 PASS。

新增四项均从 READY_NO_PREDICTION 变为 MEASURED，没有 SHA 变化造成的 BLOCKED。本轮 4 个全文参考与 4 个表格参考均有当前预测；有明确参考的数据可评估，矩阵中未要求全文标注的页不要求重复补真值。原 labels.csv 与冻结包共 29 个受保护文件，本轮前后摘要全部一致；扩展包本身也未变化。历史交付前的逐字节状态没有完整独立基准，不伪称重新证明交付前全历史未修改；旧四项预测与原记录摘要另已核验相符。

R-04 材料中的旧本地预测实际引擎字段为 structure，摘要与原任务一致；本轮强制 Structure 两张参考表也均精确。旧云端 25/30 单元格文本匹配是历史结果，不能当成本轮当前 SHA 的云端结果。当前仍需在有效授权和既有账本约束下补当前云端预测，再按同一标准比较；不把 API 成功当成质量通过。

## 6. PostgreSQL、BGE-M3 与知识库

复用已有标签为 QA round01、无宿主端口、内部网络的专用数据库；先只读核验库名 `qa_round01`、隔离标记及现有 `document_review` Schema，再执行 5 项仅合成插入/读取/事务回滚的测试。源码以只读方式挂载 `/source`，实际模块来源全部核验。未执行 DDL、DELETE、DROP、TRUNCATE、清空预算或生产库操作，数据保留，测试库恢复原先停止状态。

5 项对应：父子事务回滚、幂等且保留旧行、字段/来源/单元格映射、冲突保护与多层回滚、数据库提交后中断重试。唯一剩余方法 `test_isolated_schema_build_publish_query_rollback` 会 CREATE/DROP Schema，并经业务流程清理投影；本轮没有该操作范围的明确授权，因此保留 BLOCKED，未运行。

BGE-M3 从原有本地模型实际推理两个合成法律句子，2 个向量均为 1024 维，范数约 1，禁止联网。不是 DemoEmbeddings。

另已发现并读取场景 13 的新离线入库专项说明和标准答案，11 个定义任务的 `load_file → parse_articles → split_articles(max_chars=800)` 对照全部 PASS（含两个负例），源文件摘要不变。扫描文档对应的合成原文切分结果不冒充其 OCR 复核稿；此项未执行 PG kb_version 生命周期、版本向量复用或正式发布。已有 unittest 的人工复核门禁、法律切分与 SQLite 检索通过；其 DemoEmbedding 测试与上面的真实 BGE 分开统计。**真实 BGE→完整版本化 PostgreSQL→检索的一体链尚未完成**。

## 7. R-01～R-08 重新裁定

| 编号 | 状态 | 本轮依据及剩余条件 |
| --- | --- | --- |
| R-01 业务验收标准 | PENDING_USER_CONFIRMATION | 已给出真实 CER、表格和路由结果；仍不能自行设质量阈值。不是要求重交标准答案 |
| R-02 完整集和标准答案覆盖 | PASS | 就本次扩展交付及声明覆盖范围：66 条矩阵核验，25 份场景全量执行，4 全文+4 表格参考全部实际评估；不表示未标注页质量合格 |
| R-03 MinerU 远端任务恢复 | BLOCKED | 原授权 expires_at 早于本轮检查，旧预检绑定旧 SHA；账本保留 12 次占位。未续期或重新 POST；S00010 真实远端恢复未在当前 SHA 执行 |
| R-04 云端质量复核 | BLOCKED | 新归因材料已读取；当前本地 Structure 单列实测完成。缺当前 SHA 的有效授权云端预测与相同真值评估，历史云端结果不替代 |
| R-05 本地 OCR 和自动回退 | BLOCKED | 本地 Paddle/Structure、全量 auto 与真实本地→Mock 云回退通过；真实云端 auto 回退未完成。旧 Windows 模型阻塞已经消除，不再沿用 |
| R-06 Windows 整机重启验证 | PENDING_USER_CONFIRMATION | 系统读回本次启动时间为当天 08:32，当前持久入口 200、容器可用；未独立观测完整重启前后过程及用户确认，不能用容器 restart 或启动时间替代该验收 |
| R-07 数据库生命周期 | BLOCKED | 5 项已获准 Schema 测试 PASS；完整 kb_version/发布回滚测试仍涉及未明确获准的独立 DDL/清理范围 |
| R-08 OCR 路由边界 | PENDING_USER_CONFIRMATION | S00019 确认按像素限额拒绝；新样本意图同一行又说修复后应正常 OCR，含互相冲突的接受行为。保持原标签与安全限额，请确认该条的最终含义；不自行放宽限制 |

## 8. 已确认问题与 Fix 任务

本轮确认 4 项 P2，未新确认 P0/P1。这个分级不意味着允许忽略失败或解除版本阻塞。

| ID | 证据及实际结果 | 修复验收 |
| --- | --- | --- |
| QFA-001 | S00025 空白 PDF 返回 success，带 empty_page/复核告警；合成回归 FAIL | 异常空白负例不再报告成功；混合文档合法空白页与不加载 OCR 的行为不退化 |
| QFA-002 | S00016 表 0 真值 257 个锚点、32 个 rowspan>1；当前 330 个单元格、0 个纵向跨度；两行合成 vMerge 也被展开为两个 rowspan=1 单元格 | 正确解析 vMerge restart/continue、保留锚点/跨度/来源，合成和原表 0 通过，不按参考只含一表而删除真实第二表 |
| QFA-003 | S00022 后缀 PDF、实际 PNG；PyMuPDF is_pdf=False、format=Image，仍 OCR 后 success；合成回归 FAIL | 按内容验证文件类型；伪装文件拒绝/失败，正常 PDF/图片仍可处理 |
| QFA-004 | Fix 启动脚本实际拒绝 codex/fix-v0.2.1，仍只接受 fix/round1 | 最小适配当前固定角色分支；保持拒绝错误角色及未知分支，不更改既有工作树/目录 |

根因、精确命令、源码函数、优先级和交接边界见 `final-handoff-to-fix.md`。布局大 CER、auto/Structure 表格差异作为待工程分析的质量观测，不在缺乏质量阈值时另编造已确认代码缺陷。

## 9. 证据索引与最终关卡

所有以下路径相对 QA 固定目录，包含原始路径/全文的证据均被 Git 忽略：

- `local/v021-final-a860abf/committed-suite/suite-result.json`、`committed-suite.log`：冻结身份、全部业务 __file__、测试文件路径/摘要、232 个方法 ID、失败与跳过理由。
- `local/v021-final-a860abf/pg-result.json`、`pg-execution.json`、`pg.log`：5 个方法 ID、独立库身份、只读挂载、保留数据与恢复停止状态。
- `local/v021-final-a860abf/inventory.json`、`private-map.json`、`S*-parse-summary.json`、`S*-prediction.json`、`execution-summary.json`：盘点、25 份逐项执行、原始预测与摘要。
- `local/v021-final-a860abf/truth-audit.json`、`protected-before.json`、`evaluation-summary.json`、`expanded-evaluation/`、`frozen-current-evaluation/`、`forced-structure-evaluation/`、`assembly-first.log`、`assembly-second.log`：原包核验、映射两轮装配、各引擎评估、真值不变检查。
- `local/v021-final-a860abf/engines.json`、`engines.log`、`reference-engines.log`、`real-local-fallback.json`、`real-local-fallback-final.log`、`bge.json`、`bge.log`：真实本地推理、Mock 回退控制及真实 Embedding。
- `local/v021-final-a860abf/real-http.json`、`container-runtime.json`、`docker-state.txt`、`app-mounts.json`、`persistent-import-origin.json`、`windows-boot.json`：实际 HTTP、专用容器重启及原持久入口检查。
- `local/v021-final-a860abf/static.json`、`compose-corrected-summary.json`、`config-summary.json`、`powershell-syntax.json`、`pytest-availability.log`、`start-agent-guard.log`：静态、配置及启动证据。
- `local/v021-final-a860abf/cloud-authorization-check.json`、`historical-prediction-origin.json`、`negative-summary.json`、`type-mismatch.json`、`legal-special.json`：授权边界、历史来源核对、负例归因及场景 13。
- `local/v021-final-a860abf/evidence-manifest.json`：本轮证据文件摘要、测试时段及版本；原始执行辅助脚本也保存在该忽略目录，便于审计。

本轮没有真实 MinerU API 请求，不能写其本轮 PASS。没有定义业务阈值，不能把 MEASURED 改写为 PASS。必要集成和生命周期条件尚未满足，且有明确回归失败，**v0.2.1 最终闸门保持 BLOCKED**。修复需要新 Fix SHA 后重新绑定独立验证；不 Push、不合并 main、不部署生产。
