# v0.2.1 TEST_BATCH 授权边界正式交接

冻结业务源码：`6216ae5f40727871b369dfc8c54868ac748c4648`。这是用户新增功能范围，不将实现前的契约红测谎报为既有生产功能安全缺陷。

## 七项验收与补充边界

1. 仅服务端可信批次授权可使明确合格的当前文件上传。
2. 批次外SHA不能使用此授权，路径在测试集内也不能自动获准。
3. 字段SHA变化或实际字节变化均重新拒绝，不相信调用方自报SHA。
4. 批次过期立即失效，每次网络请求前重新读取验证。
5. 敏感、敏感状态未知、第三方外传权或来源未确认均拒绝；不能用labels或人工识别标准替代披露许可。
6. HTTP副本只有相同已批准SHA且任务由服务端绑定正确owner/batch才可用；自报批次、路径、清单无效。
7. 用户不能伪造batch_id授权其他文件。

补充：production默认FILE_SHA与原corpus拒绝不变；TEST_BATCH仅test环境；撤销实时生效；owner隔离；未知/非布尔字段和重复SHA拒绝。恢复已有任务不改绑新批次。

## 约定接口

`test_batch_authorization.TrustedTestBatch(manifest_path, *, owner, batch_id)`：路径仅服务端配置提供，不能来自HTTP。
`bind_task(task)`仅新任务服务端调用，持久化authorization_context={mode:TEST_BATCH,owner,batch_id}；同上下文幂等，不同上下文不得覆盖。
`authorize(task,file)`返回(bool,reason_or_id)，成功ID为TEST_BATCH:<batch_id>，每次重读清单与实际file_sha256。
`reserve_request(task,file,method)`在实际每一请求前重新验权后扣账，清单旁私有持久总账按owner+batch累计，进程锁与原子写；跨task/strategy/resume/重启最多32调用、最多3个唯一SHA。达到预算BLOCKED，不换ID或重置绕过，不确定POST已占用额度不返还。

清单version=1、batch_id、owner、expires_at有限实数、revoked严格false；entries唯一SHA，每项source_qualified/sensitivity_confirmed/third_party_transfer_rights_confirmed严格true、sensitive严格false、source_evidence非空。清单由服务端operator保护路径和写权限，HTTP请求不能注入或选择。动态撤销不使用固定文档digest缓存。
DualEngineConfig新增environment=production、authorization_mode=FILE_SHA默认；只有test可选TEST_BATCH。DualEngineRouter注入batch_authorizer；MinerUService服务端绑定任务；原HTTP parse_options字段白名单不扩大。每个HTTP边界（含重定向）保留原origin白名单、完整性、取消和预算守卫；限速等待之后再复验授权/字节，不能发生撤销等待竞态。

## QA契约和真实阶段限制

新增23个无网络合成边界方法，涵七项及生产/撤销/owner/清单/持久预算。实现前缺TEST_BATCH模块与config参数是预期红测；现有production/HTTP白名单控制应通过。修复后须全部通过，并补实际服务端持久绑定、撤销限速竞态和真实ASGI上传副本集成的Mock路径。

真实批次范围只包含01～12的当前19个正常候选，6异常负例排除。用户已确认当前批次自有并允许外传，不再重复逐文件申请；仍需将敏感性/来源证据逐项可信落地，未知不能变false。Key仅在本地配置，不能复制进报告或清单。首轮顺序最多3个文件，auto/remote共用同一总账，真实上传必须待独立边界Mock及root资格放行，不能自行替换其他未批准文件。

不改变全局production默认、不取消既有文件/页/请求上限、不安装依赖或下载模型、不Push/合并main/部署/迁移。标准答案变化和真实指标审计由QA负责，Fix不把模型输出当真值。
