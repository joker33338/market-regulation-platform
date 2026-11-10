# v0.2.1 离线入库链路优化：冻结源码与 QA 正式交接

## 交接状态与职责

- 日期：2026-11-10。
- 本轮用途：法规与处罚案例分别处理，优先保证离线解析、切分和来源完整性。
- Fix 分支：`codex/fix-v0.2.1`。
- 优化前完整 SHA：`c78530f191bad1a46fcfade4bb597b4e422a5754`。
- 优化后源码完整 SHA：`8ecff8866232ca33d0e350e6ead311fe8570aa89`。
- 源码提交组成：`8302fbe65947cf69e127ed02f1e0dbfeaf97d893`（离线切分优化）及 `8ecff8866232ca33d0e350e6ead311fe8570aa89`（表格门禁兼容性收尾）。
- 交接状态：**READY_FOR_QA**。六份范围内源码已独立提交；此前“四改动、三未跟踪”的草稿状态已完成收尾。
- 受测源码目录：固定 `market-regulation-platform-fix` 工作区根目录，QA 以 `$FixRoot` 显式绑定；不改工作区路径或分支。
- Fix 已完成静态检查和不涉及业务样本的轻量合成自检；OFF-QA-01～17、样本对照、性能与正式回归均未执行，由 QA 独立完成。
- 本文通过后续独立 docs 提交传输。最终交接完整 SHA 在 Fix 最终回复提供，也可用 `git log -1 --format=%H -- docs/qa/v0.2.1/offline-ingestion-handoff-to-qa.md` 读取；文件不伪造自身未来提交号。
- QA 若绑定包含本文的最终 HEAD，应先确认相对源码 SHA 仅有文档差异，再向源码绑定入口传入该 HEAD；不得把工作区改动标成历史 SHA 的结果。
- 本文件是 Fix 的说明文件，不覆盖 QA 已有报告、测试断言或版本闸门。

## 文件与函数清单

| 文件 | 主要位置 | 离线链路优化实现 |
| --- | --- | --- |
| `qa_core/config/settings.py` | `CHUNKER_VERSION` | 以 `legal-parent-child-v2` 标识本轮切分规则 |
| `qa_core/indexing/chunking.py` | `pack_units`、`split_articles` | 相邻短款项组合、超长单元分段、父条文关联、条内统一片段序号、Embedding 标题与引导语长度控制 |
| `qa_core/indexing/service.py` | `prepare_document`、`ingest_documents` | 文档修订和构建签名纳入切分版本，避免错误复用旧策略结果 |
| `qa_core/document_parsing/bridge.py` | `source_lines`、`to_legal_document` | 提取可复用的来源行转换；正式法律入库仍要求复核人，仍拒绝直接摊平表格 |
| `qa_core/indexing/preview.py` | `preview_chunks` | 整理草稿已有的分类预览、父子片段、来源与完整性指标，统一首条定位，限制编号标题误判 |
| `scripts/preview_offline_ingestion.py` | `load_result`、`main` | 整理草稿已有的离线辅助入口，提前校验参数、防覆盖输入、原子输出，确保连接最终关闭 |

本轮没有改问答提示词、检索生成接口、OCR 模型、数据库 Schema 或线上工作台页面。
没有自动构建/发布知识库，也没有将案例写入原有法规检索表。
`preview.py` 和辅助脚本在优化前基线尚未入 Git，本次首次纳入冻结提交；这是对先前工作区草稿的收尾，不宣称它们早已存在于基线。
两者只服务现有离线链路的检查辅助，不新增对外 API、页面、实体抽取或自动发布流程。

## 优化原因、前后差异与风险

