# v0.2.1 最终收尾 Fix 交接

日期：2026-11-10。Fix 交付状态：**READY_FOR_QA**。这表示工程准备可接收，不表示整体 v0.2.1 PASS；整体门禁仍由独立 QA 签发。本轮没有替换活动服务、执行生产部署、Push、合并 main 或更新 QA 的 version-gate.json。

## 1. 冻结版本和既有证据

| 项目 | 完整身份 |
| --- | --- |
| 开发分支 | `codex/fix-v0.2.1` |
| 本轮开始时 Fix HEAD | `967cff1e6eec0277b5103182b47098720367c228` |
| 上轮离线业务源码 | `8ecff8866232ca33d0e350e6ead311fe8570aa89` |
| 本轮业务源码／编写本交接时 Fix HEAD | `bf66e10753757c2e1f92383755817dd8c31ab336` |
| 上述提交 qa_core Git tree | `3f945a663099c9700bed8b4590823a1dc8b00557` |
| 正式 QA 收尾交接 | `4ca70b83367399c1f4fd87fec42f3691928caac4` |
| 离线专项 QA 报告 | `51b7413ca191025b789cae77160ceda7872f9248` |
| 离线 QA 测试 | `553c8562eee40d06aa0ae0281f916535892a42d0` |
| PostgreSQL QA 测试 | `83ee78cb5dd0b5e5640fc5523bf9efd752ad8791` |

本交接单独提交，最终文档提交 SHA 通过 `git log -1 --format=%H -- docs/qa/v0.2.1/release-closure-fix-handoff.md` 获取，并在会话交付。不能把文档自身的未来 SHA 预写为已知值。若之后仅增加文档，镜像仍绑定上述业务源码提交，不因文档提交重建。

沿用 QA 已验证的 **267 个唯一方法 PASS（包含 PostgreSQL 六项补测）**、QFA-001～004、S00016 DOCX 表 0 的 257 格与 32 个纵向合并、两张原表保留、真实 BGE 6×1024 等证据。不重做或重复累计。它们属于旧源码／旧宿主环境的有效证据，不能直接宣称本轮新源码和候选镜像也已获 QA PASS。

QA 离线证据索引为其忽略目录 `local/offline-ingestion-qa/evidence-manifest.json`，摘要 `29b0040288f8abbbb34159aa247d6fd87bf54e2b13ec852ece6d5fe7a2cb8dc6`。原始资料、模型、人工真值及历史账本均保留。

## 2. CLOSE 状态

| 项目 | Fix 已完成 | 待 QA 独立裁决 |
| --- | --- | --- |
| CLOSE-01 | 独立候选镜像构建；源码摘要、依赖、模型与当前挂载盘点；切换／回滚方案 | 候选镜像中的接口、权限、解析、持久化及受影响回归；当前服务尚未切换 |
| CLOSE-02 | 核对原批次、账本和既有远端任务；给出 GET 恢复入口及真实 auto 入口，auto CLI 支持显式原账本 | 真实旧任务恢复、真实 auto 和当前源码的云结果质量；本轮 Fix 未进行真实 HTTP |
| CLOSE-03 | 已完成归因；最小修复 SAFE-001、ROUTE-001、REVIEW-001；55 项受影响自测通过 | 真实 Structure 的无线表格复测、原大图安全裁决、当前预测质量与路由合格率 |
| CLOSE-04 | 已提供持久状态清单及重启前后步骤 | **NOT_TESTED**：用户未安排 Windows 整机重启，容器恢复记录不替代整机验证 |

用户在本轮追加明确许可：“MinerUapi随便调用，不需要授权”。QA 可据此开展必要的 MinerU 验证，**无需再次向用户申请每次调用许可**。许可不等于必须移除服务端安全机制：仍保留 SHA 绑定、调用计数、原任务防重复提交、敏感控制及 SAFE_REJECT。旧机器清单的时间戳已过期；QA 应根据本次许可在自己的执行配置中同步有效时间并记录变更，沿用原 owner、批次、范围和唯一账本，不通过清账或换批次重置预算。本轮未修改 QA 私有配置或旧清单。

## 3. 候选镜像、运行实例和依赖

