# v0.2.1 离线入库优化专项独立 QA 最终报告

**专项结论：PASS。** 本轮已完成 OFF-QA-01～17、相同样本的优化前后对照及相关兼容性回归，未发现新的已确认业务代码缺陷。该结论仅针对本次离线入库优化，不代表 v0.2.1 整体版本通过，不授权 Push、合并 main、真实资料发布或生产部署。

## 1. 冻结版本、授权与源码绑定

| 项目 | 实际值 |
| --- | --- |
| 优化前源码 | `c78530f191bad1a46fcfade4bb597b4e422a5754` |
| 优化后源码 | `8ecff8866232ca33d0e350e6ead311fe8570aa89` |
| 首次正式交接 | `7fadee031ed9d6f2664afd75357e802c38cc79cb` |
| 数据库范围补充后的最终交接 / Fix HEAD | `967cff1e6eec0277b5103182b47098720367c228` |
| Fix 分支 | `codex/fix-v0.2.1`，开始和结束均干净 |
| QA 起始 SHA | `0881807ee0524503c54b0f08fcca96c922f9828e` |
| QA 最终测试 SHA | `553c8562eee40d06aa0ae0281f916535892a42d0`，分支 `codex/qa-v0.2.1` |
| PostgreSQL 六项实际使用的 QA 提交 | `83ee78cb5dd0b5e5640fc5523bf9efd752ad8791`；随后只补充法规长标题/上下文测试，数据库夹具与原六个方法未再修改 |

执行日期为 2026-11-10，北京时间。任务初始两个 SHA 少字符，曾按要求记录接收 BLOCKED；用户随后确认采用正式文档和实际 HEAD，此阻塞已解除。初始接收报告和命令证据保存在私密 `version-reception/`，不把未绑定阶段称作测试通过。

最终交接相对优化后源码仅新增/更新交接文档；六份源码范围核对无误：settings、chunking、service、bridge、preview 和 preview CLI。优化前是优化后祖先，优化后是交接提交祖先。

使用 `git -c core.autocrlf=false archive` 将两个精确提交分别提取到 QA 忽略目录，逐文件核验 Git blob：优化前 194 份、优化后 196 份。没有 checkout、覆盖 Fix 或创建 Worktree。初次导出受 autocrlf 影响未通过摘要检查，未使用该未验证导出执行正式测试；原导出也保留。

实际源码根目录分别为 QA 的 `local/offline-ingestion-qa/before-source-exact` 与 `after-source-exact`，不是 QA 自身旧版 qa_core。优化前后对照、专项测试、真实 BGE 和 CLI 使用精确快照；完整兼容性回归直接绑定 Fix 最终 HEAD，并验证其相对优化后提交仅有文档差异。Docker 内只读挂载该快照为 `/source`，测试文件挂载为 `/qa-tests`。

实际 Python `__file__` 已记录并断言属于指定源码根目录：特别包括 chunking、service、bridge、preview、document_router、schemas、storage 和 retrieval。完整绝对源码路径、测试代码路径、解释器位置、模块列表及时间见各阶段结果 JSON 的 bindings / imported_business_modules / test_paths。按项目保密约定，机器绝对路径不写入 Git 报告。

## 2. 环境和执行边界

复用 Windows Python 3.12.16、已有 API 包、已有本地 BGE-M3，以及现有 Docker 基础镜像；未安装或升级依赖，未下载或重新部署模型。Linux 专项容器使用 network=none、只读源码、非 root、cap-drop=ALL 和 no-new-privileges。

测试集通过 `MARKET_REGULATION_TEST_CORPUS` 和 pathlib.Path 读取，绑定用户已补齐的主测试集。标准答案、labels、冻结包和场景文件没有修改；前后对照阶段保护并核验了 100 个文件，全部摘要不变。原路径、原文、预测、模型及凭据均在忽略目录，不提交 Git。

优先复用了已有真实解析 JSON；这些 JSON 的 OCR 产生于历史 SHA `a860abfa84bc2664bb119ae8f5b80c6794e6e23c`，只是本轮新切分代码的固定输入，**不冒充当前 SHA 的新 OCR 推理**。未调用真实 MinerU API、上传测试文件或关闭网络/DNS/Windows 安全保护。

数据库最初按原禁令未写入。Fix 后续交接更新范围后，用户在本聊天明确回复“确认，按最新交接范围补跑六项数据库测试”。该授权才替代本轮原有 DDL/业务库写入限制；没有仅凭截图或 Fix 的转述执行。

## 3. OFF-QA-01～17 结果

