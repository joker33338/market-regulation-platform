# v0.2.3 draft-4 独立 QA 任务

日期：2026-11-12，Asia/Shanghai。开发交付状态 BACKEND_API_PARTIAL，等待独立 QA。不得直接沿用旧软删除、旧 RBAC 或开发方成绩签发整版 PASS。

## 冻结受测对象

- 源码 / OCI：f21e9861c2fddca9b0643cf4619e485332859f5a。
- 标签：market-regulation-workbench:candidate-v023-api-f21e9861-f7bc2ec。
- 镜像 ID：sha256:04d0751efdd07af419d516c9ed4bdb7c14c1bdf38bc660a1b188e37a1951ed4e。
- 固化前端：7bc2ec3e6dc342430570734d5339b0f9ed0db038。
- HTTP：frontend-api-v0.2.3-draft-4，46 路径，owner_id 管理员选择参数已声明。
- 正式 8180 仍为 market-regulation-app-1 / sha256:e2a94f67ffacef9e780e06bc1484cb5e7dde4b287fa5ef340a666f5e573e52a3 / OCI 30c4663ceb93cbba302b322f1ecee0d06d80bfb4，不是本轮写入测试对象。

范围、请求字段和边界见 [接入包](frontend-v023-draft4-backend-handoff.md) 与 [角色方案](v023-account-role-design.md)，完整 schema 见 frontend-openapi-v023-draft4.json。

## 权限政策变更

用户已明确 ADMIN 全部业务权限。本轮应验收 ADMIN 可以跨 owner 审核、访问源文件、管理任务、软删除、构建及发布，不能再用旧“ADMIN 非 REVIEWER 必须 403”当正确结果。USER/REVIEWER 仍不得获得全局权限，证据链/质量/并发门禁对 ADMIN 仍有效。

前端冻结版仍有旧 ADMIN 审核按钮限制和 Token 登录页面；不能因此宣称新版密码登录 UI 已完成。WorkBuddy 新 UI 对接后，应另记该前端 SHA 和新组合镜像 ID，再签对应 UI 范围。

## 独立用例

1. 密码登录正确/错误/未知用户名、非法字段、限流；响应禁止缓存，不回显密码/哈希，Token 不落盘明文。
2. USER、REVIEWER、ADMIN 三类独立账号；两个普通用户隔离，不能靠 username/owner/roles 请求体伪造身份。
3. ADMIN 全局读取、跨 owner 审核与任务操作；目标 owner 参数在 OpenAPI 中存在，非 ADMIN 显式选择被拒绝。
4. 管理员创建账号、改角色/审核范围、重置密码、停用/撤销；普通用户 403；最后有效管理员保护；既有 owner 不可偷偷改写。
5. 旧会话在密码重置/停用后下一请求 401；角色撤销立即影响写操作；退出会话失效；旧 Token 兼容但不能假称已被 logout 全局撤销。
6. 审核原有四动作、事件、幂等和 expected_version；两个不同人员 operator_id 不同、owner_id 相同；原始 OCR 不修改、不自动重解析或发布。
7. 日志只含模板/方法/状态/耗时，不能含凭证、查询串、正文、真实对象路径或堆栈；匿名 principal=null，不能伪装成实际用户；普通人只看自己，ADMIN 可全局看。
8. 任务日志只记录真实状态变化；重复保存不增假事件；历史无日志明确 available=false，截断有标识，时间参数需时区。
9. 入库预检只读、逐项诊断，未审核/版本不符/源摘要或字节变化拒绝；不把 200 eligible=false 当构建成功。
10. ADMIN 构建 STAGED 与幂等回执、阶段已知/未知计数、失败及超时不确定态；缺知识库写连接 503，不能借解析读连接开启写入。
11. 发布/回滚 expected_active_version 并发冲突、幂等、PG 历史 event_id 恢复、审核撤回互斥；原始库/审核事件不变。
12. 表格、未完整解析、尚未确认的人工修订导出、缺审核来源绑定的旧版本保持 409；ADMIN 不能绕过。
13. keyword/hybrid、版本及机关/效力精确筛选；未发布版本不开放，历史已发布版本可查，筛选先于排序限额；无 ACTIVE 的默认查询合法空态。
14. 软删除原保护矩阵在新版仍成立；ADMIN 跨 owner 成功，USER/REVIEWER 403，活动/历史解析及版本引用 409，重复/详情/历史/原件 404，原字节保留。

## 环境与自测范围

全部写用例只用合成身份、临时 SQLite、全新独立 PG 容器、market_review_test_ 前缀 MySQL；不使用真实人员凭证，不触碰正式库/ACTIVE、SQLite 历史、授权预算或 8180。

开发方最终镜像成绩：132 个 pytest 方法通过，25 subtests；独立 PG/MySQL 全链路 1 方法通过，真实 PG 删除保护 6 方法通过，合计 139 个不同方法、0 跳过。HTTP 登录/权限/删除探针另计，不与方法数相加。同一镜像还完成 7 个真实浏览器删除场景自测；不包含尚未实现的密码表单或账号管理 UI，不代替独立 QA。

PG 全链路运行账号为逐表授权：原始 document_review 只读，公开知识库仅所需 DML，发布历史不可 UPDATE/DELETE，不授予 public CREATE；同时实际验证构建、发布和回滚仍可成功。MySQL 使用既有非 root 隔离账号。

全链路向量为明确的合成 1024 维测试向量，用来验证真实 PG vector/事务与服务编排，不是 BGE-M3 正式推理质量验证，不代表真实云 OCR 已测试。真实模型资源若要纳入验收，应只读挂载既有模型，在隔离状态另行记录范围，不触发云探测。

候选校验插件 tests/candidate_source_provenance.py 对 83 个源文件/入口核对冻结 Git 对象；仅规范 CRLF/LF，不忽略其他差异。测试只读挂载，业务从镜像加载，不挂载宿主 qa_core。后续 QA 报告记录实际测试辅助提交 SHA，不把文档 HEAD 当 OCI。

可复用测试：test_password_accounts、test_principal_rbac、test_mysql_review、test_frontend_missing_apis、test_ingestion_api、test_frontend_workflow_pg、test_document_delete、test_document_delete_pg，以及原接口/发行保护回归。真实 PG 类初始化只允许空 qa_round01 临时库，发现既有 Schema 立即拒绝，不能清库重跑；使用新容器和新名称。

私密配置不入 Git。开发证据保留于 backend-api 工作区 local/frontend-api-v023/final/；请独立执行并记录自己的实际范围，不累加重复运行或直接复制开发方 139 作为 QA 成绩。

## 放行规则

独立结论可按后端接口范围签发，UI 未对接项目必须 NOT_TESTED，不能扩大为整版前后端 PASS。只有新 UI 和受测镜像身份一致并实际验收，才能签对应联合范围。QA 不重建业务镜像，Agent C 不在 QA 中静默替换镜像；正式启用及切换仍等待用户最终许可。