| 身份 | 值 |
| --- | --- |
| 候选标签 | `market-regulation-workbench:candidate-v021-bf66e1075375` |
| Docker inspect 候选镜像 ID | `sha256:ff555f5d00330c199ae5933b97b6a9fc6fa125d9710109f7fcf2213e5ac5f342` |
| 候选 OCI revision | `bf66e10753757c2e1f92383755817dd8c31ab336` |
| 复用基础镜像 | `market-regulation-app:local` |
| 基础镜像 ID | `sha256:b4010953b65e06c2d1000fdcd129f6fcceeed9b9a5d48a12266d3365a610a2b1` |
| 当前活动镜像（保留） | `market-regulation-workbench:local-4ecd995cb4be8ee4` |
| 当前活动镜像 ID | `sha256:04392161ca0e4acc37530679fbb11564e8341389a76aa475469d0bbeafa74af6` |
| 当前活动 OCI revision | `350f5ad3d8d0859e6dbbb2a879367e901913b556` |

Fix 在无网络、无业务状态／凭据挂载的一次性容器中读取候选文件和包元数据；57 个核心源码、HTML、SQL、脚本与启动入口文件的规范化换行 SHA256 全部一致，核心目录多余文件为 0。模型仅以只读方式检查目录存在，未加载模型或下载权重。这属于构建身份检查，不是候选运行集成验收。

| 依赖 | 宿主既有 QA/API 环境 | 候选镜像实读 |
| --- | --- | --- |
| FastAPI / uvicorn | 0.115.12 / 0.34.2 | **0.162.0 / 0.54.0** |
| PyMuPDF / httpx | 1.26.7 / 0.28.1 | 1.26.7 / 0.28.1 |
| PaddlePaddle / PaddleOCR / PaddleX | 3.2.2 / 3.3.2 / 3.3.10 | 3.2.2 / 3.3.2 / 3.3.10 |
| sentence-transformers / torch | 4.1.0 / 2.7.1+cpu | 4.1.0 / 2.7.1+cpu |
| transformers / tokenizers | 4.57.6 / 0.22.2 | 4.57.6 / 0.22.2 |
| psycopg2-binary / numpy / pillow | 2.9.13 / 2.5.4 / 13.0.0 | 2.9.13 / 2.5.4 / 13.0.0 |

候选 Python 为 3.12.16。`requirements.txt` 保留既有固定版本，FastAPI/uvicorn 的声明值仍为宿主列；本轮未安装、升级或假称基础镜像与 requirements 全量一致。Dockerfile 复用现有基础层，仅叠加源码。基础镜像依赖差异由 QA 在镜像中验证，不以宿主 267 PASS 代替。

本轮补齐 Dockerfile、专用 dockerignore 和 prepare.py 的构建摘要输入：已有 `preview_offline_ingestion.py` 与 `run_test_batch.py` 现在也进入候选镜像，避免源码有入口而容器内缺失。未改数据库 Schema、API 响应字段、Embedding 或法律切分实现。

## 4. 模型、状态及无损切换

当前仅保留一个 `market-regulation` 项目，app、PostgreSQL、MySQL、Redis 四个既有容器均 running/healthy；MySQL、Redis 按用户要求保留。

| 容器内位置 | 当前挂载／要求 |
| --- | --- |
| `/models` | 原模型目录，bind，只读；`ocr` 和 `bge-m3/config.json` 均存在 |
| `/private/runtime.json` | `local/docker-workbench/runtime.json`，bind，只读；含访问码、数据库连接及 API Key，不打印内容 |
| `/state` | `local/docker-workbench/state`，bind，可写；保留任务 SQLite、上传、解析工件及已有合成云探针状态 |
| `/app/reports` | 同一 state 下 logs 目录，bind，可写 |
| PostgreSQL `/var/lib/postgresql/data` | 原命名数据卷，原样保留，不迁移、不删除 |

OCR 配置使用 PP-OCRv5_mobile_det、PP-OCRv5_mobile_rec、PP-DocLayout-M，以及开启表格时的 PP-LCNet_x1_0_table_cls、SLANeXt_wired、SLANet_plus、RT-DETR-L_wired_table_cell_det、RT-DETR-L_wireless_table_cell_det。已有 BGE-M3 目录继续只读使用；本轮不重新安装模型。

固定入口仍为 `http://127.0.0.1:8180`；宿主 PostgreSQL `127.0.0.1:15432/market_regulation`，容器经既有网络使用 `db:5432`，是同一个库。应用 user 65534:65534、只读根文件系统、restart unless-stopped。只读模型和只读私密文件不属于可写任务目录。