| 编号 | 状态 | 本轮实际证据与边界 |
| --- | --- | --- |
| 01 层级及条之一 | PASS | 合成编/章/节/条及真实标准中的条号、顺序、父子引用核对 |
| 02 长条条件与例外 | PASS | 父文、片段正文可恢复；否定/但书保留；长标题与引导语只限制 Embedding，不截正文 |
| 03 数值临界和超长单句 | PASS | 日期、金额、百分比、文号核心在边界保持完整；超长受保护字段明确拒绝；罕见格式不外推 |
| 04 短款组合及序号 | PASS | 长条 9→6；条内 fragment_index / fragment_total 连续且统一，正文不丢失 |
| 05 ID、移动及参数 | PASS | 相同内容/配置稳定；改变上限或 bbox 修订变化；移动源路径不重新编号 |
| 06 空格/Markdown 条号 | PASS | 首条定位与既有 ARTICLE 一致；条前内容进入 unassigned_preface |
| 07 案例及法条引用 | PASS | 合成已标注案例分节及引用原位保留；案例未进入法规分支。真实案例分节准确率 NOT_LABELED |
| 08 普通编号及长标题 | PASS | 不单凭普通编号分节；无标题正文完整；长标题 Embedding 有界。真实标题语义准确率 NOT_LABELED |
| 09 页、行、bbox 与缺块 | PASS | 页序/来源范围保留，缺正文块页面显式告警，不称生产可用；来源精度为 unit，不是字符级 |
| 10 排除项 | PASS | 页眉/页脚/注释/页码/图片说明排除可见，原结果保留，须人工核对实质内容 |
| 11 表格 | PASS | 案例表格独立保留跨度和来源；法规含结构化或未结构化表格块均拒绝，未摊平 |
| 12 异常与上限 | PASS | failed/partial/空正文/重复条号/目录/越界拒绝；needs_review 不伪造审核；原文件保护另复测 |
| 13 三种 CLI 来源 | PASS | 同一合成 Word 的原文件、实际 JSON 和真实数据库记录均经原 CLI，三个完整预览 JSON 完全一致，无重复 OCR |
| 14 只读、安全及原子输出 | PASS | DB 预览仅参数化 SELECT；身份、关闭连接、参数预检、防覆盖、写入中断和符号链接保护验证。Windows 缺符号链接权限，该方法改由 Linux 同代码实测 PASS |
| 15 版本和 ACTIVE | PASS | 新策略进入 processing_signature / revision；缓存资格与修订分开；原业务 ACTIVE 不变；随机测试 Schema 内真实生命周期通过 |
| 16 正式桥接审核 | PASS | 缺复核人、失败/部分结果、表格仍拒绝；预览仅 requires_review，不生成审核或发布记录 |
| 17 相关既有回归 | PASS | 267 个唯一方法合并后全部通过，包含六项 PostgreSQL，原有断言保留 |

“PASS”指清单的工程行为和兼容性，不将正文 roundtrip 当作 OCR、法律语义或真实阅读顺序准确率。

## 4. 方法级统计（去重）

- Windows 最终完整执行：267 项，260 PASS、7 SKIP、0 FAIL、0 ERROR。
- 7 SKIP：6 项 PostgreSQL 未在默认入口配置 DSN；1 项 Windows 当前令牌不能创建测试符号链接。
- 用户授权数据库入口：原六个方法全部 PASS、0 SKIP。原数据库名/主机/标记保护保留在默认夹具；受控入口仅替换两项 setup 的目标身份核验，不伪装 qa_round01 或设置 test-only 标记，测试方法的字段、幂等、回滚断言均不变。
- Linux 同源码专项：20/20 PASS，包含实际创建符号链接的保护测试。与 Windows 重叠的 19 项不重复计数。
- **按相同方法 ID 合并后：267 个唯一方法，267 PASS、0 FAIL、0 BLOCKED。** 探针、真实样本和模型评估另列，不加进该方法数。

默认完整入口清空 DSN 的保护未修改；业务库需要显式授权参数、准确目标、源码快照及受控 SQL 范围。DE-I 旧适配器的 isolated_postgres 字段是历史测试协议标签，不是本轮数据库身份；真实连接始终核验为获准的 market_regulation，未伪造库名或隔离标记。

## 5. 标准答案与优化前后对照

相同 Python、同一模型签名 QA-SAME-MODEL、max_chars=800、同样 11 个法律专项定义执行。每个正例重复 5 次 prepare_document，表中耗时为中位数，仅包含清洗、结构、切分及质量校验，不含 OCR、模型加载或数据库。