| 文件/环节 | 优化前或草稿问题 | 冻结后的行为与预期收益 | QA 风险及映射 |
| --- | --- | --- | --- |
| settings/service：版本 | 基线签名未包含切分规则版本，变更策略可能仍命中旧修订 | 构建和文档处理签名均纳入 CHUNKER_VERSION；旧 ACTIVE 的发布/回滚代码未改，不能隐式更新 | 核验旧向量是否仅在同输入文本/模型时合理复用；OFF-QA-05、15、17 |
| chunking：短款项/长单元 | 基线长条通常逐 unit 输出，短项容易碎片化；fragment_total 按各 unit 计算 | 相邻短单元按上限组合，不跨条；超长单元分段，片段序号/总数在父条文内统一 | 原有语义边界仍需对照，不以数量减少当正确率；OFF-QA-01～05 |
| chunking：字段与上下文 | 硬长度边界可能落在数值内部；草稿复用的首款引导语可能很长 | 可识别的数值/日期/文号核心跨界时调整边界；单个受保护字段本身过长则拒绝而非截断；只限制 Embedding 标题/引导语，父文与子正文不截断 | 中文大写金额、罕见文号格式不保证自动识别，须实样核对；OFF-QA-02、03、17 |
| bridge：来源转换 | 正式桥接内联生成来源行，预览需相同转换 | 抽取 source_lines 复用原逻辑；保留文件关联、页/行、可用 bbox 和来源证据，审核/表格门禁不变 | 跨页长 unit 来源仍为 unit 级；OFF-QA-09、10、16 |
| preview：法规/案例 | 草稿首条定位另写正则，与 ARTICLE 不一致；所有短编号行容易成为案例标题；仅检查已提取表格会遗漏只有表格块的情况 | 首条与既有 ARTICLE/Markdown 清理保持一致；编号还需标题主题及新段信号；案例不进入法条解析分支；表格块无结构化结果时法规拒绝、案例明确告警 | 命名/编号标题仍属启发式；法规页前说明单独保留，非空页缺块和正文/版面差异显式告警；OFF-QA-06～12 |
| CLI：安全与异常 | 草稿先解析再判无效长度，直接写固定文件可能覆盖输入或留下半写文件；rollback 异常可能阻止 close | 参数预检；拒绝目标与输入/配置相同；同目录原子替换、不跟随输出文件符号链接；rollback 的 finally 中关闭连接 | 三种输入、符号链接、只读连接及错误分支由 QA 独立复验；OFF-QA-13、14、17 |

不应变化的行为：原文不由 LLM 改写；无云调用/模型下载；既有审核门禁、解析结果格式、法条父子元数据兼容字段、
PostgreSQL Schema、数据库读写/发布的显式授权要求、历史 ACTIVE 指针与已有数据均保留。
片段数量、片段边界及本轮版本签名允许随优化发生变化，不应降低覆盖与来源要求。

## Fix 实际检查记录（不是 QA 验收）

| 检查 | 实际结果与范围 |
| --- | --- |
| Git/范围审查 | 开始时分支和 HEAD 与上述基线一致；暂存区为空，完整读过四份 diff、两份未跟踪源码及交接文档；没有发现本轮外修改 |
| 代码分支/兼容性 | 静态核对函数签名、正式审核和表格门禁、参数化 SELECT、无自动向量/发布入口、版本签名及来源转换；此结论不能替代回归 |
| 语法/导入 | 六份源码 AST 解析和相关模块导入完成；未加载 paddle/paddleocr，未安装依赖 |
| 轻量合成自检 | 空格条号、案例普通列表与主题标题、四类数值字段分界、无效参数及输入覆盖的提前拒绝、未结构化表格的法规门禁与案例告警完成；仅人工生成字符串和内存对象 |
| 首轮自检夹具说明 | 曾把多个新段放进单个版面块，导致标题断言失败；夹具修正为逐段独立块后复查，断言和业务规则未因此降低。该过程不是业务样本测试 |
| 差异/私密保护 | `git diff --check`、显式六文件清单与敏感模式检查完成；未纳入 Token、DSN、原文、模型、日志、环境或导出数据 |

轻量自检摘要仅在忽略目录 `local/offline-freeze-selfcheck/summary.json`。
本轮未执行 OFF-QA-01～17、真实 OCR/表格/法律专项、真实 BGE、数据库查询或写入、正式入库与完整自动化回归。
未接触真实测试集/真值、QA 工作区、运行容器、main；未 Push、部署或修改模型。

## 需要 QA 确认的实现边界

1. 法规复用既有 `parse_articles`，按编/章/节/条保留父文；子片段仍带条号，不跨条合并。
2. 案例按原文新段中的主题编号标题或已支持的命名标题分节；普通编号不单凭编号分节，正文内引用“第几条”不走法规切分分支。
3. 案例标题识别是启发式，不自动完成事实、证据、法律依据的实体抽取或真实性判断。
4. 案例表格单独保留原结构；法规含表格时当前预览拒绝，需独立适配和复核，不算已实现法规表格检索。
5. 页码、行号和可用 bbox 保留；长单元拆分后的来源精度为 `unit`，不是逐字符/逐片段精确坐标。
6. 标题和引导语长度限制仅作用于 Embedding 输入，父文和片段正文应保留；实际 BGE token 预算仍由既有校验负责。
7. 预览允许读取 `needs_review` 结果，但返回仍为 `requires_review=true`，不能作为通过审核或正式发布的证据。
8. `body_roundtrip_equal` 只比较解析后正文与子片段重组，忽略空白及人为重复的法条标签；不是原文件到 OCR 的逐字正确率。
9. 法规条前内容保存在 `unassigned_preface`；页眉、页脚、编号、注释等排除情况列入指标，须核对是否包含实质内容。
10. 案例目前是预览能力；法规的候选版本构建仍走既有 `ingest_legal_documents.py`，两者不能混称为已发布 RAG。
11. CASE_VERSION 与 CHUNKER_VERSION 分别参与对应预览修订，来源 bbox 也纳入预览摘要；不因无关案例规则变化而重新编号法规预览。
12. 对超过片段上限的单个受保护数值字段，当前选择明确拒绝；增加上限后仍需核对 BGE token 预算，不能删除文本来通过。
13. 预览使用文件标题，不自动推定法规正式名称、稳定法规身份或效力；正式构建仍需原有名称/身份与人工复核。
14. 表格单独保留不等于已生成表格向量；正文重组一致不等于 OCR、阅读顺序、跨页语义及标题启发式已获验收。
15. 现有工作台容器未更新到本轮离线优化 SHA；不能把现有页面或旧镜像的运行结果当成本轮代码的验收。

