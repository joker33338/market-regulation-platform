# v0.2.1 修复记录（按交接批次保留）

## 提交与交接

- 原源码基线：`5ed1ba6339dc817f53747c0db7cbcbde3224dd3b`。
- 已读取 QA 正式交接：`bc0219e9e723f91f38c3f04c3b513a6ee45b6437`。
- QA 红测提交：`4022606420695a22579a82b3ce8e4c03448ca4ac`，四项为两失败、两通过控制。
- 本轮受测代码提交：`6216ae5f40727871b369dfc8c54868ac748c4648`。
- 本报告及结构化交接的传输 SHA 由 Git 在提交后提供，不自引用。

## Q021-001：增强失败丢弃原生正文（P1）

根因：纯合成双栏 PDF 已先完成原生提取，再进入 Structure 增强；异常分支只追加空失败页。
修复限定为本页确有非空 Native 候选的路径，保留原生正文、版面块、表格、PDF 坐标和原始结果。
返回页明确为 `native_pdf` / `needs_review`，保存增强尝试方法、异常类型和安全错误信息，附中文复核警告。
质量评估新增 `layout_enhancement_failed` 复核及回退原因，不把保留正文默认为干净成功。

没有改变多栏默认增强策略。扫描、强制 OCR/Structure、无可用原生候选仍按既有失败行为处理。
候选在每页重置，不能把上一页文字带到下一页。成功的 Structure 结果不走兜底。
未改客户端、外传授权、结果不可变语义或法律人工复核。

## Q021-002：CLI 默认值覆盖显式表格配置（P2）

根因：`--tables` 未指定时为 False，脚本以该值覆盖 `ParsingConfig.from_env()` 的显式启用。
修复为未指定选项时继承进程配置，显式 `--tables` 才启用；基准报告的 `tables` 取实际生效配置。
未设置环境且无选项时仍关闭，不增加新选项，不改全局默认、服务环境或资源限制。

## 真实执行的定向测试

| 执行 | 数量 | 通过 | 失败/跳过 |
| --- | ---: | ---: | ---: |
| Windows：QA 两缺陷用例、配置控制和新增隔离控制 | 7 | 7 | 0/0 |
| 已有镜像：上述7项及受影响解析、历史回归、任务实现和双引擎策略 | 71 | 71 | 0/0 |

第二行已包含第一行的方法，不能相加声称78个唯一方法。
容器断网、非root、只读源码、禁额外权限；只复用既有依赖，没有安装、下载、真实模型或数据库操作。
测试在代码提交前同一修复树执行，随后仅提交对应三份实现和三份回归文件。

```text
python -B -m unittest tests.test_v021_native_preservation tests.test_v021_table_cli tests.test_v021_fix_edges -v
python -B -m unittest tests.test_v021_native_preservation tests.test_v021_table_cli tests.test_v021_fix_edges tests.test_document_parsing tests.test_round01_regressions tests.test_mineru_implementation tests.test_dual_engine_policy -v
```

## 仍保留的质量边界

本次没有修改原始标注、九处标签差异、图像像素限制或默认表格开关。
真实 CER 与人工结构真值不足仍是质量证据限制；本次修复不宣称已解决全部专项质量问题或批准合并 main。
后续 QA 只需对精确代码 SHA 复验失败用例与受影响测试；无须因这两项改动重跑149项、模型或数据库。

## 2026-11-10 最终 QA 问题修复：QFA-001～004

本节为最新批次，以上为历史批次记录。最新 QA 已交付扩展真值且真实本地模型可测，不能沿用历史的真值不足或模型阻塞结论。
本次仅修复四项已确认 P2，未修改 QA 的最终 BLOCKED 闸门。

- QA 测试 SHA：`78b7e05e747656414badd8350c83d48b672ecc16`。
- QA 报告 SHA：`0881807ee0524503c54b0f08fcca96c922f9828e`，核验其 `final-handoff-to-fix.md/json`、`final-acceptance-report.md` 与 `version-gate.json`。
- 修复基线：`a860abfa84bc2664bb119ae8f5b80c6794e6e23c`。
- 安全接收测试的本地 SHA：`509f823ae8217855e3a4ea6ed1b98cfdd62f0fac`；没有导入 QA 的旧依赖或用其目录覆盖 Fix。
- 冻结受测代码 SHA：`73c9f10a04b2d375b2aec542b29e9ef9a1112a4e`；完整回归开始/结束均为此 SHA 且工作区干净。
- 报告传输提交号由提交后的正式交接提供，避免文件自引用。