| 样例 | Chunk 数量（前→后） | 条号及正文参考一致 | prepare 中位数（前→后） |
| --- | --- | --- | --- |
| LEGAL-001 | 11 → 11 | 是 | 0.213 → 0.382 ms |
| LEGAL-002 | 7 → 7 | 是 | 0.170 → 0.334 ms |
| LEGAL-003 | 9 → 6 | 是 | 0.205 → 0.209 ms |
| LEGAL-004 | 8 → 8 | 是 | 0.155 → 0.181 ms |
| LEGAL-005 | 9 → 9 | 是 | 0.178 → 0.356 ms |
| LEGAL-006 | 9 → 9 | 是 | 0.176 → 0.198 ms |
| LEGAL-007 | 8 → 8 | 是 | 0.156 → 0.191 ms |
| LEGAL-008 | 前后均拒绝 | 不适用 | 不计正例耗时 |
| LEGAL-008B | 前后均拒绝 | 不适用 | 不计正例耗时 |
| LEGAL-009 | 7 → 7 | 是 | 0.173 → 0.160 ms |
| LEGAL-010 | 13 → 13 | 是 | 0.220 → 0.423 ms |

9 个正例：条号列表 9/9 与原标准一致，去掉人工重复法条前缀并统一空白后，正文 9/9 与原参考一致。2 个负例前后都拒绝。原标准 11 项、正文与块边界没有改写：8 个正例仍精确匹配旧边界；LEGAL-003 的旧 9 块边界精确匹配为 false，按优化允许的短款组合变为 6 块，但正文、顺序、来源、父文均保持。该预期变化单列，不把旧边界不相同偷偷改记相同。

| 指标 | 优化前 | 优化后 | 解释 |
| --- | --- | --- | --- |
| 正例总 Chunk | 81 | 78 | 长条相邻短款组合减少 3 块；不是以少块代替正确性 |
| 父条文引用 | 81/81 | 78/78 | 各自按实际 revision + article_no 核验 |
| 页/行来源完整 | 81/81 | 78/78 | 可用 bbox 保留，TXT/DOCX 无 bbox 不伪造 |
| 条内片段序号与总数 | 76/81 | 78/78 | 旧版本按 unit 计算总数；新版本按父条文统一 |
| 最大 Embedding 字符数 | 828 | 828 | 真实样本标题较短；超长标题/引导语限制另有合成用例验证 |
| 九份正例中位耗时之和 | 1.645 ms | 2.434 ms | 本小样本没有证明提速，约增加 0.789 ms；不是一次批处理耗时或生产 SLA |
| 语义完整性准确率 | NOT_LABELED | NOT_LABELED | 有正文与结构不变证据，但没有人工语义逐块评分，不推算百分比 |
| 案例分节准确率 | 基线无该预览 API | NOT_LABELED | 合成期待已测试；真实样例未提供该项语义标签 |

九份法规 revision / processing_signature 因切分版本变化而区分。78 个新片段中 77 个 Embedding 输入哈希在对应旧文档集合中已存在，说明这些向量具备复用资格；这不是跨策略真实库的缓存命中次数。原回归另有实际重复构建/版本复用断言。策略变化不会绕过 full_snapshot 保护或隐式替换 ACTIVE。

基线没有 preview.py 或预览 CLI，按正式交接比较其既有 parse_articles / split_articles / prepare_document。未向基线补业务代码，也未把基线不存在的案例预览 API 记作回归失败。

## 6. 真实场景 01～12 覆盖

25 个原样例全部保留并对照原文件摘要。复用 22 份已有解析 JSON；3 份原来被安全拒绝/无预测的样例不伪造预测。19 份缓存结果产生案例预览，共 70 个子片段，父子引用 70/70、正文重组 19/19，均带人工复核标记，没有未提示的非空缺块页。其余缓存 failed/空正文结果拒绝。

| 场景 | 样例 | 实际范围 |
| --- | --- | --- |
| 01 文字 PDF | S00001～02 | 原生结果的段落、来源和案例预览 |
| 02 扫描 PDF | S00003～04 | 已有真实 OCR/Structure 结果的正文和表格保留 |
| 03 混合 PDF | S00005～06 | 原页号、跨页来源与预览 |
| 04 有框线表格 | S00007 | 结构化表格独立保留；法规分支不得摊平 |
| 05 无框线表格 | S00008～09 | 固定 auto 结果预览；不凭此次切分宣称表格识别精度 |
| 06 多栏 | S00010～11 | 现有顺序与来源保留；不将 roundtrip 当作原页面阅读顺序正确率 |
| 07 跨页表格 | S00012 | 页及表格结构保留 |
| 08 隐藏 OCR 层 | S00013 | 现有 OCR 候选被完整消费，不重新 OCR |
| 09 低质量扫描 | S00014～15 | 复核信号及固定正文预览，不宣布质量合格 |
| 10 Word | S00016～17 | 原生逻辑页、正文与独立表格保留；另有真实 Word 三来源 CLI 一致性 |
| 11 图片 | S00018～19 | S18 缓存 OCR；S19 原文件按安全像素限额拒绝，无模型调用 |
| 12 异常文件 | S00020～25 | 缓存失败拒绝及当前原文件门禁复测，见下述区分 |