## QA 优化效果和回归验收清单

以下 `OFF-QA-*` 是建议的验收用例编号，不是已确认 Bug ID。QA 如复现失败，应另建正式 Bug 并记录真实证据。

| 编号 | 场景与步骤 | 预期及必须核对项 |
| --- | --- | --- |
| OFF-QA-01 | 短法规，多编/章/节，含“第几条之一” | 层级与条号准确，短条保持完整，不跨条，不丢顺序 |
| OFF-QA-02 | 长条文包含多款、多项、共同适用条件与末尾除外条款 | 每个子片段不超上限；父文完整；引导语、否定、但书和例外均可恢复，无错配 |
| OFF-QA-03 | 超长单句及金额、日期、百分比、文号临近分界 | 不丢字、不重复；记录不可避免的硬切风险，不能仅凭长度达标判语义合格 |
| OFF-QA-04 | 一条内大量短款项 | 合理组合而非每短行一个碎片；条内 fragment_index/fragment_total 连续、准确 |
| OFF-QA-05 | 同一法规重复预览、移动文件、调整上限 | 相同内容及配置的 ID/修订稳定；上限或内容改变后相应变化；父子引用一致 |
| OFF-QA-06 | 空格条号如“第 一 条”、Markdown 条号、条前说明 | 与既有条号解析兼容；不得异常退出或静默漏掉前置内容，重点核对首条定位逻辑 |
| OFF-QA-07 | 处罚决定书包含事实、证据、适用依据、决定及救济，内含法规引文 | 案例分节不冒充法条；引文留在原位置；标题识别结果人工核对 |
| OFF-QA-08 | 案例包含长标题、普通编号列表、引号内标题、无明确标题段落 | 不将普通正文大量误识别为章节；无标题正文不丢失；超出规则范围明确记录 |
| OFF-QA-09 | 跨页续段、多栏文本、空白页、缺少 layout_blocks 的非空页面 | 页序和段落衔接与原文件对照；缺来源/未覆盖正文页不得被误报为生产可用 |
| OFF-QA-10 | 页眉、页脚、注释、页码、图片说明 | 排除项可见；有法律解释或业务内容的注释不能无提示丢弃；保留原解析结果 |
| OFF-QA-11 | 含普通表格、横纵合并表格和跨页表格的法规/案例 | 案例表格独立保留跨度与来源；法规按当前边界拒绝，不摊平、不静默丢格 |
| OFF-QA-12 | failed、partial、空正文、重复条号、目录及越界参数 | 明确拒绝或告警，无伪造成功；原有异常文件保护不退化 |
| OFF-QA-13 | 三种 CLI 来源分别指向同一解析结果 | 分类、正文、来源及片段指标一致；读取已有结果时不重复 OCR 或访问云端 |
| OFF-QA-14 | 数据库来源、输出路径与凭据保护 | 仅参数化只读 SELECT；无 DDL/INSERT/DELETE/发布；输出限私密目录，无凭据/原文进入 Git 或公开日志 |
| OFF-QA-15 | 新旧切分版本对同一法规准备修订 | processing_signature、文档修订及相应片段正确区分；旧 ACTIVE 不被隐式替换 |
| OFF-QA-16 | 正式法律桥接回归 | 缺复核人、含表格、失败结果仍按旧规则拒绝；预览不生成虚假的审核记录 |
| OFF-QA-17 | 全部已有回归及原 QA 法律专项 | 失败保留并报告，不降低断言、不改人工真值；历史执行结果不冒充本轮结果 |

## QA 执行入口

以下为**供 QA 执行的正式验收命令模板，Fix 本轮未运行这些命令**。复用现有 Python 与离线模型，不安装依赖、不下载模型。
先完成冻结版本接收，记录实际源码目录、完整 SHA、工作区状态和模块导入位置。

### 优先复用已有解析结果

`$SourceRoot` 指向已接收冻结改动的 QA 源码目录，`$Python` 指向既有解释器，`$NormalizedJson` 指向私有解析结果。
从该源码目录执行，输出保存在该目录的 Git 忽略 `local/` 内：

