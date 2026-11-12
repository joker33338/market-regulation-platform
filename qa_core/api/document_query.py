"""基于真实上传元数据进行稳定排序与带时区的闭区间筛选。"""
from datetime import datetime
from qa_core.document_parsing.mineru_client import MinerUError


def validate_window(date_from, date_to):
    if any(value is not None and value.utcoffset() is None for value in (date_from, date_to)):
        raise MinerUError("timezone_required", 422)
    if date_from is not None and date_to is not None and date_from > date_to:
        raise MinerUError("invalid_date_range", 422)


def select_documents(rows, date_from, date_to, sort_by, order):
    validate_window(date_from, date_to)
    def timestamp(row):
        return datetime.fromisoformat(row['uploaded_at'])
    selected = [row for row in rows if (date_from is None or timestamp(row) >= date_from)
                and (date_to is None or timestamp(row) <= date_to)]
    # 先固定同值项的次序，避免分页出现不确定顺序。
    selected.sort(key=lambda row: row['file_id'])
    selected.sort(key=lambda row: timestamp(row) if sort_by == 'uploaded_at' else
                  row[sort_by].casefold() if isinstance(row[sort_by], str) else row[sort_by],
                  reverse=order == 'desc')
    return selected
