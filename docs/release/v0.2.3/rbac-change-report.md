# v0.2.3 多用户审核权限调整结果

日期：2026-11-12。状态READY_FOR_QA。独立开发分支codex/backend-improvements-v023；只完成身份与授权架构，不启用正式MySQL审核写入。

## 基线核对

执行起点a17bbeeb83130bc9d33b96c8085eceb0af58f3c2；本地main为076d4f968aa2c71133c551007b5d082da96a5929。Git网络读取失败后，使用GitHub只读compare API核实076d4f9与当前远程main为identical，ahead/behind均0。本次实际核查未发现main已偏移，没有重置、覆盖、合并或推送。正式镜像source/OCI 30c4663与main076d4f9的差别是此前收尾归档链，未据此更改版本历史。

实现完整SHA b96c34901f783cd136235663d20ccef6cc62a019；后续文档提交不改变候选代码。设计、字段、配置、角色矩阵见identity-rbac-design.md；QA见rbac-qa-handoff.md。

## 交付文件范围

- qa_core/api/principals.py：身份、私密映射校验、状态与动态配置重核。
- qa_core/document_parsing/mineru_api.py：认证身份依赖与独立owner依赖，GET /api/auth/me。
- qa_core/api/review_rbac.py、review.py、review_writes.py、read_store.py：RBAC、文档范围、能力与写授权。
- qa_core/api/documents.py、knowledge.py、common.py、frontend.py、monitoring.py：保持原任务owner存储并允许授权审核范围的原件/只读预览；元信息认证不要求个人owner。
- qa_core/storage/mysql_review_ledger.py：实际operator_id、目标owner_id、按principal隔离幂等键，保留共享文档版本锁。
- scripts/provision_review_mysql.py：独立DB账号初始化不再配置writers；没有实际正式执行。
- docs/integration/frontend-openapi-v023-draft2.json：新版30路径契约，不覆盖draft-1或v0.2.2冻结契约。
- tests/test_principal_rbac.py及已有回归/工具测试、镜像runtime检查器：61项通过。

## 正式保护核实

正式8180仍market-regulation-app-1，ID b23198928dda0e75ff7ad40d3ce8170da825cb81922526a1db65e8b5815621c1；镜像ID sha256:e2a94f67ffacef9e780e06bc1484cb5e7dde4b287fa5ef340a666f5e573e52a3；启动时间2026-11-12T00:54:43.04620371Z，healthy。正式market_review库存在性只读查询结果0。本轮不触碰正式Token映射、MySQL配置、writers、runtime、SQLite任务或PG ACTIVE，不清理旧库或证据。

新候选镜像和完整身份在QA交接中记录。它只用于无端口、短生命周期隔离测试，没有形成第二套长期服务，没有覆盖任何既有候选或v0.2.2回滚标签。

## 兼容性和遗留

旧字符串映射只兼容普通用户；旧writers授权被取消。当前已知local-user一条配置无需数据迁移。多Token共享owner/principal的旧配置需管理员明确拆分，不能静默提升或迁移历史数据。历史MySQL事件不能补认具体人员，保持原内容，新增事件才有principal身份。

本轮没有实现公开账号注册、管理员配置页面或实际人员认证；私密配置运维仍需要授权。新前端适配、事件request层级修正及浏览器正向联验不在本次后端候选通过范围。正式建库/身份名单/独立QA/部署授权均未完成，不能宣称READY_FOR_RELEASE或RELEASED。
