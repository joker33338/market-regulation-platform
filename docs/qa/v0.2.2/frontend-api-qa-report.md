# v0.2.2 前后端独立验收报告

## 最新裁决：FAIL（新增有头PDF交互证据，2026-11-11）

新增18张截图的摘要/大小已全部核验。有头PDF原文可辨识，页签/质量/候选等只读段已有补证，原先“初始原文空白”的显示证据缺口可以关闭；headless空白不认定产品Bug。分页状态变化但左侧实际原文画面不变已由两张全景与两组相同特写证实，登记 [V022-F01，P1，RELEASE_BLOCKER](V022-F01-preview-pagination.md)，交WorkBuddy最小修复。前端当前b511f388def788fa1b07fdfeab9a93c7342f4cd3仅文档变化；后端/共享镜像不变。

当前整体由BLOCKED转为FAIL，依据是真实分页对照错配，不是缺少CDP JSON。V022-E01仅保留QA尚未执行的隔离合成写闭环证据，不再重复登记初始PDF不可见，也不将分页状态标签变化标为分页PASS。后文保留此前各时点记录。

## 已有截图独立审查更新（2026-11-11）

用户已提供原始截图及索引位置。QA完成40张图片摘要/大小/可解码性核验，其中24张是v0.2.2主截图；直接目视15张，覆盖七页面及详情、空态/无权限和响应式抽查。见 [截图证据审查](browser-evidence-review.md)。前端当前5bd769346a2486c216ce20e26d39501cf1f034f2仅文档变化。原始CDP未落盘，不补造；不再因“缺少JSON”单独阻断，也不重复索取已有截图。

V022-E01收窄为前端P0真实写闭环、原文视觉对照及必要交互的证据缺口；截图显示层审查已完成，不能再笼统写为“七页面没有任何独立证据”。整体仍BLOCKED，无新增确认业务Bug。后文为各时点原记录，依本补记解释最新状态。

## 最新正式交接补记（2026-11-11）

用户指定的WorkBuddy正式入口 `docs/frontend-api-integration-report.md` 已完整读取。其最新已提交HEAD为 `bcf4fed064d38f7f36d7715b48d0b0111a06760c`，工作区干净；相对本轮已构建的5d83b13仅四份文档变化，业务源码未变化，因此类型/构建证据复用，无需重跑。8180实读容器ID、镜像ID和healthy与下文一致，未发生静默切换。

正式报告明确：FRONTEND_INTEGRATION_READY仅覆盖七页面约定只读接入，不覆盖上传/创建/恢复/取消写链路或独立QA。镜像、revision、契约与QA实测一致，消除了交接身份的歧义，但没有改变QA正式P0范围，也没有提供写闭环已执行的新证据。

逐页浏览器证据卷引用了Edge/CDP、网络事件、DOM、按钮禁用态和截图，但截图只注明“本机临时目录”，未给出可直接读取的采集文件位置。本轮没有据此假定原始浏览器产物已独立核验。可先只读审查其采集JSON/截图，避免重复浏览器操作；仍须区分开发自测与QA核验。V022-E01保持BLOCKED，无新增代码Bug，不要求开发重复修复。

以下保留首轮实际测试和环境拒绝事实；补记不是重写旧执行结果。

日期：2026-11-11。**当前结论：BLOCKED。** 后端定向自动化、共享8180只读检查和前端类型/构建通过；七页面浏览器交互及前端P0写链路缺独立证据。不将WorkBuddy自测READY当成QA PASS，未确认新的业务代码缺陷。

## 1. 源码、交接及真实运行身份

