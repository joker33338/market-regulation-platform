# 文件工作台开发与隔离验证报告

日期：2026-11-17，Asia/Shanghai。
状态：BACKEND_API_PARTIAL；已实现的流程完成开发自测，正式启用待确认。
这是单Agent开发自测，不是独立QA，不签发QA_PASS、READY_FOR_RELEASE或RELEASED。

## 源码与运行身份

- 分支：codex/file-workbench-ux。
- 开发基线：0b962f1ff7a0b579eb632fc6db9e1c509b801ec7。
- 后端源码提交：7cafac62af052b8fb0a454f8222feca9cec46457。
- 前后端联合源码提交：e82898757036ef521bc5c7a625727a29e565211a。后续交接提交仅调整文档，业务源码不变；报告本身的最终HEAD见Git提交记录。
- 新工作台镜像：本轮未构建；没有候选镜像ID或OCI revision，不以源码测试代替镜像验收。
- 当前8180：market-regulation-app-1，running / healthy。
- 当前完整容器ID：ab2e4e86148804b3815b682fabd09fdfbad61a352632c1c9311cae6960ade299。
- 当前运行镜像引用和镜像ID：sha256:683bc72b3c2ab972158c22224475fc8624bc777921ae42318de53b3dd21bd118。
- 当前运行源码/OCI revision：0b962f1ff7a0b579eb632fc6db9e1c509b801ec7。
- 启动时间：2026-11-16T07:17:24.056642778Z；本轮没有重启或替换。
- 现有持久化挂载目标：/private/runtime.json、/state、/app/reports、/models。只记录容器目标，不公开宿主私密位置。

## 完成的开发内容

1. 文件工作台替代原列表主入口；旧文件页和入库页保留高级入口。统一业务步骤、空态、失败提示与操作入口，技术标识折叠。
2. 文件/目录上传、子目录分组、本批同owner SHA去重、格式/大小校验、整批归类确认、自动分批排队；失败项重试不重传成功项。整批不设固定文件数上限，不代表无限资源或已完成大规模压力测试。
3. 按文件名/资料名称/文号/案号搜索及类别、批次、时间、阶段筛选；重置、账号隔离的本机常用条件、分页和固定全匹配快照；跨页选择、跨页连续预览及审核返回查询恢复。
4. 完整待人工审核队列，显式批量审核确认、后台逐份记录、结果分页查看和恢复。角色撤销、source变化、审核版本冲突不会被当作成功。
5. 整页正文修订page_body_v1，原始OCR和表格保留；每页采用最新明确修订，重新审核后绑定revision_id入库。历史语义不明修订继续阻断。
6. 法规与案例分别适配既有清洗、切分、向量及目录投影；来源范围保留原页/块/坐标；案例不会被法规条款解析器误当成法规。
7. 汇编拆分建议、人工标题和范围确认、跨正文段设置范围。后端拒绝重叠范围；已发布来源范围或类别变更须专门更正流程，本轮不静默转换。
8. 后台等待审核/解析、管理员接手、预检与构建；到期时间公平领取避免前部待审核条目使后部饥饿；排队协程独立于引擎，慢文件不会卡住后续提交。使用既有解析结果，构建不重复OCR/MinerU。
9. 固定发布清单、显式确认、增量保留原有ACTIVE资料、复用已构建向量；来源、审批、模型/规则签名和ACTIVE乐观锁全部保留。多篇文件的部分发布不标整份完成。
10. 修补HTTP知识检索owner范围检查；默认法规、显式案例/全部授权资料，未知归属失败关闭。核验无SQLite任务历史的PG离线导入最新解析，旧解析不继续审核/构建。
11. 新增26个方法声明，完整OpenAPI共77条路径，Pydantic与TypeScript同步。独立工作台草稿，不覆盖旧冻结契约。

## 修改范围

