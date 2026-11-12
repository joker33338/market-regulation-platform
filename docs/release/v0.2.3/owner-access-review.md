> 历史draft-1记录保留。最新principal/RBAC设计与验收请见 [身份设计](identity-rbac-design.md) 和 [RBAC QA交接](rbac-qa-handoff.md)；旧writers建议不再适用。

# v0.2.3 正式审核启用前：owner与权限只读核查

日期：2026-11-12。用户已明确暂不授权创建正式market_review、开放正式审核写入或修改正式runtime。本报告只记录只读核查与候选建议，不授予任何权限。

## 1. 当前真实映射及数据归属

仅在容器内部读取私密runtime的Token→owner映射，只输出owner和凭证条目数量；未输出、复制或提交Token。查询SQLite任务和PostgreSQL解析结果时使用只读连接。

| owner标识 | 当前runtime凭证条目 | SQLite任务 | PostgreSQL解析记录 | 能确认的身份及来源 |
|---|---:|---:|---:|---|
| local-user | 1 | 5 | 9 | 当前唯一已配置认证身份；权限来自私密runtime中的Token→owner映射。不是已核验的个人账号，也不能凭名称认定为管理员或审核员 |
| synthetic-qa | 0 | 0 | 15 | 历史QA数据归属标签；当前无对应认证映射 |
| qa-release-alice | 0 | 0 | 3 | 历史QA数据归属标签；当前无对应认证映射 |
| synthetic-dual-qa | 0 | 0 | 10 | 历史合成测试归属标签；当前无对应认证映射 |
| 空值 | 不适用 | 0 | 1 | 历史记录缺少owner；不自动补齐、迁移或分配权限 |

以上是可在现有认证配置和数据记录中观察到的owner，不是用户注册表。历史记录存在某个owner不表示该owner当前可以登录，更不表示有审核权限。候选测试使用的alice/bob仅为合成身份，不属于正式runtime账号名单。

## 2. 三类权限必须分开

| 类别 | 现有实现 | 权限来源及边界 |
|---|---|---|
| 普通认证用户 | 有效Bearer Token映射到owner | 允许既有业务接口；任务、原件、审核详情按owner隔离；不是全部只读，也没有自动审核写权限 |
| 审核写入者 | v0.2.3候选新增writers白名单 | 必须先通过Token认证、PG对象owner校验，再匹配服务端writers，且独立MySQL台账可用。未在writers中返回403，跨owner仍404 |
| 管理员/部署操作者 | 没有对应的Web管理员角色或登录接口 | 本机管理员安全提供初始化所需数据库管理员配置；执行DDL及账号授权。不能把数据库root或运维权限当成API用户，API禁止root账号 |

当前认证实现位于qa_core/document_parsing/mineru_api.py：比对静态Bearer凭证后返回owner，没有用户注册表、个人账号绑定、审核员角色表或平台管理员角色映射。不能从mysql用户名、数据库root、owner字符串或历史QA标签反推人的身份。

## 3. 最小白名单建议

**当前建议writers保持空列表，正式审核写入继续关闭。** 用户尚未确认任何人员，正式runtime也不存在REVIEW_MYSQL_CONFIG_JSON，正式market_review库不存在。

如后续确认现有local-user凭证确实由指定审核人员独占使用，并明确批准其审核自己owner下的记录，最小候选白名单才是 `["local-user"]`。这只是待审批建议，本次没有配置或启用。

不能把synthetic-qa、qa-release-alice、synthetic-dual-qa、测试alice/bob或空owner加入正式白名单。不能默认“有Token就有审核权”，也不能把所有历史owner整体放行。

若local-user凭证由多人共享，当前审计operator只能记录local-user，无法区分实际操作者。简单新增第二个Token但仍映射到同一owner，也不能实现普通用户与审核人员的独立授权，因为当前写权限基于owner。需用户先确认独占使用，或另行设计独立操作者身份/角色和数据owner授权关系。

若创建新的reviewer-owner，它也不能直接审核现有local-user数据；当前实现禁止跨owner。不得以修改旧数据owner或放开全局查询绕过此限制。多人分权/跨owner审核需要另行确认授权模型，不能由本次台账启用静默扩展。

## 4. 正式初始化前必须由用户确认

1. 是否允许创建全新market_review数据库及独立最小权限账号。
2. 哪些实际人员担任审核者，其受控凭证对应哪个owner；是否存在多人共用。
3. 明确writers列表，接受其仅能审核同owner对象的边界。
4. 管理员在本机安全提供REVIEW_MYSQL_ADMIN_JSON，不能发到聊天或入Git。
5. 独立QA通过候选后，再单独批准正式配置注入与8180切换。

未满足这些条件前，不能创建正式库、注入正式账号、改变runtime或重启8180。当前状态为等待最终授权，不是正式启用成功。
