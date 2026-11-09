# 安全诊断与构造失败修复交接

受测业务源码：`0770e65578b6cf128cb497afbd521901b59e6719`。
Fix 基线运输提交：`e16b4e241651a0641bdccac8420a64290e40869f`，对应业务源码 `ee7dd7e6c8243e98c9f1bf995a4c57c555611786`。
正式 QA 交接：`9bdb4685a081fa412eea88b4c15fe2913d96e8f3`；原样导入测试提交：`5e752376d8c8855a974be5add9f0902c324fc22d`。

已实现 OBS021-001 四字段安全诊断与 Q021-003 构造/上下文进入失败候选保存。
策略拒绝只接受结构化577/1260证据，普通导入失败保守标记一般加载失败，原异常正文不进入诊断。
普通算法异常保持失败，不能误记依赖不可用；失败候选、人工复核、真实SHA、生产授权与TEST_BATCH预算保持。
远端构造异常未发HTTP时仅记BLOCKED/NOT_TESTED，不把初始化失败当真实API失败。

正式8项合同通过。最终最小相关回归104项全部通过，0失败、0错误、0跳过，含8项合同，不重复计数。
命令如下，使用已有镜像且断网、只读、非root；源码需固定为上述完整SHA：

```text
python -B -m unittest tests.test_v021_engine_diagnostics -v
python -B -m unittest tests.test_v021_engine_diagnostics tests.test_v021_diagnostic_edges tests.test_v021_native_preservation tests.test_v021_fix_edges tests.test_document_parsing tests.test_dual_engine_policy tests.test_v021_test_batch_authorization tests.test_v021_test_batch_flow tests.test_v021_test_batch_startup_guard tests.test_mineru_api -v
```

本地忽略证据：`local/diagnostics-contract.log`、`local/diagnostics-focused.log`。
补充详情见 [缺陷修复报告](08-缺陷修复报告.md)。报告运输提交仅含Fix报告，不替代业务源码。

请QA独立复验这8项合同、6项新增边界及必要权限/预算控制；本次没有重新执行完整历史套件或真实模型。
Windows系统策略阻塞尚未解决，本地真实引擎BLOCKED、官方真实API NOT_TESTED，双引擎真实验证BLOCKED。
没有外传、修改系统策略、替换解释器、安装依赖、修改Docker/网络、Push或合并；版本闸门保持BLOCKED，等待独立验收与环境处理。

## 运输记录更正

初次报告运输 `d627fa3bc6360f27dede6dfaf0e6be0755b533ba` 的 JSON 中文路径和剩余事项受管道编码影响，
其中空对象哈希不能作为有效证据。本次只更正报告，不改历史或源码；重新验证每个精确 Git 对象存在且内容非空后计算哈希。
QA 另在验证文件 I/O 异常分类边界，当前源码不抢先修改，不以本轮报告更正替代独立验收。