无损切换方案（尚未执行）：

1. 先在隔离候选环境完成 QA；使用新的 QA state 和日志目录，不把活动 `/state` 可写挂给第二个进程，不对旧队列自动启动 worker。
2. 安排本地切换窗口，暂停接收新上传，确认任务无运行中的上传／解析／数据库事务。记录任务计数、状态及原工件摘要；SQLite 使用一致性备份，不能只复制活动主库而漏 WAL。
3. 仅停止 app。保留原私密配置、访问码、授权与调用账本、state、日志、模型、网络、全部数据库容器和卷。禁止 `down -v`、prune、remove-orphans。
4. 在私有 Compose 环境中将 `LOCAL_APP_IMAGE` 明确指定为上面的已验候选标签，其余挂载和端口保持相同；用现有 compose.local.yaml 仅启动 app。不要直接调用会重算 deployment.json 的准备脚本来代替这个精确候选选择。
5. 校验实际镜像 ID/revision、健康、原任务和 `document_review` 结果可读、幂等及鉴权。此次业务修改不需要数据库迁移。
6. 失败时仅停止候选 app，选择上表保留的旧标签并挂回同一原 state；确认没有双 worker。不得删除新旧工件来掩盖失败。若发生新旧版本工件摘要冲突，保留双方结果供 QA 裁决，不能覆盖已确认结果。

本轮没有改 deployment.json 或 runtime.json。其内容摘要保存在私有 `image-inventory.json`，切换时先比对，不能把旧配置悄悄更新成候选已上线。

## 5. 确定性缺陷与最小修复

以下是本次复现后分配的 Fix 收尾编号，不冒充 QA 原有正式缺陷编号。首次修复与工程准备提交为 `5f52a7241484a843573a8ffc749afb17d51124f3`；SAFE-001 的缓存路径跟进为 `bf66e10753757c2e1f92383755817dd8c31ab336`，后者是包含全部修复的最终业务基线。

| 编号 | 复现／根因 | 修改文件和函数 | 结果及限制 |
| --- | --- | --- | --- |
| SAFE-001 | 10×10 合成 PNG、像素上限 50、有效 Mock 云授权；原本一般异常回退产生 1 POST、5 次 Mock HTTP，并完成云候选。资源拒绝与 OCR 质量失败未区分 | config.py 新增 ParsingSafetyError/validate_image_safety；DocumentParser 的文件、图片、PDF 页数及 parse_batch 安全错误；DualEngineRouter.parse/_remote；MinerUService._local | auto/remote 拒绝超限图片，不调用模型或 HTTP；旧缓存候选恢复前也复验当前文件；保留失败候选、SAFE_REJECT 机器码并阻止失败结果写入 sink。正常 OCR 失败仍可按规则回退。未放宽任何限额 |
| ROUTE-001 | S00008 开启 enable_tables 后仍 native_pdf、0 表、无 Structure 调用；默认 PDF find_tables 只识别框线，原生正文提前返回 | document_router.py：has_text_table_hint、DocumentParser._parse_pdf | 仅在开启表格能力、原生未提取表时，使用文字对齐检测的多行多列及数字行线索进入已有 Structure；同一真实文件现在触发一次 Mock Structure。普通 PDF、关闭表格能力均保留原生优先；增强失败仍保留原生候选并复核。真实新表格准确率待 QA |
| REVIEW-001 | 合成重复条号文本、历史原生表格均出现 quality.review_required=true，而顶层 requires_review=false | document_router.py：DocumentParser.parse | 顶层合并既有质量复核信号，不更改原文、阈值、条号、发布授权或自动判定法律准确率 |

新增测试为 `tests/test_release_safety.py`（4 方法）和 `tests/test_release_routing.py`（4 方法）。首次修复连同已有文档解析、双引擎策略和本地配置共 **55 方法 PASS，3.533 秒**。随后又复现旧缓存 auto 在当前超限时仍 completed（零 HTTP），对读缓存后的安全校验做了跟进；最终源码仅重跑受影响的安全与双引擎策略 **18 方法 PASS，2.724 秒**，缓存检查覆盖 auto/local/remote，保留原 checkpoint 内容。18 是前述 55 的重叠子集，不能相加成 73；其余源码及测试不变。这些都是 Fix 自测，8 个新方法已包含在 55 内，不与历史 267 合成一个“最终通过数”。没有真实 HTTP、数据库、模型推理或性能测试。

