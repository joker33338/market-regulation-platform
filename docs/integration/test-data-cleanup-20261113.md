# 2026-11-13 旧测试解析数据清理记录

用户明确要求删除之前导入的测试数据，保留本批法规，并明确要求不新增备份。本次按该授权直接执行 PostgreSQL 数据清理，没有新建备份，没有修改源码或服务配置。

## 范围与校验

目标为现有 market_regulation 数据库。清理前 document_review.documents 共169条，其中 law-import-20261113 批次121条、旧记录48条。已核对旧48条未被 business_library.records 引用，market_review 的 review_events、review_heads 中对应 parse_id 引用均为0。SQLite 当时无活动任务。

保留名单来自本批实际接收回执的121个 parse_id，不依赖文件名猜测。一个 SERIALIZABLE 事务按外键顺序删除旧记录及其子数据，设置锁等待/语句超时；数量变化或保留数据摘要不一致即报错回滚。未使用 TRUNCATE 或 CASCADE，未删除表或数据卷。

| 删除对象 | 实际删除行数 |
|---|---:|
| document_review.documents | 48 |
| document_review.pages | 208 |
| document_review.blocks | 3,669 |
| document_review.tables | 32 |
| document_review.cells | 1,745 |
| document_review.images | 33 |
| document_review.findings | 43 |

事务已实际 COMMIT。保留的本批解析及其子表、business_library 六张表、public 八张相关表共21个关系范围，清理前后逐行摘要聚合均相同。清理后通过 DBX 连接再次独立只读确认：

| 保留内容 | 实际数量 |
|---|---:|
| 旧测试解析 | 0 |
| 本批解析接收 | 121 |
| 法规目录 | 117 |
| 章节候选 | 1,942 |
| 条款候选 | 10,618 |
| 本批零页 PDF 异常接收 | 4 |
| ACTIVE | 0 |

四条零页 PDF 为本次法规导入的异常记录，属于当前批次而非旧测试数据；不计入117条有效法规目录。法规仍为未索引、待复核、未发布，没有借数据清理改变审核或发布状态。

本次只清理上述 PostgreSQL 旧测试业务记录；SQLite 历史任务、文件存储原件、MySQL 追加式审核历史、既有备份、隔离测试库和模型不在本次操作范围。没有重启/替换8180、Push、Merge或打Tag。操作性数据清理不作为独立QA_PASS。

精确SQL及执行回执在 backend-api 工作区 ignored local/test-data-cleanup-20261113/，不包含正文或原文件名。此前[资料接收报告](law-import-20261113-handoff.md)中的旧48条保留状态为接收当时快照，以本清理记录作为后续变化说明。
