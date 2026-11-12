# v0.2.3 MySQL审核候选独立QA交接

状态：READY_FOR_QA（候选），不表示QA_PASS或正式启用。用户明确禁止正式建库、runtime变更和8180切换。

候选镜像固定ID `sha256:d502cb6d82be9f8037cb22c6ab9e8ff67ae10bbb6bfadaa302545a569b2ac811`，标签market-regulation-workbench:candidate-v023-4395c2eab604；OCI/source为4395c2eab60472e04e8dd2a26ce7ebc7679b9c4b；测试脚本提交5d45cf4e159b94681a55e66a2f5407dc89863c24，业务不变。OpenAPI29路径，前端冻结业务63bbcc07a6b6d12a6be56fa7b0e81731c3917a45。

正式8180仍v0.2.2，镜像ID e2a94f67ffacef9e780e06bc1484cb5e7dde4b287fa5ef340a666f5e573e52a3，容器b23198928dda0e75ff7ad40d3ce8170da825cb81922526a1db65e8b5815621c1。不能用正式服务的22路径或v0.2.2身份签发本候选PASS。

## 独立复核步骤

1. 从Docker inspect核对候选ID、OCI、前端revision和实际业务导入路径，不仅看标签。
2. 使用现有随机隔离测试库与专用账号。配置只由本机受控ignored文件提供，host=mysql、port3306。不得使用正式root账号或实际PG/SQLite状态。
3. 启动短生命周期测试容器，无发布端口，不挂正式runtime/state/models；root只读、cap_drop ALL。数据库网络仅为隔离MySQL连接，保持云关闭。
4. 只读挂载指定测试提交的tests到/checks/tests，部署前端网关文件到/checks/deploy/frontend（仅供其静态测试），配置到/private/test-review.json。不能挂载旧qa_core替换镜像业务。
5. 执行以下41项套件；显式REVIEW_MYSQL_TEST_CONFIG=/private/test-review.json。确认无SKIP，所有MySQL测试库名必须market_review_test_前缀：

```text
tests.test_mysql_review
tests.test_api_improvements.APIImprovementTests
tests.test_frontend_api
tests.test_mineru_api
tests.test_schema_identity
tests.test_frontend_gateway
```

Python启动时先将/checks置于sys.path前端以读取指定测试，但业务qa_core必须从/app导入。候选验证已输出business_module=/app/qa_core/__init__.py。

6. 在同样隔离条件下执行tests/check_v023_runtime_image.py，检查可选私密runtime加载、部署工厂、29路径、ledger能力和真实MySQL批准回执；该脚本使用合成Token及模拟PG详情，不声称真实PG写验证。
7. 宿主复核tests.test_review_provision_safety四项；这些是无真实DDL的工具单元测试，不要执行正式provision命令。
8. 核对重复请求不新增事件、同版本并发仅一个成功、源变化409、无理由/页码错误422、无权限403、跨owner404、无Token401、未配置或故障503。审批不改变原OCR/PG复核信号，不自动发布ACTIVE或创建重解析任务。
9. 审计账号实际UPDATE/DELETE WHERE 1=0均应被权限拒绝；禁止以真实删除/改写历史作为权限测试。
10. MySQL不可用测试只把测试连接指向关闭端口，不停止共享MySQL，不对正式8180注入故障。复核详情降级能力false且原正文仍可读。

Agent C结果：候选41项PASS、私密runtime集成检查PASS、初始化工具4项PASS。QA需独立记录执行证据，不能直接复制为QA_PASS；浏览器写按钮和正式账号权限尚未验证。

## 独立报告必须记录

镜像完整ID、源码OCI、测试提交、前端SHA、测试实际范围及证据、MySQL隔离与权限、未修改正式PG/SQLite/runtime的边界、未验证事项。审核员名单等待用户确认；当前建议writers空，不以合成alice/bob替代正式审核人员。

QA结束后也不能自动部署。只有正式建库、writer名单、初始化权限、runtime、回滚配置均确认，并获得用户最终部署授权，才能进入READY_FOR_RELEASE/RELEASED。
