"""Transactional writer for an existing document_review schema; never executes DDL."""
import hashlib
import json

from qa_core.utils import stable_hash
from qa_core.document_parsing.mineru_client import MinerUError


class PostgresResultSink:
    def __init__(self, dsn):
        self.dsn = dsn

    def save_import(self, owner_id, batch_id, file_id, result):
        """管理员离线资料接收：只存待复核解析，不伪造队列任务或人工审核。"""
        import re
        from qa_core.api.principals import identifier
        from qa_core.document_parsing.schemas import DocumentResult
        if not identifier(owner_id) or not identifier(batch_id) or not re.fullmatch('[a-f0-9]{32}',file_id):
            raise MinerUError('invalid_import_identity',422)
        pending=DocumentResult.from_dict(result.to_dict())
        pending.requires_review=True
        if pending.parsing_status=='success':
            pending.parsing_status='needs_review'
        pending.quality.update(import_batch_id=batch_id,human_verified=False)
        return self.save({'owner':owner_id,'id':batch_id},{'id':file_id,'source_file_id':file_id},
                         pending,import_batch_id=batch_id)

    def save(self, task, file, result, *, import_batch_id=None):
        import psycopg2
        from psycopg2.extras import Json
        payload = result.to_dict()
        payload["source_location"].update(owner_id=task["owner"],
                                          source_file_id=file.get("source_file_id", file["id"]))
        if import_batch_id:
            payload['source_location'].pop('local_task_id',None)
            payload['source_location']['import_batch_id']=import_batch_id
        else:
            payload['source_location']['local_task_id']=task['id']
        # 即使页面渲染不同，也保留远端原始 Markdown。
        markdown = result.quality.get("markdown", result.markdown_content)
        digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        parse_id = stable_hash("import-result-v1" if import_batch_id else "parsing-result-v1", task["owner"], task["id"], file["id"])
        connection = psycopg2.connect(self.dsn, connect_timeout=5, application_name="market_parsing_results")
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute("""INSERT INTO document_review.documents
                        (parse_id,document_id,report_sha256,file_name,file_type,parsing_status,requires_review,
                         source_location,quality,raw_text,markdown_content,original_result)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(parse_id) DO NOTHING""",
                        (parse_id, result.document_id, digest, result.file_name, result.file_type,
                         result.parsing_status, result.requires_review, Json(payload["source_location"]),
                         Json(result.quality), result.raw_text, markdown, Json(payload)))
                    if cursor.rowcount == 0:
                        cursor.execute("SELECT report_sha256 FROM document_review.documents WHERE parse_id=%s", (parse_id,))
                        if cursor.fetchone()[0] != digest:
                            raise MinerUError("database_result_conflict", 409)
                        return parse_id
                    for page in result.pages:
                        cursor.execute("""INSERT INTO document_review.pages
                            (parse_id,page_number,parsing_method,parsing_status,raw_text,normalized_text,markdown_content,
                             confidence,warnings,source_location,raw_result,processing_seconds)
                            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (parse_id,page.page_number,page.parsing_method,page.parsing_status,page.raw_text,
                             page.normalized_text,page.markdown_content,page.confidence,Json(page.warnings),
                             Json(page.source_location),Json(page.raw_result),page.processing_time))
                        for index, block in enumerate(page.layout_blocks):
                            cursor.execute("""INSERT INTO document_review.blocks
                                (parse_id,page_number,block_index,source_block_id,kind,raw_text,bbox,confidence,
                                 reading_order,source_location) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                                (parse_id,page.page_number,index,block.block_id,block.kind,block.raw_text,
                                 Json(block.bbox) if block.bbox is not None else None,block.confidence,
                                 block.reading_order,Json(block.source_location)))
                        for index, table in enumerate(page.tables):
                            cursor.execute("""INSERT INTO document_review.tables
                                (parse_id,page_number,table_index,source_table_id,html,markdown,table_rows,row_count,
                                 column_count,bbox,source_location,warnings) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                                (parse_id,page.page_number,index,table.table_id,table.html,table.markdown,Json(table.rows),
                                 len(table.rows),max(map(len, table.rows),default=0),
                                 Json(table.bbox) if table.bbox is not None else None,Json(table.source_location),Json(table.warnings)))
                            for cell_index, cell in enumerate(table.cells):
                                cursor.execute("""INSERT INTO document_review.cells
                                    (parse_id,page_number,table_index,cell_index,row_index,column_index,row_span,column_span,
                                     cell_text,is_header,bbox,source_location,original_cell)
                                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                                    (parse_id,page.page_number,index,cell_index,cell["row"],cell["column"],
                                     cell.get("rowspan",1),cell.get("colspan",1),cell.get("text",""),cell.get("header",False),
                                     Json(cell["bbox"]) if cell.get("bbox") is not None else None,
                                     Json(cell.get("source_location",{})),Json(cell)))
            return parse_id
        finally:
            connection.close()