## 6. CLOSE-03 质量归因

### 三栏 LAYOUT-01 / S00011

绑定历史预测源码 `a860abfa84bc2664bb119ae8f5b80c6794e6e23c` 与原任务指定的同页人工全文参考；属于复用历史预测的离线归因，不是本轮当前 SHA 的新 OCR。

- 参考 1857 字符、预测 1793，编辑距离 1664，CER **89.6069%**；统一换行后计算。
- 去除空白的诊断 CER 仍 **91.3934%**，所以仅改变换行／空格不能解决；这不是替代正式 CER 的新口径。
- 去空白字符多重集合相较参考缺 3、多 2，显示大量字符虽存在而顺序不合。多重集合不能定位具体漏段或重复段，不能当作字符准确率或证明没有 OCR 错字。
- 原始 PP-Structure 只有 **1 个文本块**；适配器按 block_order 输出的文本与原模型内容一致。没有证据支持适配器跨块排序错误；证据更支持模型块内阅读顺序问题。未硬编码“三栏”重排、未改真值或补写法律正文。
- 输入页和参考沿用 QA 固定任务映射；没有发现样本串号证据。但关键语义段落关系未独立标注的部分继续 **NOT_LABELED**，不能用相似字符集合代替语义核验。
- 不符合复杂文档 CER≤5%。已有 requires_review 和 quality.review_required 均 true；保留原始模型 JSON／候选，继续人工复核。具体法律条件／例外的完整准确率无法由现有字符诊断断言。

### 无线表格 S00008 与有框线对照 S00007

范围仅 **2 页、2 张人工参考表、78 个锚点单元格**：S00008 48 格、S00007 30 格。历史强制 Structure 各自位置、跨度及文本精确；不外推所有文件。

S00008 原生 347 字、默认表检测 0、文字对齐检测 1；代码提前返回导致 Structure 未运行，按 ROUTE-001 修复。修后同原件只读复现为 method=structure、Mock 模型调用一次、text_table_hint=true、requires_review=true，原件 SHA 不变。此证据验证调用路径，不把 Mock 内容冒充真实 48 格已通过。QA 需以当前冻结源码、原模型、同参考重新核验。

S00007 原生检测为 1 张表，但原生 cells 不完全等于人工参考；强制 Structure 历史精确。这个事实不证明所有有框线原生提取都应强制 OCR。本轮保留原生优先并通过 REVIEW-001 纠正复核标记，不改写表格、不把启发式当作 98% 质量证明。尚未满足自动候选资格的结果仍需复核。

### 历史 MinerU S00007 第 4 页表

来源为原 7 页官方任务的历史 normalized.json，SHA256 `fe958f34a3cf281f6eea5b894ff50c8fdebc9a219bce9684a75f63c2c1c2cbed`。保存 HTML 为 715 字符／943 UTF-8 字节，SHA256 `17659b68eae2a494b90ea1bf8bdf1b2e9b88be71a8fc564e338865ac286cbaad`。本轮离线解析这个有界 HTML，不调用官方 API，不在业务规范化中展开不可信远端跨度。

同一已审参考有 14 行、4 列、30 个锚点：行列与位置、rowspan、colspan 完全一致；结构整表匹配 **1/1**，文本严格一致 **25/30=83.33%**，结构及全部文本同时一致 **0/1**。normalized.cells=0 是原安全策略，HTML 完整保留，不能算官方识别率 0%。

5 个差异（零基坐标）如下；跨度及数字序列均相同：

| 锚点 | 跨度 rowspan×colspan | 文本差异归因 |
| --- | --- | --- |
| (0,0)、(4,0)、(7,0)、(11,0) | 各 1×4 | 全角左右括号变为半角括号 |
| (12,1) | 1×3 | 全角左右括号及冒号变为半角 |

5 格 NFKC 后均一致，但本轮**不据此降低严格断言、自动规范化覆盖原文或宣称 30/30 PASS**。未发现这 5 格数字变化或字段跨度错配；全页法律字段正确率、Markdown 语义和全文 CER 尚未完成相应标注评估，仍 NOT_LABELED／未测。不符合本轮严格单元格文本≥98% 线；已有 requires_review=true 和 table_alignment_review，路由保留本地候选。归因为历史云端标点格式差异，无已证实需改写客户端的 Bug；当前源码云端结果须 QA 另测。