| 对象 | 本轮实读 |
| --- | --- |
| 正式受测后端 | `4fc4cf124a120762593064676ea5f8dbe2394119`，`feat/backend-api-v0.2.2` |
| 后端文档交接HEAD | 原始工程 `20bfeef57e101f08a2f37bd4a73b6ed4237dcba5`；只读交接，不将文档SHA冒充运行revision |
| Agent C另一工作树 | `codex/backend-api-v0.2.2`，`712521429bb39e10b00730e139ccb4889dd2e555`；仍为分阶段开发态，不是正式运行受测源码 |
| WorkBuddy受测前端 | `5d83b13f4132464ddb764501967bc50992778062`，`feat/frontend-api-v0.2.2` |
| 前端检查结束时HEAD | `688b824213a4489e2f1ce1577677b341f2c10792`，相对受测版本只改四份交接文档，业务源码不变；另有WorkBuddy未提交报告修改，QA未触碰、不计入冻结交付 |
| QA起点 | `843c64d9589091d49bdf68f8576647593bedfaa0`，原QA工作树与名称保留，未改v0.2.1报告 |
| 8180容器 | `market-regulation-app-1`，ID `de1c0271a55eb579ef43073ad3f7109732bd409bb49259087451b6f32fe401af`，前后均healthy且未切换 |
| 镜像标签 | `market-regulation-workbench:candidate-v022-4fc4cf124a12` |
| 实际镜像ID | `sha256:8f169cd82cc1bf55807eb48a9f75e0b5206ac4cb10ca27c38fe206a85e93d7a4` |
| OCI revision | `4fc4cf124a120762593064676ea5f8dbe2394119` |
| 契约 | 正式交接 `frontend-api-v0.2.2-1`；实际OpenAPI `info.version=0.2.2-api-candidate`，22路径 |

正式事实来源：原始工程 `docs/integration/v0.2.2-local-runtime-handoff.md`、该源码的契约/OpenAPI及WorkBuddy前端集成报告。不能误用另一分阶段工作树的draft-1契约认定当前服务缺接口。

后端Git精确快照276文件核验，通过只挂测试目录在**同一镜像**一次性network=none容器中执行必要测试；业务模块实际来自 `/app/qa_core`，未用QA旧业务代码。此为隔离测试，不是另一长期后端，不切换/重启共享容器。前端按受测SHA导出到QA忽略目录构建，复用已安装依赖，不安装/升级依赖或写WorkBuddy业务文件。

## 2. 本轮实际测试

| 测试层 | 实际执行及结果 |
| --- | --- |
| 定向API及隔离安全 | 候选镜像内 `tests.test_frontend_api`、`tests.test_mineru_api`、`tests.test_schema_identity`，28 PASS，0 FAIL/ERROR/SKIP |
| 测试真实性边界 | TestClient+临时SQLite、合成输入，PG游标/远端模拟；不冒充本轮真实云OCR或真实PG写入 |
| 真实8180认证只读 | OpenAPI、服务信息、documents、tasks、review、versions、stats、health共八组：无凭证401、有凭证200 |
| 参数及不存在对象 | 三组非法分页422；文档、原件、审核不存在ID均404 |
| 真实原文读取 | 一个现有可访问对象HEAD200、body0；Range bytes=0-9返回206、10字节，均有X-SHA256；未保存或输出原文内容 |
| 真实既有解析结果 | GET结果200，quality存在；没有创建共享任务 |
| 真实审核详情 | 200，review_write_supported=false；未调用审核写操作 |
| 真实结构/Chunk预览 | 一个现有任务结果POST只读preview200，write_performed=false；不当作入库通过 |
| 真实检索空态 | keyword检索200，unpublished、kb_version=null、count=0、source=public；仅空态通过，有ACTIVE数据的PG真实检索未验证 |
| 前端静态检查 | 精确SHA副本 `tsc --noEmit` 退出0 |
| 前端构建 | 精确SHA副本Vite build退出0；只有chunk体积提示，不是构建失败 |
| 独立浏览器 | 启动Edge headless被执行策略拒绝，未取得浏览器会话、截图或交互证据，未尝试绕过 |

初次预览服务启动在错误工作目录下提示dist不存在；在QA构建副本正确目录启动后正常，后因浏览器环境阻塞主动停止该前端预览。原错误仅为执行环境诊断，未作为产品Bug。共享8180始终未重启或替换。

## 3. 七个页面逐项情况

WorkBuddy记录的七页面只读真实联调属于开发自测，本轮仅复用为接线参考，不算独立浏览器PASS。前端代码有路由与契约适配，独立类型/构建通过；以下“API通过”不等于对应页面交互已通过。