```powershell
& $Python -B scripts/preview_offline_ingestion.py `
  --result $NormalizedJson --document-type law --max-chars 800 `
  --output local/offline-ingestion-qa/law

& $Python -B scripts/preview_offline_ingestion.py `
  --result $CaseNormalizedJson --document-type case --max-chars 800 `
  --output local/offline-ingestion-qa/case
```

若 QA 显式绑定只读 Fix 源码，请遵守该 CLI 的输出目录约束；不要通过写对方工作区或修改断言绕过。
可以先直接导入冻结源码的 `preview_chunks`，将返回值由 QA 测试辅助代码写入自己的忽略目录。

### 原文件与已有数据库记录

```powershell
# $OriginalFile 仅指向获准的原文件；访问真实测试集时使用 MARKET_REGULATION_TEST_CORPUS 与 pathlib.Path。
& $Python -B scripts/preview_offline_ingestion.py `
  --input $OriginalFile --document-type law `
  --output local/offline-ingestion-qa/source

# $PrivateConfig 是已批准的本地配置文件；不要把 DSN、密码或 Token 粘贴进命令。
& $Python -B scripts/preview_offline_ingestion.py `
  --parse-id $ParseId --config $PrivateConfig --document-type case `
  --output local/offline-ingestion-qa/database
```

既有解析记录位于 `document_review.documents.original_result`；正式检索片段位于另一条知识库链路。
不要将工作台“解析成功、正文已入库”直接当作“Chunk 已构建/向量已生成/知识库已发布”。

### 相关回归

```powershell
& $Python -B -m unittest tests.test_mvp tests.test_document_parsing tests.test_v021_final_acceptance_edges -v
```

QA 补充本清单对应的优化效果、长度与覆盖、版本失效和只读保护测试；不要求 QA 开发业务功能，不用历史执行替代本轮验收。
原来的 `tests/run_v021_final_acceptance.py` 可在固定 QA 工作区用于冻结 Fix 源码的完整回归，
必须传入干净 Fix 工作区的完整 HEAD，并核验它与源码 SHA 的差异仅为文档，不能使用旧基线冒充优化后结果。

```powershell
# 在固定 QA 工作区执行；变量只保存已知目录和提交号，不含凭据。
$FixRoot = (Resolve-Path ../market-regulation-platform-fix).Path
$SourceSha = '8ecff8866232ca33d0e350e6ead311fe8570aa89'
$HandoffSha = (& git -C $FixRoot rev-parse HEAD).Trim()
& git -C $FixRoot diff --name-only $SourceSha $HandoffSha
# 先确认输出只有本交接文档；有源码差异或未提交修改则停止并记录 BLOCKED。
& $Python -B tests/run_v021_final_acceptance.py `
  --source $FixRoot --source-sha $HandoffSha `
  --api-packages (Join-Path $FixRoot '.venv-api/Lib/site-packages') `
  --output local/offline-ingestion-qa/regression
```

对照时固定相同匿名样本、max_chars、模型和配置。优化前基线没有草稿预览入口：应比较其已有 `parse_articles`/
`split_articles` 与优化后对应输出，不把基线入口不存在记作优化后回归失败，也不修改基线以凑齐命令。
基线可从 Git 已提交内容只读提取到 QA 忽略目录，记录来源 SHA 和实际导入模块；不得 reset、覆盖 Fix 或原工作区。
本清单不授权数据库迁移、发布、回滚、重建容器、真实云端调用或上传真实测试集。

## 结果与回传要求

- 每项记录：受测完整 SHA、匿名样本 ID、实际命令、退出码、实际/预期、证据位置和 PASS/FAIL/BLOCKED。
- OCR 质量与切分质量分别记录；有真值时对照正文、数字、条号、表格和阅读顺序，无真值不宣称准确率。
- 每份预览保存 `chunk-preview.json`；重点核对 `chunks`、`parents`、`tables`、`unassigned_preface`、`quality` 和 `warnings`。
- 原路径、原文件名、正文、坐标、输出 JSON 和数据库配置仅在忽略目录；报告使用匿名标识，不修改原文件或真值。
- 总体结论由 QA 独立给出；发现失败后交回 Bug ID、最小复现和正式测试提交，Fix 再针对性修改。
- 用户最新职责界定：Fix 完成代码优化、静态与必要轻量检查和冻结交接；独立测试、真实样本验证、性能对照和最终验收由 QA 完成。
- 六份源码已冻结；文档传输提交完成后须再次确认工作区干净、且相对源码提交只有文档差异，再正式接收。
- 本文件的 READY_FOR_QA 仅表示可绑定版本开始测试，不改变此前 QA 闸门，不宣称优化效果或生产验收通过。