## 7. 正式质量标准与 S00019 独立意图裁决

以下是用户本轮给定的业务接受线，不是代码启发式能自动测出的指标。每次统计必须附有效样本数、人工参考覆盖和未标注范围。

| 维度 | 接受条件 |
| --- | --- |
| 人工全文 CER | 文字 PDF≤1%；常规扫描≤3%；复杂扫描／多栏≤5%。无人工参考为 NOT_LABELED，不能用置信度或其他模型代替 |
| 法律关键内容 | 已标注的法规名称、条号、金额、日期、处罚依据、否定／但书／例外、决定与救济等，自动候选必须 100% 正确；错漏或逻辑倒置均 REVIEW_REQUIRED |
| 表格 | 参考覆盖内单元格文本≥98%、结构≥98%；分别核验行列数、锚点位置、rowspan、colspan、文本及关键字段关系；重要合并／对应／数值错误不能自动通过 |
| 阅读顺序 | 已标注关键段落顺序 100%，标题正文、适用条件和处罚条款不能错位；全文仍适用相应 CER 线 |
| 路由 | 人工审核意图下合格决策≥95%；分开统计 SAFE_REJECT、原生／本地、复杂结构、授权质量回退及人工复核，不以云调用比例代替 |
| 后续入库 | 合格质量、完整来源与原有人工审核／发布授权同时满足。解析库留存不等于正式 RAG 发布；不合格结果保留候选、来源并复核，不静默自动发布 |

**独立安全意图记录（不修改原始人工标签）：**

| 样本 | 本版本最终预期 | QA 裁决要求 |
| --- | --- | --- |
| S00019 | **SAFE_REJECT** | 超出现有资源限制时明确失败及拒绝码、可审计、原件不变、无模型／云提交、无伪成功、无可入库的不完整正文；不再要求超限后 Paddle 成功 |

保持原像素／内存资源限制，不新增超限图片缩放后识别，不通过云回退绕过。现有对限额内图片的常规处理不构成对超限的豁免。8 个新测试中的安全测试只使用 100 像素合成图和更小测试限额，真实 S00019 由 QA 按原限额复判 R-08；不重写历史标签来清除原始矛盾记录。

## 8. CLOSE-02 既有任务恢复和真实 auto 入口

### 原批次状态及请求预算

只读核验原清单 19 SHA；首批仍 S00014、S00007、S00010，共 13 页；owner／batch_id／选定 SHA 与 canonical 注册一致。原 manifest 的机器期限为 2026-11-09 10:42:13 UTC，现已过期。用户本轮新许可已记录于第 2 节；不是 API Token 失效结论，也不要求再询问用户是否允许调用。

canonical 账本仍 **12/32 预留、3/3 唯一 SHA，POST=3、GET=7、PUT=2**；SHA256 `cd79653bd1401e6f3048d8487932592134ca5c662cb7e5e7f4916f877bcd9c91`。原清单摘要 `4024d35a311083664e786da4b1d191b758f34db337095797cd5481f20ed26d50`，注册摘要 `08b699432a106f8f06ff53cfb610c8ab7696f4ed614f72c445e681d8e16b3e5f`。具体任务 ID、SHA 映射、真实路径和 Token 留在 QA 原忽略证据；不复制进跟踪文档。

- S00007：旧 child 已 completed、uploaded=true、结果在本地，parent 调用 5；优先复用已有结果，不重新 POST。
- S00010：旧 child timed_out、已有 remote_id、uploaded=true、未下载结果；parent 调用 6。可在**最多 2 次剩余请求**内尝试一次状态 GET 和一次结果 GET；重定向也计数。若没完成则停止，不能超过原每文件 8 次预算。
- S00014：parent／child 已保留失败和 POST 占位，remote_id 不存在。维持 FAILED_NO_ORIGIN_HTTP，不通过重新提交“恢复”。

### A. GET-only 恢复入口（由 QA 在自己的原状态副本／执行窗口运行）

复用 `OfficialMinerUClient.bind/detail/download` 以及 `MinerUService.resume/run/_download`，不新增客户端。恢复对象是 S00010 **原 cloud child**，不是重新 submit 一个父任务。先以 SQLite 只读查询父／子 payload，核对 parent.routing_state.child_task_id、remote_task_id 与 child.remote_id、文件 remote_id、source_sha256、源文件现 SHA 和注册范围全部一致；不把父任务 completed 当作云 child 已完成。

