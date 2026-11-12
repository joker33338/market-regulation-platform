# v0.2.3 多用户身份、角色与审核数据范围设计

状态：READY_FOR_QA（后端候选）。本设计替代draft-1的Token→owner→writers授权方案；不表示正式启用。

## 身份与配置

`principal_id`是实际登录身份标识，`owner_id`是业务数据归属，`roles`是业务角色集合。三者分别存储，不能互相推导。沿用Bearer Token，不新增公开注册、账号管理API或第四套数据库。

仍使用私密runtime中字符串值`PARSING_API_TOKENS_JSON`，其JSON对象每个凭证对应以下记录。下面只展示一个合成记录值，不包含Token或完整凭证映射：

```json
{
  "principal_id": "person-reviewer-01",
  "owner_id": null,
  "roles": ["REVIEWER"],
  "review_owner_scopes": ["data-owner-01"],
  "credential_status": "active"
}
```

- principal_id必须显式且唯一；不同凭证不得重复principal_id。普通USER的owner也不得重复，避免配置静默共享普通用户数据。角色可以显式组合，但ADMIN不隐含REVIEWER。
- owner_id可以为空；USER必须有owner，只有审核角色的人员可以没有个人owner。
- roles只接受USER/REVIEWER/ADMIN；review_owner_scopes必须明确列举合法owner标识，不接受通配符。非REVIEWER的范围列表不产生审核授权。
- credential_status为active/disabled/revoked。停用或撤销凭证返回401。缺失字段、非法角色、重复principal、通配符等配置失败时拒绝加载，不降级放行。
- 凭证仍至少32字符，配置、密码及完整映射不得提交或打印。新增GET `/api/auth/me`仅返回当前身份、owner、角色、范围和凭证状态，不返回凭证。

## 兼容local-user

旧字符串映射兼容为：principal_id=`legacy:local-user`、owner_id=`local-user`、roles=[USER]、审核范围为空、状态active。其他历史字符串配置同样只兼容普通用户，绝不依据数据库writers提升权限。历史数据owner、历史QA标签和原文件不改。

旧MySQL配置中的writers仅允许被读取以避免旧测试配置报错，已完全退出授权计算。初始化工具不再接受--writer，也不再在数据库账号配置中生成业务审核名单。数据库最小权限账号与业务身份角色分别配置。

这是有意的安全不兼容：旧依赖writers启用审核的draft-1客户端必须升级并明确配置REVIEWER及范围；否则写入403。不能把历史owner自动转换成实际人员。

## 权限矩阵

| 能力 | USER | REVIEWER | ADMIN |
|---|---|---|---|
| 有效凭证、读取本人身份及认证公共元信息 | 是 | 是 | 是 |
| 本人owner下文档/任务操作 | 有个人owner | 有个人owner时，仍按原任务规则 | 不因ADMIN获全局权限；个人owner配置也不授审核权 |
| 审核队列、详情、事件、只读结构预览 | 仅自己owner | 自己owner及明确review_owner_scopes | 不隐含全局范围 |
| 原件授权读取 | 仅自己owner | 自己owner及明确审核范围 | 不隐含全局范围 |
| 审核四个写动作 | 403 | 仅明确审核范围 | 403，除非另有显式REVIEWER与范围 |
| 审核审计摘要 | 仅自己owner | 自己owner及明确范围 | 不隐含全局审计访问 |
| 修改别人任务/原OCR、发布ACTIVE | 不授权 | 不授权 | 不因角色而授权 |
| 配置账号/角色/范围 | 无公开修改API | 无公开修改API | 由获准管理员走私密配置运维流程；ADMIN Token本身不等于数据库root或Docker权限 |

审核只读范围与写范围有区别：审核人员可读自己的owner，但写入仍要求目标owner显式出现在review_owner_scopes，不自动允许“审核自己”。没有owner的纯审核员可以读取本人身份、契约、配置/健康、公共法规版本检索及授权审核资料；不能把空owner当作新建上传/任务归属。

