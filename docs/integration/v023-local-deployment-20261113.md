# v0.2.3 本地联调切换交接

日期：2026-11-13，Asia/Shanghai。状态：**LOCAL_INTEGRATION_PENDING_QA / BACKEND_API_PARTIAL**。用户最新明确指示“先切换本地联调入口”，作为原“独立QA后再切换”的本次例外；不签发QA_PASS、READY_FOR_RELEASE或正式生产RELEASED。

## 实际运行身份

| 项目 | 8180当前实际值 |
|---|---|
| 后端源码 / OCI revision | d28cc81f413fb25b0446ceb67451c36e2bfe7a0e |
| 前端冻结 HEAD | 477d8c858f67ff8d20177a4bf722f45cabab9d64 |
| Docker镜像ID | sha256:cb478ff8a778a79c841db7a70d690c3735ca39da7c3b755676449e8cafde9367 |
| 镜像标签 | market-regulation-workbench:candidate-v023-joint-d28cc81f-f477d8c85 |
| 当前容器 | market-regulation-app-1 |
| 容器完整ID | d6b567be5b42c6f41121fca14ffc37ac2adb88ab95d0d72ba1cc84c1ea1fbeab |
| 实际服务身份 | frontend-api-v0.2.3-draft-5，info.version=0.2.3-dev，54路径 |
| 健康与页面 | healthy；/login真实HTTP 200、用户名及密码输入框可见 |

入口 http://127.0.0.1:8180/login 。前后端来自冻结Git对象，前端独立类型检查和Vite构建通过；仅有既有大bundle告警。未修改前端worktree。镜像ID、容器.Image、后端及前端label逐项相符；不能用其他文档HEAD替代此OCI。

## 前端缺口核对和补齐

前端draft-4/draft-5接入报告及最新源码已核对。账号/角色、日志、审核、删除、入库治理、检索筛选及8条library路由均已有对应后端方法。最新前端已修正ADMIN审核判断、pages[].tables读取、终止任务重试和统计窗口刷新，无需本轮改前端。

本轮确认并修复library显式kb_version选择的权限缺口：所有8条library GET统一要求ADMIN才能显式传版本，普通用户传参403；默认ACTIVE查询及范围外404仍保留。没有给普通人新增全局权限。源码修正提交为上述d28cc81f…，测试增加真实HTTP 403断言。

运行期54路径与[离线OpenAPI](frontend-openapi-v023-draft5.json)完整比较相同，包含DELETE文档方法、账号管理、日志及library方法；不存在“只有源码未加载”的旧状态。保留draft-4冻结快照，不伪造路径能力。

## Runtime和安全边界

原Token映射、MinerU配置/Token、模型、PostgreSQL、SQLite任务存储、状态挂载及授权预算保持。原runtime文件未覆盖，创建独立新runtime用于本次容器，私密内容不入Git。

启用账号密码存储，初始化管理员用户名admin、独立principal/owner、ADMIN全部业务权限；没有将local-user升级为管理员。随机密码仅写本机ignored私密文件，账号文件仅存PBKDF2加盐哈希，文件ACL收紧，聊天及报告不记录密码。用户通过本机私密文件取得密码后登录；未用真实管理员密码执行自动化测试。

复用已初始化market_review的非root最小权限账号，并改用正确Docker网络主机地址；只读预检health成功，审核事件无UPDATE/DELETE权限。用户业务审核需要真实ADMIN或授权REVIEWER，记录实际principal，不自动批准任何法规。

KNOWLEDGE_WRITE_PG_DSN本轮未配置；入库/发布写能力因此明确关闭，不能借现有PostgreSQL超级用户读连接默默启用发布。既有运行账号market_app具有超级用户权限的问题见数据库专项报告，仍需后续最小权限整改。

117条法规、1942个章节、10618个条款均仍为待复核候选，未建立ACTIVE，未生成向量。法规库/案例库默认返回合法unpublished空态；这不是数据被删除。管理员可在审核中心处理本批解析资料，再经真实审核、BGE构建及发布门禁进入正式检索。本地界面可访问不等于发布能力或法规已核验。

## 自测与未覆盖项

同一不可变镜像的自测最终去重：132项接口/安全回归、1项真实隔离PG/MySQL编排、6项真实PG删除引用、22项法规PG，共**161个不同方法通过，0失败、0跳过**，另25子用例。85个源码/入口文件与冻结Git文本LF内容核对一致；未挂载宿主业务源码冒充镜像。

HTTP探针验证纯密码模式、ADMIN跨owner删除、USER拒绝、登出失效及54路径；正向删除使用明确无引用夹具，真实PG引用另有6项验证。真实PG/MySQL编排使用合成1024维向量，不代表真实BGE推理质量或云OCR验收。

联合镜像内的真实密码表单登录和10个页面共11项浏览器检查通过，未捕获页面脚本异常；使用合成身份、临时状态，无正式数据库写操作。这只证明已执行的表单/渲染范围，不覆盖所有业务按钮、已发布法规详情或管理员完整CRUD浏览器流程。

切换后真实8180只读核对：54路径、密码登录配置true、审核台账配置true、知识库写配置false；匿名登录页200、输入框正常、无pageerror；未提交真实用户密码。短期18185浏览器容器已停止，没有新增长期联调服务。

新版独立QA未完成，历史RBAC/软删除QA_PASS不自动延伸。请QA固定本镜像ID及上述前后端SHA独立验收；无需重建镜像。对共享8180只读核查，审核/账号/删除/发布写测试仍在批准的隔离状态使用合成数据，不用正式数据做故障或破坏测试。QA期间冻结镜像。

## 切换和回滚

切换前确认活动任务为0；短暂取得SQLite任务写事务锁以阻止检查窗口内新提交，停止旧容器后释放，没有修改任务记录。只切换app，不重启PostgreSQL/MySQL/模型，不删除卷。

首次创建遗漏原部署在容器层设置的健康检查，切换脚本未取得healthy而超时，已自动恢复旧容器；随后补齐原检查参数，在同一镜像上重试成功。不是业务镜像缺陷，首次及重试记录均保留。没有因超时删除数据。

回滚容器market-regulation-app-v022-rollback-20261113已停止并保留；其原完整ID为b23198928dda0e75ff7ad40d3ce8170da825cb81922526a1db65e8b5815621c1，镜像sha256:e2a94f67ffacef9e780e06bc1484cb5e7dde4b287fa5ef340a666f5e573e52a3，原标签market-regulation-workbench:sha-30c4663ceb93cbba302b322f1ecee0d06d80bfb4，后端OCI30c4663ceb93cbba302b322f1ecee0d06d80bfb4。历史镜像均保留。

需要回滚时先再次核对活动任务，协调停止新app、保留新容器后，将旧容器恢复原名并启动；旧runtime及挂载原样可用。账号/审核历史即使有新增也不得删除回退。不要直接运行旧Compose/准备脚本覆盖当前冻结镜像；后续更新必须重新核对实际镜像ID与挂载。

完整运行配置、回滚参数、管理员私密文件、构建/测试/浏览器/切换记录位于backend-api工作区ignored local/v023-joint-release/，不提交配置、口令、Token、DSN或真实文件内容。测试辅助及文档交接SHA在最终消息记录，业务源码仍冻结d28cc81f…。未Push/Merge/打Git Tag/部署外部生产。