| 范围 | 主要文件 |
|---|---|
| API与编排 | qa_core/api/workbench_*.py、reviewed_export.py、source_segments.py、upload_ownership.py，以及frontend/review/review_writes/ingestion/read_store/search/contracts/capabilities/common/business_library/schema入口 |
| 解析/入库/检索 | document_parsing/mineru_api.py、case_bridge.py；indexing/service.py；retrieval/store.py；storage/library_projection.py、mysql_review_ledger.py |
| 前端 | FileWorkbenchView、WorkbenchIngestionView、ReviewView、SearchView；components/workbench；api/workbench、reviewWrite、frontend、types；路由与导航 |
| SQL | 20261116_reviewed_article_range_up/down.sql；仅准备并在隔离库验证，正式未执行 |
| 契约与说明 | frontend-openapi-workbench-draft-1.json、file-workbench-api-contract.md、确认范围与用户指南 |
| 验证 | 新增workbench/case/reviewed_export/source_segments测试、真实隔离PG及浏览器探针和可复现运行入口 |

## 自动化及真实数据库结果

最终精确统计以私密原始JUnit和JSON为依据；重复执行不累加为新测试方法。

| 类别 | 结果 | 实际证明范围 |
|---|---|---|
| 定向pytest回归 | 121 PASS / 0 FAIL / 0 ERROR / 1 SKIP（共122项） | 新工作台、入库、检索范围、源结果、删除、账号与真实隔离MySQL权限；SQLite均临时合成状态 |
| business_library真实隔离PG回归 | 24 PASS / 0 FAIL / 0 ERROR / 0 SKIP | 法规/案例目录、条款范围、来源与权限；后续未改该套件的只读目录查询；新契约标识另由HTTP测试验证，不重复整套只读回归 |
| 既有前端流程真实PG/MySQL | 1 PASS / 0 FAIL / 0 ERROR / 0 SKIP | 密码身份、审核、候选、发布、查询与回滚夹具 |
| 工作台真实PG/MySQL | 4 PASS / 0 FAIL / 0 ERROR / 0 SKIP | 案例目录与owner检索、较长整页修订、同页两篇合并发布、离线新解析阻断旧审核/候选 |
| TypeScript与Vue脚本 | PASS | 现有tsc配置，以及8个改动Vue组件的脚本块检查；后者不冒称完整Vue模板类型检查 |
| Vite生产构建 | PASS | 实际组件模板编译成功；输出仅开发验证产物，未替换8180固化页面 |

Windows测试符号链接创建不获系统允许时跳过，不能将该项写成PASS。没有新安装或升级依赖。

## 浏览器验证

- 工作台11组检查通过，0页面脚本错误：真实合成HTTP及临时SQLite，覆盖查询/重置/保存恢复、跨页多选、全部匹配服务端快照、原件连续预览、空态、320/768/1024/1440宽度，以及整批归类上传、重复和不支持格式提示。
- 真实PG/MySQL流程7组检查通过，0页面脚本错误（另作为1个pytest方法记录，不重复计数）：从已经保存的合成解析结果开始，确认2份法规和1份案例、保存整页修订、明确批量审核、构建、核对清单、显式发布、分别在目标库查到，以及审核/发布页面四种宽度。
- 使用合成凭证和合成PDF，没有使用真实用户凭证或私密原件自动化操作。
- 原件SHA及原始PG解析结果保留；长修订库查询返回reviewed_copy。原始OCR未被修订覆盖。
- 首次浏览器探针点击组件内部隐藏输入被可见占位层阻挡，改为点击实际可见控件后通过，没有强制点击或放宽业务断言。

真实数据库测试使用全新短生命周期PG容器及专用qa_round01，并仅复用既有market_review_test_前缀MySQL测试库。PG镜像固定sha256:0dd3149a06e4579a0d70d8fef9945636cd514005e7237deb27f9b67886f8dc4f，未拉取镜像。容器结束后停止，保留卷与证据；没有正式DDL、正式业务数据写入、正式审核或ACTIVE变动。