## 请求授权和状态码

每个请求重新解析私密认证配置，得到不可变Principal。本轮未提供账号管理API。正式部署默认从实际挂载的/private/runtime.json重读；专用PARSING_AUTH_CONFIG_FILE或测试注入也可用。测试/内部替换必须重新通过完整配置校验。

凭证失效或角色撤销在配置更新完成后的下一请求生效，无缓存放行。已开始执行的请求使用其请求时身份快照，不声称能撤回已经提交的事件。配置写到一半或读取失败时503，不能继续使用旧权限兜底。

未来更新bind挂载的私密文件时，必须核验容器实际读到新内容；不能假设宿主机原子替换文件路径就会更新已有文件挂载。本轮没有修改任何正式文件。

有效写请求依次检查：认证及状态→REVIEWER角色→PG范围限定查询→真实文档owner是否在写范围→台账健康→原始结果身份/内容绑定→幂等和版本锁。普通用户或只有ADMIN的有效写请求403；审核人员越界404；Token无效401；body伪造operator_id/owner_id等额外字段422；冲突409；未配置/存储故障503。

PG只读查询在SQL内按owner相等或ANY参数化数组限定，空范围使用FALSE，拒绝先全局查对象再仅依赖前端隐藏。后端还核验返回行owner。任务存储和上传归属继续使用owner字符串；Principal对象不会写进旧SQLite owner列。

## MySQL事件与幂等

新事件JSON增加operator_id（实际principal_id）、owner_id（PG源文档归属）、identity_model=principal-v1；兼容operator字段改为实际principal_id别名。action、event_id、revision_id、timestamp、version及原始结果保护回执保持。

审核头记录和版本锁仍按文档owner+parse_id共享，两个审核员写同一文档仍竞争同一版本。幂等键按数据owner+principal_id+客户端键隔离；同人同键同body返回原回执，同人同键异请求409，不同人复用键不会拿到对方回执。

不执行MySQL ALTER或历史UPDATE/DELETE：身份字段保存于现有事件JSON，独立库schema仍为版本1。旧事件不补认实际人员，operator原值保留；typed事件/回执对旧事件提供operator_id/owner_id=null及identity_model=legacy-owner的响应默认值，不篡改存储。

审批只追加台账，不覆盖OCR或原件，不改变PG requires_review，不自动创建重解析任务或发布知识库。旧事件的旧幂等命名空间不迁移，客户端升级应使用新的操作键，不借用旧回执推断新审核员身份。

## 契约与前端影响

最新离线契约为docs/integration/frontend-openapi-v023-draft2.json，info.version仍0.2.3-dev，x-contract-version=frontend-api-v0.2.3-draft-2，30路径。draft-1及v0.2.2快照均保留。

前端可读取/api/auth/me展示实际身份和角色，但最终写权限仍以后端review_write_supported、review_ledger.available及每次写请求校验为准。回执应展示operator_id和owner_id，不能把owner称作实际审核员。事件正文仍在event.request.content/reason/page，不扁平化。前端3b7b62f版本此前的事件层级问题仍须其负责人修正，本轮不替换前端源码或声称联合UI验收通过。

## 风险和正式边界

这是私密配置驱动的RBAC，尚无公开注册、凭证签发/轮换界面、密码登录或个人实名认证。本机管理员必须确认实际人员与principal_id的对应，独立管理凭证。多人共用同一Token仍无法精确到人，不得以新字段宣称已解决共享凭证的人身归属。

同一principal当前只允许一条配置凭证；轮换需受控替换条目，不能通过新增重复principal绕过校验。跨owner上传/任务修改、全局审核、角色隐式继承均未授权。

正式market_review、正式角色配置、runtime注入和8180更新仍须另行明确授权。本轮不创建正式库、不修改writers、不重启、不改ACTIVE、不清理测试证据。