最小真实操作清单：

1. 按本次用户许可记录当前执行时间、保留原身份的有效清单及变更摘要；挂载同一个原 canonical 账本和原任务仓库。网络准入重新检查，不假设历史 QA gateway 仍在运行。
2. 构造既有客户端，绑定原 child。`before_request` 同时调用现有 TrustedTestBatch.authorize/reserve_request，每次 HTTP 前复验 SHA、当前期限、原总预算和 parent.routing_state.calls。
3. 此恢复入口的 hook **只准 GET**，POST／PUT／DELETE 在发送前直接拒绝；原父 calls 从 6 起累计并持久保存，先预留再请求，不能因为超时回滚计数。配置 max_polls=1、max_upload_retries=0、max_download_retries=0、连接超时 5 秒、请求超时 30 秒；没有等待上传的豁免。
4. `await service.resume(old_child_id, owner)`，然后 `await service.run(old_child_id)`。原 remote_id 必须已存在；若状态是 waiting-file，PUT 被 hook 拒绝，停止而非重传。
5. completed 时复用现有下载、压缩包安全检查、normalize_artifacts 和 SHA 关联。先将候选保存在隔离结果目录，审查两候选、来源、复核标记与当前质量线；不自动覆盖已确认法律文本或发布到 RAG。
6. 账本预留、真实返回、超时和不可判定的源站到达情况分别记录；无结果记未完成，不能伪造成功。重复执行前先读原仓库与账本，已下载结果直接复用，不再发送请求。

这里交付的是现有 SDK／Service 的精确恢复调用方案，**没有声称旧 QA 批处理 runner 可以直接完成恢复**。其 `select_unreserved_rows` 会拒绝已预留 POST 的样本，且有历史源码冻结条件；不能删掉这些保护后当作当前恢复入口。QA 应在自己的 GET-only harness 中落实上述 hook 和当前源码身份，保留旧 runner 原测试。

### B. 真实 auto 入口

已有 `scripts/run_test_batch.py` 使用真实 DocumentParser + DualEngineRouter；新增可选 `--usage-path` 只用于显式复用登记账本，旧默认调用兼容。**原批次必须传原 canonical 路径，不能用默认的新输出目录账本。** 原 S00010 remote 恢复走 A，不通过该命令另建任务。

以下变量由 QA 从原私有注册加载，不把真实路径、owner、批次或 Token写入命令记录；先运行不带 execute 的预检：

```powershell
# QA 已切到冻结源码，并使用已有环境；输出目录必须在其忽略的 local 下。
$env:DUAL_OCR_ENVIRONMENT = 'test'
$env:DUAL_OCR_AUTHORIZATION_MODE = 'TEST_BATCH'
$env:DUAL_OCR_ENABLED = '1'
$env:DUAL_OCR_CLOUD_ENABLED = '1'
& $Python -B scripts/run_test_batch.py --manifest $Manifest --usage-path $CanonicalLedger `
  --owner $Owner --batch-id $BatchId --input $ApprovedInput --output $AutoOutput --strategy auto
