> ARCHIVED：此文件保留历史设计／执行事实；当前v0.2.1操作入口为 docs/current/v0.2.1-guide.md。

# 复用现有 PostgreSQL 结构

用户已提供本地测试连接并允许本轮接入。现有 document_review schema 能容纳解析结果。
`qa_core/storage/parsing_results.py::PostgresResultSink.save` 只执行 INSERT 和 SELECT，不执行 DDL。
连接通过显式 PARSING_RESULT_PG_DSN 提供，不自动使用 PG_DSN。

| 现有表 | 本轮保存内容 |
| --- | --- |
| documents | 来源 SHA、记录 ID、状态、复核标志、正文、Markdown、原始/标准化 JSON、来源元数据 |
| pages | 原始页码、方法、状态、文本和定位 |
| blocks | 顺序、类型、正文、坐标 |
| tables / cells | 可用的表格结构；远程表格 HTML 和完整 JSON 保留，不假造单元格 |

来源关联含 owner、local_task_id、source_file_id、远程 batch/task/data/file ID、实际解析器版本和模型。
parse_id 由 owner、任务和文件身份确定。ON CONFLICT DO NOTHING 后校验内容摘要；冲突不覆盖历史正文。
一个文件及其全部子记录在同一事务中提交，子记录失败会回滚父记录。
任务恢复数据暂存独立 SQLite，不声称已实现 PostgreSQL 分布式任务队列。

数据库查看：

```sql
SELECT parse_id, file_name, parsing_status, imported_at,
       raw_text, markdown_content, source_location, original_result
FROM document_review.documents
ORDER BY imported_at DESC
LIMIT 20;

SELECT page_number, raw_text, normalized_text
FROM document_review.pages
WHERE parse_id = :parse_id
ORDER BY page_number;
```

本轮没有迁移，无需数据库 schema 回滚。回退应用代码不会删除已有解析记录。
合成事务测试和真实官网合成 PDF 入库均通过。正式生产迁移仍需单独评审授权。
