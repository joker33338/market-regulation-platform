# v0.2.3 前端适配交接：后端契约核对

日期：2026-11-12。依据用户指定的frontend-v023-adaptation-2026-11-12.md及agent-c-backend-improvement-handoff-2026-11-12.md；核对的是实际前端业务提交 `3b7b62f6373509ee5da2bbccb89bca67e54583ee`，不是仅采信报告。

状态：前端仍ADAPTATION_PREPARED / NOT_LIVE_VERIFIED。尚未合入联合候选或更新8180，不签发前端QA PASS。此前纯后端隔离候选的证据保留其原镜像/源码范围。

## 1. 已核对一致的内容

- 七条新增路径与后端29路径契约一致，四个写请求携带Idempotency-Key、base_result_id、expected_version，不由客户端指定operator。
- 写按钮要求运行期四路径存在、详情review_write_supported=true、review_ledger.available=true。当前正式8180的22路径无法通过第一道门，不会因前端源码交付提前授权。
- 修订提交不trim正文，页面使用插值/pre呈现不可信文本；回执没有把批准当发布或自动重解析。
- 文档筛选、进程资源、审核审计和统计不可用原因已有请求/类型适配。正向联验仍不能从源码或只对v0.2.2的浏览器测试推断为通过。

## 2. 阻止联合前端验收的契约不匹配

**FRONTEND-V023-C01：审核事件的正文/理由/页码读取层级不一致。**

真实GET `/api/review/{parse_id}/events` 返回：

```json
{
  "list": [{
    "event_id": "<event_id>",
    "action": "save-revision",
    "request": {
      "base_result_id": "<parse_id>",
      "expected_version": 0,
      "page": 1,
      "content": "人工修订正文",
      "reason": "",
      "span": null
    }
  }]
}
```

说明性样例省略其余回执字段。实际结构是完整回执加request，不把请求字段扁平放到顶层。后端此前交接亦说明事件包含原请求。

前端实际代码：

- frontend/src/api/types.ts 的ReviewEvent将reason/page/content定义为顶层可选字段，未定义正式request结构。
- frontend/src/api/reviewWrite.ts 的getReviewEvents直接返回响应，没有扁平映射。
- frontend/src/views/ReviewView.vue 的事件表读取row.content/row.reason，latestRevision读取e.content，因此实际event.request.content不会被正确显示为最近修订，理由与页码同样受影响。

已在真实隔离MySQL+TestClient实证：顶层content=false、request.content=true；顶层reason=false、request.reason=true。仅输出字段存在性，没有保存真实正文或凭据。此结论不冒充浏览器回归。

前端建议修正：ReviewEvent增加 `request: ReviewActionBody`（或独立只读类型），事件表/最近修订读取row.request.content、row.request.reason、row.request.page；也可在唯一请求适配层明确转换，但必须保留真实来源且不伪造修订。不要改后端审计存储或让客户端猜字段。

后端已补充ReviewEvent、ReviewEventsResponse显式OpenAPI Schema，将request设为必填，content/reason/page定义在ReviewAction内；**实际HTTP层级没有改变**。新增防漂移断言验证嵌套正文和Schema。离线frontend-openapi-v023.json已更新，仍29路径，避免通用dict掩盖这种不匹配。

## 3. 建议前端同时检查的失败重试语义

前端报告称失败重试沿用同键同body，但当前submitAction每次重新读取可编辑form和计算得到的expectedVersion，未冻结首次提交的请求。若失败后改正文/理由或详情刷新导致版本变化，仍使用旧键，会触发后端正确的idempotency_conflict。建议首次提交冻结action/parse_id/body；同一次未知结果重试使用同快照，主动修改内容则明确作为新操作换键。该项为代码审阅建议，尚未浏览器复现。

503提示“本次未执行写入”也不宜一概保证。数据库提交确认丢失等通信故障下，客户端可能无法确认事务结果，应提示结果未确认并使用同键同请求重试，而不是据错误码推导绝对没有写入。后端幂等记录正用于这种恢复场景。

## 4. 联合候选下一步

1. WorkBuddy在自身分支提交事件层级修正，核对重试语义；不修改后端或正式服务。
2. 明确最终前端完整SHA，再在后端开发分支集成，类型检查/构建并记录前端revision。
3. 基于新的前后端冻结源码生成新唯一候选标签；不覆盖之前候选，也不混用旧前端63bbcc0与新3b7b62f的测试结论。
4. 独立QA用获准隔离数据检查正向双门控、四写动作、事件正文/理由/页码、幂等及权限；浏览器写按钮尚未验证，需按现有授权边界执行。
5. 正式建库、writers与runtime仍须用户最终授权。当前writers建议为空，正式market_review不创建、8180不切换。

本轮后端契约明确化后45项测试通过（含真实MySQL隔离、API、初始化工具安全测试），不等于新增联合前端QA_PASS。未推送、未合并main、未构建/部署新的联合镜像。
