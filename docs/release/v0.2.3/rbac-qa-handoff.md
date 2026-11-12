# v0.2.3 RBAC独立QA交接

状态：READY_FOR_QA，仅多用户后端与隔离候选；不是QA_PASS、READY_FOR_RELEASE或RELEASED。正式环境仍v0.2.2。

## 不可变候选

- 业务/认证源码完整SHA：`b96c34901f783cd136235663d20ccef6cc62a019`。
- 镜像标签：`market-regulation-workbench:candidate-v023-rbac-b96c34901f78`。
- 镜像ID：`sha256:be18c7064c73bcd5ac312b6919809ac6edc19008ee45b30249ed704ace797b4c`。
- OCI revision：同上述b96c349完整源码SHA。
- 镜像内前端仍冻结`63bbcc07a6b6d12a6be56fa7b0e81731c3917a45`；本轮不含新前端3b7b62f，不得用后端通过替代其UI联验。
- 契约：frontend-api-v0.2.3-draft-2，30路径，独立文件frontend-openapi-v023-draft2.json。

独立QA首先核对Docker inspect完整ID、revision及业务导入路径。测试主业务必须来自/app/qa_core，禁止把QA旧业务源码挂进候选。

## 实际自测与复跑

宿主与候选镜像各61项通过、0FAIL/ERROR/SKIP；两次执行是同一套测试，不能相加算122项。候选另有私密runtime加载、部署工厂和真实MySQL写入检查通过。

套件：

```text
tests.test_principal_rbac
tests.test_mysql_review
tests.test_api_improvements.APIImprovementTests
tests.test_frontend_api
tests.test_mineru_api
tests.test_schema_identity
tests.test_frontend_gateway
tests.test_review_provision_safety
```

使用显式REVIEW_MYSQL_TEST_CONFIG，只允许market_review_test_前缀随机隔离库及非root运行账号；缺少该配置时测试会SKIP，不能写为通过。所有用户和凭证为合成，未使用真实local-user凭证进行自动化写测试。

候选以--rm、无端口发布、根文件系统只读、cap_drop ALL运行；现有数据库网络仅用于隔离MySQL，云关闭，没有正式runtime、PG凭据、state、模型挂载。tests只读挂到/checks/tests；静态网关文件挂/checks/deploy/frontend；初始化脚本与SQL分别挂/checks/scripts和/checks/qa_core/storage的对应文件；/tmp与/checks/local为一次性tmpfs。

第一次测试准备因未配置/checks/local tmpfs而只读失败，未开始业务测试；补齐临时挂载后61项通过，不把该准备错误当产品缺陷或通过结果。私密配置加载检查器为tests/check_v023_runtime_image.py，同样仅用隔离库及合成PG源。

## 必须独立确认的矩阵

| 要求 | 对应验证 |
|---|---|
| 两个USER相互隔离 | user-a/alice、user-b/bob，自己可读、别人404，原有上传/任务隔离回归 |
| USER不具审核权限 | 有效写请求403，即使旧MySQL配置writers包含owner |
| REVIEWER授权范围 | 无个人owner的reviewer-1可审核alice；越界reviewer-outside仅bob，访问alice详情/事件/写均404 |
| 两审核员同一owner | reviewer-1与reviewer-2共享alice文档版本，operator_id不同、owner_id相同 |
| Token身份唯一 | 重复principal配置被拒绝；USER owner配置也拒绝静默共享 |
| local-user兼容 | 旧映射仅legacy:local-user/USER，无审核范围，不提升权限 |
| 凭证失效 | revoked/disabled后401；私密文件更新后下一请求立即拒绝 |
| 审核角色撤销 | 下一写请求403，不靠旧writers兜底；撤销范围后对象不可见 |
| ADMIN默认无审核权 | ADMIN单角色写403，无全局owner范围 |
| 幂等/并发锁 | 同审核员重复同键返回原事件；不同审核员同键不互拿回执；共享文档版本并发仅一个成功 |
| 源结果保护 | 原始正文、source字节、PG原结果不被审核改写；仍requires_review，不自动发布 |
| 审计身份 | operator_id=真实principal，owner_id=源文档归属，operator为兼容身份别名 |
| MySQL失败 | 写503、详情200且能力false、其他只读接口继续可用；故障只指向测试关闭端口，不停共享MySQL |
| 禁止请求伪造 | body中的operator_id或owner_id额外字段422 |
| 其他安全边界 | 通配符范围拒绝、空范围SQL FALSE、范围数组参数化、事件账号UPDATE/DELETE权限均拒绝 |

历史事件不补造principal，不能以旧operator值当作新身份。独立QA应记录原事件未修改的边界和新事件字段差异。

## 报告要求及停止边界

记录候选完整镜像ID、source SHA、前端SHA、契约版本、测试脚本提交、数据隔离、实际执行范围与未验证事项。Agent C的61项自测不能复制为QA_PASS。

不创建正式market_review，不初始化真实人员，不注入正式配置，不改正式runtime或writers，不重启8180，不改ACTIVE，不删除数据库、卷或证据。正式启用需用户另行批准。