S00022 的旧缓存来自早期版本，当时伪造扩展名曾被误解析；本轮作为既有 JSON 可以预览且强制复核，不能因此认定当前文件门禁失败。当前精确源码对其原文件重新检查已拒绝，模型调用为 0。S00019/20/24 也拒绝，S00025 返回 needs_review（不再是 success），均无模型调用、摘要不变。损坏缓存 S00021/S00023 和空正文缓存 S00025 不进入预览。

本轮不重复计算历史 OCR CER 或把没有案例标题/语义标签的字段写成百分比；标准答案扩展已接收，不要求用户补交重复资料。

## 7. 原有能力与实际 BGE-M3

PDF/Word 解析、PaddleOCR 与 PP-StructureV3 结果协议、结果恢复/标准化、MinerU 官方适配与 Mock 回退、复核门禁、清洗/切分、安全授权/预算和检索相关既有回归均通过。六文件优化没有修改 OCR runtime、模型、官方客户端、解析结果 schema 或 PostgreSQL 表定义；固定原始结果通过当前桥接/预览消费，来源及表格未被新切分逻辑摊平。

按“优先已有结果”要求，没有重新对全部样例运行真实 OCR，也没有执行真实 MinerU 云端；上述对应回归如使用 FakeRuntime/MockTransport，仍按 Mock 报告，不能冒充新真实模型/云端精度。

真实本地 BGE-M3 对 LEGAL-003 优化后的全部 6 个 Embedding 输入实际推理，输出 6×1024 维，范数约 1；实际 Token 数为 [49, 439, 125, 510, 91, 37]，均小于 2048。没有截断正文或偷偷放宽预算。PostgreSQL 生命周期用例的向量是原测试定义的合成 1024 维契约夹具，与这项真实 BGE 测量分开，不宣称完整真实语义 RAG 生产验收。

## 8. 数据库实际执行及数据保留

使用用户后续明确授权的既有 market_regulation；没有新建数据库、伪造 QA 标记、迁移已有 public/document_review 表或安装扩展。已有 public.vector 在写入前核验。源码只读挂载精确快照，入口核对数据库、账号、地址与端口；凭据只从私密配置/进程环境读取。

六项原方法全部实际执行：两项 ParsingPostgres、两项 Round01PostgresAcceptance、DE-I 提交中断恢复、MVP 随机 Schema 的 build→publish→retrieve→version reuse→rollback。原业务断言保留。

前五项仅使用随机合成任务/文件 ID 和 synthetic 来源；对每个计划 parse_id 先检查不与已有记录冲突。生命周期只在新建 mvp_test_UUID Schema 运行，初始化后逐表核对名称解析到该 Schema，业务 SQL 前持续校验；禁止回退访问 public 同名对象。复用 vector，抑制原用例末尾 DROP Schema CASCADE，仅保留测试 Schema；未跳过主体或业务断言。

**确实执行了经新授权允许的 DDL 和测试投影 DELETE**，不能写成完全无 DDL/DELETE。最终有效生命周期执行创建 1 个随机 Schema、8 张测试表，执行 5 条显式建索引语句；连同表约束自动创建的索引，实际目录核验为 14 个索引、1 个序列。6 条 DELETE 语句只针对本次 Schema 的合成投影。真实业务 ACTIVE、public.law_chunks 及全部原业务行摘要不变。CLI 的数据库来源本身仍只读 SELECT，与测试夹具写入分开。

首轮已进入写入的尝试中，QA 安全检查器在 SET TRANSACTION 前插入 SELECT，造成事务顺序错误；这是已复现并修正的测试夹具问题，不是业务缺陷。修正后原六方法 6/6 PASS；首轮失败日志和其测试 Schema/数据全部保留，没有删结果、降断言或把首轮标成通过。更早两个接收前检分别被 DSN 格式及 inet 地址掩码检查挡住，没有写入。