# 仅在私有预检全部 READY、原账本可用、当前源 SHA/预算已复核后，在同一参数后加 --execute。
```

该 CLI 会在首次新建任务时运行；重复调用复用任务，不会自动重跑不确定的未完成任务。旧 remote 探针 `verify_mineru_cloud.py` 固定 strategy=remote，不能作为 auto 成功证据。当前工作台云开关仍默认关闭；不要为执行测试全局开启生产工作台外传。

QA 优先采用当前许可下的公开合成文件，在独立 FILE_SHA 测试配置中登记明确 SHA、有效期和小预算，以真实 DocumentParser 为本地工厂。**不 Mock 掉本地结果后称为真实 auto**。合成范围不得与旧真实批次混账，也不得将同一旧文件当成新批次规避占位；若需要在原 19 SHA 中选择新的 auto 策略样本，仍受原 canonical 的 32 总次数和 3 个唯一内容约束，选定范围不能暗中扩大。

必须分开保存以下事实：

| 场景 | 真实 auto／边界验收要点 |
| --- | --- |
| 原生优先／正常本地 OCR | 本地内容和质量达到现有路由条件，无远端 HTTP、候选和引擎来源可追踪 |
| 空白或低质量／普通引擎失败 | 原始本地质量、当前许可、预算均留痕；符合条件才回退，保留本地和云候选；失败回退不丢本地 |
| 敏感／无服务器授权／撤销 | 负向构造仍需拒绝；用户本次调用许可不是删除安全机制的理由 |
| 超限图片 | SAFE_REJECT，永不作为普通低质量回退 |
| 幂等／超时／预算 | 同一 request key 不多 POST；重定向、失败尝试计数；未知结果不重发；达到限额停止 |
| 来源与人工复核 | input_sha256、remote_task_id、initial/selected/fallback engine、质量、两候选、requires_review 完整；不能用成功 HTTP 代替质量验收 |

真实批量性能和总体识别准确率本轮均未新增验证。不是因为需要重复询问调用许可，而是本轮 Fix 收尾以工程准备和最小修复为范围，真实独立验收由 QA 执行。

## 9. QA 可复现命令和证据

使用已有环境，不重新创建虚拟环境或安装全部依赖。先核对受测 Git SHA，再检查新增测试和业务源码：

```powershell
git diff --stat 967cff1e6eec0277b5103182b47098720367c228 bf66e10753757c2e1f92383755817dd8c31ab336
git diff --check 967cff1e6eec0277b5103182b47098720367c228 bf66e10753757c2e1f92383755817dd8c31ab336
& $Python -B -m unittest tests.test_release_safety tests.test_release_routing `
  tests.test_document_parsing tests.test_dual_engine_policy tests.test_local_workbench_config -v
```

候选镜像的依赖环境必须单独验证。QA 将当前冻结的 tests 目录只读挂载到镜像，避免基础层的旧 tests 混入；下面不加载模型、不连接业务库、不访问外网：

```powershell
$image = 'market-regulation-workbench:candidate-v021-bf66e1075375'
$qaTests = (Resolve-Path -LiteralPath tests).Path
docker image inspect --format '{{.Id}} {{index .Config.Labels "org.opencontainers.image.revision"}}' $image
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges `
  --tmpfs /tmp:rw,nosuid,size=512m --mount "type=bind,source=$qaTests,target=/app/tests,readonly" `
  --entrypoint python $image -B -m unittest tests.test_release_safety tests.test_release_routing `
  tests.test_document_parsing tests.test_dual_engine_policy -v
# 接口和官方适配器仍在无网络 Mock/ASGI 下独立覆盖当前镜像版本。
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges `
  --tmpfs /tmp:rw,nosuid,size=512m --mount "type=bind,source=$qaTests,target=/app/tests,readonly" `
  --entrypoint python $image -B -m unittest tests.test_mineru_api tests.test_mineru_official -v