| ID | 根因与修改位置 | 修复与回归 | 修复提交 |
| --- | --- | --- | --- |
| QFA-001 | document_router.py：DocumentParser.parse 聚合仅处理页面异常，整文无正文仍 success | 仅对全篇无正文/表格文字的成功 PDF 提升为 needs_review；保留 empty_page、页来源和复核信息。混合空白页仍成功且不加载 OCR | `708002475d942b21288e84971ece094cc00b1caa` |
| QFA-003 | document_router.py：_parse_pdf 将 fitz.open 成功当作 PDF 内容已验证 | 增加 is_pdf 检查，PNG 伪装 PDF 在 auto/ocr/structure 均先拒绝；正常图片入口保留 | `708002475d942b21288e84971ece094cc00b1caa` |
| QFA-002 | native.py：docx_document 仅输出 colspan，未追踪 vMerge | 复用 table_from_html；新增 _docx_table_html 按相邻行、列位置与跨度连接锚点，延续格不重复输出。保留原 XML、异常/非空延续格文字和告警，限制新增列跨度计算。覆盖横纵混合、终止/重启、孤立延续及多表隔离 | `5df48af877265213d58566af28e5b2bb47b08cf0` |
| QFA-004 | start_agent_workspace.ps1 仅接受旧 round1 分支 | 每个角色允许旧分支与当前固定分支；隔离执行实际脚本，验证两个角色和错误/未知分支，Git 与交互入口均用替身，不启动真实会话 | `73c9f10a04b2d375b2aec542b29e9ef9a1112a4e` |

### 实际验证

修复前三项 QA 最小测试均断言失败，与 QA 一致；旧启动脚本实际退出 1 并拒绝当前 Fix 分支。
初次本地尝试因受限临时目录权限未能执行断言，该日志单独保留，不计作业务复现；在获准的既有环境中重跑后得到上述三项断言失败。

| 验证 | 本次结果 | 边界 |
| --- | --- | --- |
| 受影响定向回归 | 49/49 PASS，0 SKIP | 已包含 QA 三项失败及新增边界；不与完整回归相加 |
| QA/Fix 测试并集完整回归 | 243 个唯一方法：237 PASS、0 FAIL/ERROR、6 SKIP | 模块来源全部绑定 Fix；同名旧测试仅归一化换行后核验相同；保留 QA 独有测试 |
| S00016 表 0 只读参考对照 | 257 个锚点、32 个 rowspan>1；跨度和 257 格文字全部一致 | 第二张表继续保留，共两表；不把两张输出表直接与单表参考作表数匹配 |
| S00022 / S00025 | REJECTED / needs_review | 三个原样本 SHA-256 均未变化；未运行模型或云端 |
| PowerShell 语法与 Git 差异检查 | 通过 | 不代表整机重启或生产部署验收 |

完整回归复用 QA 提供的 `run_v021_final_acceptance.py`，只在忽略目录生成执行副本：
显式绑定 QA 测试目录，将证据输出约束改为 Fix/local，并使用独立 ASCII 临时缓存名。
没有修改测试断言、待测模块、SHA/干净工作区检查及方法计数逻辑。
原始记录在忽略目录 `local/v021-qfa-fix/`：`reproduce-confirmed.log`、`guard-before.log`、`targeted.log`、
`full.log`、`full/suite-result.json`、`sample-verification.json`；真实文件名、路径、正文与参考不进入 Git。

定向命令（使用已有项目 Python 和 API 包目录）：

```text
python -B -m unittest tests.test_v021_final_acceptance_edges tests.test_v021_qfa_pdf tests.test_v021_qfa_docx tests.test_v021_agent_launcher tests.test_document_parsing tests.test_v021_native_preservation tests.test_v021_fix_edges -v
```

独立 QA 完整回归命令见 `handoff-to-qa.md`，必须绑定新的冻结 SHA；禁止将脏树标成历史提交结果。

### 剩余风险与复测范围

六项跳过均为 PostgreSQL 测试：五项需要明确的现有测试 Schema 连接，一项需要独立 DDL/生命周期清理授权。
本次未写数据库；QA 在旧 SHA 的 5/5 PASS 仅作历史证据，未并入本次通过数。数据库结果字段/Schema/持久化逻辑未修改。