本轮两次进入六项测试，累计保留 10 条合成 documents；另为 OFF-QA-13 的同一原文件/JSON/数据库真实对照新增 1 条合成 documents，总计 11 条。两份随机测试 Schema 均保留，各实际含 8 表、14 索引、1 序列。精确 Schema 名、目录清单、记录 ID、逐表增量、原行 MD5 多重集和执行事件位于私密证据；Git 报告不包含真实文档内容或凭据。

额外真实三来源对照使用自建合成 Word；先准备 1 条授权的结果记录，再经原 CLI 分别读取原文件、JSON 和该记录，三个完整报告完全一致、源文件摘要不变、rag_index_written=false。现有业务行再次核对不变。没有部署或重启现有业务容器。

## 9. 缺陷、限制及最终判断

新增已确认业务 Bug：0；优化新增异常：本轮测试未发现。测试入口自身的导出/地址/事务顺序调试与业务结果区分，失败证据保留。

限制如实保留：真实案例分节/语义准确率 NOT_LABELED；预览不是法律审核，不证明 OCR、阅读顺序或实体事实正确；来源精度仍为 unit，DOCX 页码为逻辑页；少数罕见中文金额/文号不保证自动保护；基线不存在的预览 API 无数值对照；小样本耗时不支持宣称提速。Windows 的符号链接创建权限仍未改变，安全逻辑由部署常用的 Linux 环境实测。

以上限制均属于正式交接已声明范围及指标口径，不以此发明新增功能需求或修改真值。所有要求的专项工程检查和相关回归均有实际证据，故专项 PASS。既有 `version-gate.json` 未被修改，其整体 BLOCKED 属于先前版本验收记录；当前专项补充证据需与其他专项、业务质量及版本统一门禁综合，不自动把整体改为 PASS。

## 10. 复现命令与证据索引

在 QA 固定目录使用现有 $Python。完整命令和原始路径在私密日志；以下仅列无凭据模板：

```powershell
& $Python -B tests/run_offline_ingestion_qa.py --source-sha 8ecff8866232ca33d0e350e6ead311fe8570aa89 --source local/offline-ingestion-qa/after-source-exact --output local/offline-ingestion-qa/special-new-run
& $Python -B tests/run_offline_ingestion_comparison.py --source local/offline-ingestion-qa/before-source-exact --source-sha c78530f191bad1a46fcfade4bb597b4e422a5754 --output local/offline-ingestion-qa/before-new-run
& $Python -B tests/run_offline_ingestion_comparison.py --source local/offline-ingestion-qa/after-source-exact --source-sha 8ecff8866232ca33d0e350e6ead311fe8570aa89 --output local/offline-ingestion-qa/after-new-run
# 完整回归入口需指定已有 API 包目录，并设置 OFFLINE_QA_SOURCE 为上述QA内精确快照，以便CLI夹具只写QA目录。
# 业务库六项入口 tests/run_offline_business_postgres.py 只能带显式授权参数和私密scope/环境运行，不通过命令传密码。
```

全部证据均位于 QA 忽略目录 `local/offline-ingestion-qa/`：

| 路径 | 内容 |
| --- | --- |
| version-reception/ | 初始错误 SHA、只读接收、原 BLOCKED 报告 |
| before-source-exact/snapshot-identity.json、after-source-exact/snapshot-identity.json | 194/196 份 Git blob 核验 |
| before-results/comparison.json、after-results/comparison.json | 相同真值/参数/运行环境、逐样本 Chunk/来源/耗时与实际模块路径 |
| after-results/samples/S*/chunk-preview.json | 私密真实结果的案例预览 |
| final-committed-regression/suite-result.json、final-committed-regression.log | 最终 267 个方法的原始结果、实际 Fix 导入路径、QA 测试位置 |
| linux-special/result.json、linux-special-history/ | 20/20 及历史容器完整日志，包含符号链接实测 |
| latest-business-pg.json、business-pg-*/database-result.json、business-pg-*/execution.log | 六项补跑、含首轮失败、授权、随机 Schema、原业务行摘要和副作用 |
| retained-test-catalog.json | 两份保留 Schema 的表、索引和序列实际目录 |
| real-three-source.json、real-three-source.log | 同一 Word 三来源真实 CLI 完整一致性及额外合成记录 |
| bge-compatibility.json、bge-compatibility.log | 当前代码真实 6×1024 推理及 Token 预算 |
| cache-eligibility.json、original-guards.json、original-guards-final.log | 77/78 缓存资格、当前原文件门禁与零推理记录 |
| evidence-manifest.json | 全部阶段版本、证据摘要及最终时间 |

本报告对应的实际报告提交 SHA 由最终回复提供；文件不伪造自身未来提交号。未 Push、未合并、未改 Fix 业务代码、未发布真实知识库。