## 模型、数据及未覆盖范围

- 本轮真实PG和浏览器闭环使用明确标识的合成解析、固定测试向量，仅证明数据库/API编排和权限。不是BGE-M3质量、真实OCR或云端MinerU验收，不将上传→OCR成功→业务发布全链路描述为已实测。
- 原有PaddleOCR、PP-StructureV3、MinerU及BGE-M3实现保留；本轮没有真实云调用、模型下载或授权预算变更。
- 未测超大目录、长时间故障恢复、进程崩溃/磁盘断电、多人高并发、大数据量性能、所有屏幕阅读器。JSON操作快照与元数据存在全目录扫描成本，不能宣称无限吞吐。
- 汇编建议为标题规则，目录/引文/重复标题仍需人工核对，不提供模型自动准确拆分保证。
- 案例日期、处罚金额、地域、机关等缺失事实不自动编造；本轮没有新增这些业务筛选或可靠事实抽取。
- 未定义正式表格修订/导出承接的资料继续阻断发布。
- 已发布来源范围/类别重划仅做冲突拒绝，没有新增撤回/替换更正向导。需要该操作时按专门更正流程确认，不能绕过本轮门禁。
- MySQL审核与PG发布不是天然跨库原子事务；保留源指纹/审核锁/幂等及结果待确认语义，不声称完成所有跨库故障注入测试。

## 启用前清单与回滚

1. 固定新前后端源码并完成候选镜像构建，记录镜像ID/标签/OCI revision/前端revision。现有源码验证不等于镜像已验收。
2. 明确批准后再执行整页修订法规所需check_article函数升级；无新增表或引擎。本轮仅隔离库执行，正式缺标记时503失败关闭，不自动DDL。
3. 复核正式MySQL仍为最小权限账号、既有角色与范围、PG写账号、模型签名、文件与五类工作台私密状态目录持久化、活动任务和备份。
4. 明确批准切换时再更新共享8180，不能在活动任务处理中强行替换；保留现有v0.2.3及v0.2.2回滚镜像，不移动历史标签。
5. 回退应用保留原始文件/解析/MySQL事件/新增状态目录；旧应用不读取新工作台状态。已发布审核副本时，旧读接口可能不识别reviewed_text，需先核对并显式恢复兼容ACTIVE；不得靠删除新版本或历史修订回滚。
6. down脚本仅恢复旧条款范围函数，不删除既有记录；不能在新修订资料继续写入时盲目执行。

本轮未Push、未合并main、未打标签、未构建正式镜像、未清理历史容器/卷/镜像、未改正式runtime。正式版本仍由上列8180身份提供。

## 复核入口及私密证据

可复现入口：tests/run_workbench_regressions.py、tests/run_workbench_isolated_databases.py、tests/check_workbench_server.py、tests/check_workbench_browser.cjs、tests/check_workbench_flow_browser.cjs、tests/check_workbench_types.cjs。执行前按各脚本说明提供既有测试环境；不得填正式连接或用真实凭据测试。

原始证据位于Git忽略的local/workbench-evidence/：regression的JUnit/JSON/执行日志；databases各轮JSON与私密配置/日志；browser-result.json及响应式截图；browser-flow各轮日志；openapi-methods.json、shared-8180-identity.json、script-types.log、vite-build.log。早期失败证据保留，不作为最终通过成绩。

新增的来源范围和最新离线解析保护，均先用合成夹具复现失败，再修改实现并执行回归；慢解析阻塞后续排队也以同样方式验证。早期复现失败不与最终通过重复计数。

实际使用的技能：grill-me/grilling（需求澄清）、frontend-ui-engineering（Vue界面）、api-and-interface-design、python-code-style、supabase-postgres-best-practices、python-testing-patterns、test-driven-development、systematic-debugging、webapp-testing。只使用本机既有依赖；用户单Agent组织方式保持。