请 QA 独立复验四项、原样本表 0 与合法第二表、混合空白页、扫描/文字/混合 PDF、正常图片及加密/损坏负例。
合成模型结果不外推真实 OCR 准确率；本次没有新的真实 OCR、BGE、云端或完整 PostgreSQL 链路结论。
不修改现有持久入口；运行服务仍可能是历史快照，不能以当前页面可用宣称本提交已部署。
质量阈值、三栏/auto 表格质量观测、过期云授权和既有预算、整机重启、数据库生命周期及 S00019 意图冲突，均维持最新 QA 的未决状态。
未 Push、合并 main、部署、改动原/QA 工作区、安装依赖或修改语料、模型、真值与云账本。

## 2026-11-10 用户追加：服务验证与本地 Docker 整理

此项在上述四项 Bug 完成后由用户另行授权：使用其 Docker PostgreSQL，检查已提供的 MinerU API，补齐持久入口，
清理旧容器/镜像，统一一个项目；用户随后明确要求保留 MySQL、Redis。这里是本地部署，不是生产发布。

- 部署代码提交：`a8f7031bfd3bdc6cc7df5f9adb190a75eee8a968`。
- 项目/8180 入口整合：`e29ac56b1f55cca8af64f1638e0d6a0d59ffdded`。
- 实际迁移中发现并修复启动脚本将数据库镜像误判为旧 app：`8e80f73`，已用实际统一项目启动验证。
- 修改/新增 `compose.local.yaml`、`deploy/local/`、`scripts/local-workbench.ps1`、`tests/test_local_workbench_config.py`；业务解析源码未再变化。
- 最终仅 `market-regulation` 一个项目，app/db/mysql/redis 四容器健康；入口 `http://127.0.0.1:8180`。

| 实际执行 | 结果 |
| --- | --- |
| 用户数据库只读连接、解析表与 pgvector | 通过；应用配置目标与用户提供地址一致 |
| 官方客户端 GET 一个历史已完成批次 | HTTP 200、code=0、关联匹配、1 done；1 次 GET，0 新任务、0 上传 |
| 新增部署后的完整方法并集，冻结于 a8f7031 完整 SHA | 245 个唯一方法，239 PASS、0 FAIL/ERROR、6 PostgreSQL SKIP |
| 部署配置安全测试 | 2/2 PASS，已含在245项内；合并项目后再定向通过，不另加总 |
| 实际本机 HTTP：认证、合成 PDF 上传/任务/结果、PostgreSQL 与幂等 | 通过；仅新增1份合成记录（2页），原8份仍保留 |
| 容器 restart 与跨项目迁移后的任务/结果和数据库记录 | 通过；单条合成记录未重复，当前数据库9份 |
| 新镜像非root实际 PaddleOCR | 合成图片识别24字，success，requires_review=true，离线拦截4次；无新数据库写入 |
| PowerShell 语法、现有数据容器保留 | 通过 |

完整回归记录 `full-with-deploy/suite-result.json` 的受测 SHA 是 a8f7031 完整 SHA，开始/结束干净。
其后仅改 Compose 项目/端口、prepare 默认端口和 app 镜像保护检查；已用真实启动与持久任务读取验证，未重复整套耗时模型测试。
最初合成 HTTP 辅助脚本误用 upload_id 字段，在创建任务前失败；已按实际 file_id/file_ids 契约修正，未修改接口或测试断言。
当前容器复用原依赖，镜像 API 依赖版本与宿主测试环境不同，已明确记录在部署说明，不宣称镜像全套独立 QA 已通过。

本次按新授权进行了一次本地合成结果提交，不再适用上一批次“未写数据库”的范围表述；仍未执行 DDL、DELETE 或生产迁移。
清理13个旧实例，保留全部卷（含3个历史QA库卷）、证据、模型与批次账本；清理5份旧QA/候选镜像及2个重复标签，保留重建所需镜像。
新入口以同一 state 目录保持数据，旧8181入口撤销。正式中文部署说明为 `deploy/local/README.md`。
真实云解析/恢复、质量阈值、整机重启与完整 PostgreSQL 生命周期的 QA 未决项不因本次连接成功而变为 PASS。