```

55 方法命令包含宿主专用 deploy/local 测试，因此镜像命令不包含 test_local_workbench_config；候选未复制部署准备脚本，不用临时复制实现伪造镜像自带能力。镜像检查的具体方法数和差异由 QA 实际记录。

真实质量复测复用 QA 忽略目录 `local/v021-final-a860abf/evaluate_current.py` 及原 expanded-evaluation／frozen-current-evaluation 的固定任务映射与真值；先检查该历史脚本的硬编码输出位置，为本轮预测另建忽略输出，不直接覆盖历史预测。S00008 仅需同页 auto/Structure 与原参考；S00011 不为寻找更好数字反复调模型；S00019 按独立安全意图复判。PostgreSQL 六项既有 PASS 保留，只有本轮 sink 的安全拒绝／复核标记影响需针对性验证，保留原业务记录和 ACTIVE。离线 preview 现在可在镜像执行 `python -B scripts/preview_offline_ingestion.py --help`，实际含原文输出只进隔离 `/state`。

Fix 忽略证据均位于本工作区 `local/release-closure/`：

| 文件 | 含义 |
| --- | --- |
| safety-reproduction/before.json、reproduce_safety.py | 原 SAFE-001 零真实网络复现；保留原 before，不覆盖成 after |
| focused-regression.log、cached-safety-regression.log | 首次修复 55 项及最终缓存跟进 18 项重叠回归；并非 QA 签发 |
| cached-auto-before.json | 跟进前旧缓存 auto 虽当前超限仍 completed 的真实 Mock 复现 |
| review-flag-reproduction.json | 同一合成输入在原源码与修改后顶层复核标记对比 |
| wireless-route-before.json、wireless-route-after.json | 同原文件路由，after 使用 FakeRuntime，仅证明 Structure 被选中 |
| quality-attribution.json、historical-cloud-table-html-attribution.json | 历史三栏、表格及云 HTML 归因，不作为当前云 OCR 新预测 |
| batch-inventory.json | 原批次／canonical 计数、身份和已有 child 状态的只读核验 |
| candidate-build.log、image-inventory.json | 构建过程、镜像 ID/revision、57 文件核对、实际包版本及挂载；已去掉凭据和宿主原始路径 |

这些私有证据不提交 Git。跨工作区交接按已有私有映射定位，不能把正文、真实文件名、Token 或连接密码复制到报告。

## 10. Windows 整机恢复检查

当前结论 **NOT_TESTED**，本轮没有执行 Windows 重启。待用户安排重启窗口后，QA 按最终实际运行版本检查：若尚未切换，则明确记录验证的是旧运行镜像，不能据此宣称新候选整机恢复 PASS。

1. **重启前**：记录 UTC／本地时间、Docker Desktop 引擎与登录启动设置、四个容器状态、实际镜像 ID/revision、回环端口、restart 策略、挂载的稳定位置及网络。不要输出完整 inspect 的 Env。
2. 暂停新上传并记录活动任务；SQLite 使用只读事务记录每库任务总数、状态分组及原任务 ID 映射，必要时一致性备份。记录选定工件摘要、私密配置摘要、Token可用性（不记录值）、授权期限／撤销标记、canonical 调用计数和已预留 POST；保存到忽略证据目录。
3. 记录 PostgreSQL 数据卷、业务表计数和 ACTIVE 状态，只读核验原 parse_id。无需重跑六个写入用例来证明重启；不要碰 MySQL、Redis 的既有数据。
4. 用户自行安排 Windows 整机重启；本任务不执行 shutdown、修改登录／安全策略或停止 Docker Desktop。
5. **重启后**：等待 Docker Desktop 恢复，检查原项目仅一个 app worker、四容器及健康、实际 revision、相同持久卷和只读模型／私密文件挂载。unless-stopped 不代表用户主动 stop 的服务一定自动启动。
6. 核查固定入口 `http://127.0.0.1:8180`、无访问码被拒绝、正确访问码可读原任务和结果。不能只以根页 HTTP200 代表原任务完整。
7. 对比任务总数／状态、原工件、parse_id、授权和调用账本；正常恢复引起的状态变化要逐项解释。检查无新增不确定 POST、无清零计数、无误恢复旧过期外传任务。
8. 核查端口仍仅本机回环、容器权限与原网络边界；旧 QA 代理容器已被先前清理，不能把历史 nft 隔离记录当作重启后仍存在。
9. 保存重启前后清单、差异和真实执行命令；任何丢失、重复提交、错误镜像、鉴权或隔离失败均按实际 FAIL/BLOCKED 交回 Fix。只有实际整机证据齐备，QA 才可把 CLOSE-04 从 NOT_TESTED 改为 PASS。

## 11. 剩余风险和正式交付

1. 新候选尚未通过独立镜像集成验收，也未替换当前工作台；宿主/API 版本差异显式保留。
2. 无线表格启发式只覆盖当前可复现的文字对齐路径，可能误报或漏报。它不是表格准确率；真实 Structure、关键字段和其他普通文档由 QA 复测。
3. 三栏历史 CER 未达业务线，不能宣称已修复；未标注语义继续 NOT_LABELED。云表严格文本同样未达线，保留复核。
4. 最新用户许可已解除重复申请 API 调用的要求，但旧机器授权配置仍需由 QA 在执行时同步；真实 auto 与旧任务恢复尚无本轮新实测。
5. SAFE-001 新路径及顶层复核变化影响解析结果摘要；相同旧 parse_id 的不可变入库冲突应显式处理，不能覆盖或删除历史记录。无 Schema 变更，无生产数据清理。
6. Windows 整机重启未测；未虚构云端批量性能、真实法律字段总体正确率或最终总体路由合格率。

接收分支及完整业务 SHA 见第 1 节，镜像身份见第 3 节。QA 以本交接新增范围独立回归，保留既有有效结果，按本轮用户标准合并最终门禁。此 Git 交接文件是正式交付载体；没有自动唤醒其他会话，也没有宣称已经通知协调器。