| 页面 | 优先级/交付能力 | 独立API证据 | 独立页面证据 |
| --- | --- | --- | --- |
| 文档管理 | P0上传/列表/原文 | 真实列表与原文HEAD/Range；合成上传/身份/幂等自动化PASS | 浏览器上传、列表操作与原文对照NOT_TESTED |
| 智能解析 | P0任务、OCR、结果、质量 | 真实既有任务/结果/质量读取；合成提交/轮询/结果PASS | 新上传→真实OCR→质量提示的页面闭环NOT_TESTED |
| 文档审核 | P0只读结果 | 真实审核列表/详情；跨owner SQL及只读约束自动化PASS | 候选/原文对照渲染、HTML安全交互NOT_TESTED；不要求未承诺审核写入 |
| 知识库入库管理 | P1结构/Chunk/版本 | 真实只读preview200、write_performed=false、versions200 | 结构/Chunk操作NOT_TESTED；不把预览算正式发布 |
| 法规知识检索 | P1检索/追溯 | 真实public未发布空态；合成SQLite有数据检索自动化PASS | 空态显示及有数据来源跳转NOT_TESTED；不要求填充正式ACTIVE |
| 首页工作台 | P2真实统计 | 认证stats200，匿名401 | 数值/图表与API逐项对应NOT_TESTED |
| 系统监控 | P2健康/异常 | 认证health200，匿名401，服务异常脱敏自动化PASS | 状态语义、错误/空态渲染NOT_TESTED |

## 4. 安全覆盖与边界

28项中已覆盖：认证/跨owner、原件Range/HEAD/摘要及篡改拒绝、上传身份与任务映射/幂等、参数校验、审核owner SQL过滤和不依赖finding视图、连接失败清理、Schema OID/vector/路径/所有者等fail-closed、错误脱敏。真实HTTP本轮确认401/404/422；没有独立复现403，不能宣称所有状态均实测。

跨owner主要为合成TestClient证据，不冒充共享8180双用户真实会话验证。未向共享服务上传原始或合成文档，未写共享SQLite、结果库、正式ACTIVE；唯一POST为契约明确只读的preview和keyword search。没有云API请求、预算变更、DDL、DELETE、迁移或模型下载。

## 5. 历史复用

v0.2.1本地模型、缓存安全、法律切分/父子Chunk、BGE及数据库隔离/生命周期等原PASS保持原SHA和范围，不重复全量。v0.2.2接口适配、前端显示和新增HTTP权限由本轮证据判定，不能继承v0.2.1整体PASS。历史MinerU403、Windows整机恢复、MySQL迁移均不加入本轮API门禁。

## 6. 当前唯一阻断及最小解除条件

**V022-E01 — EVIDENCE_GAP，状态BLOCKED；根因ENVIRONMENT_LIMITATION。**

- 受测后端SHA：4fc4cf124a120762593064676ea5f8dbe2394119；前端SHA：5d83b13f4132464ddb764501967bc50992778062（688b824业务相同）。
- 复现条件：从QA独立构建副本预览，尝试启动独立Edge headless浏览器。
- 真实证据：工具返回启动命令 `rejected: blocked by policy`，没有浏览器执行成功证据。
- 对应承诺：七页面独立验收，以及P0上传→任务→OCR→结果→原文→质量提示的前端闭环；开发自测明确未覆盖写链路，不能从READY扩大声明。
- 业务影响：当前无法确认实际按钮/请求/身份映射/渲染与正确API响应一致，不能签发前后端整体PASS。
- 最小解除：提供合规可用的浏览器测试入口，只补七页面及上述必要闭环；写入部分只用获准合成对象和隔离状态，不影响共享8180既有任务/ACTIVE。不需重跑28项或v0.2.1全量，不要求新建长期后端。
- 是否需改代码：目前无证据要求Fix、Agent C或WorkBuddy修改业务代码。若后续复现后端缺陷则Fix修复、Agent C集成新SHA/镜像；前端缺陷由WorkBuddy最小修复。

暂无已确认RELEASE_BLOCKER代码缺陷。没有把环境拒绝升级为P1，也没有把未验证功能写PASS。有数据PG正式检索、共享故障注入、独立双用户HTTP、全部复杂OCR样本效果仍按未测记录；不为填满这些项扩大本轮功能。

## 7. 证据与停止边界

原始证据只在QA忽略目录 `local/v022-qa/`：后端精确快照 `backend/`、`image-tests/result.json`及execution.log、`runtime-openapi.json`、`live-readonly.json`、`existing-data-readonly.json`、`typecheck.log`、`build.log`、前端精确构建副本 `frontend-source/`。浏览器拒绝为会话工具证据，未伪造本地截图/日志。

本轮仅提交v0.2.2 QA报告，不改历史v0.2.1文件、不改开发工作树、不构建业务镜像、不重启共享容器、不清理状态或依赖。QA分支名称保留。未Push、未Merge、未部署。执行策略拒绝的是本次浏览器启动；在获得可用合规入口前停止依赖浏览器的工作，不绕过安全策略。
