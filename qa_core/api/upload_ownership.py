"""从元数据、已知任务或解析来源核对历史上传owner，绝不按当前管理员猜测。"""
import hashlib

from .principals import identifier
from qa_core.access import is_all_owners
from qa_core.document_parsing.mineru_client import MinerUError


def upload_owner(reader, identity, upload, path):
    directory = path.parent.name
    def matches(value):
        return identifier(value) and hashlib.sha256(value.encode("utf-8")).hexdigest() == directory
    explicit = upload.get("owner_id")
    if explicit is not None:
        if not matches(explicit):
            raise MinerUError("source_owner_mismatch", 409)
        return explicit
    scopes = identity.read_owners
    if not is_all_owners(scopes):
        known = [value for value in scopes if matches(value)]
    else:
        known = [value for value in getattr(reader, "known_owner_ids", lambda: [])() if matches(value)]
        if not known:
            known = [task["owner"] for task in reader.service.repository.owned_tasks(scopes)
                     if matches(task.get("owner")) and
                     any(file.get("source_file_id") == upload["file_id"] for file in task["files"])]
        if not known and reader.review is not None:
            with reader.review.cursor() as cursor:
                cursor.execute("SELECT DISTINCT source_location->>'owner_id' AS owner_id FROM document_review.documents WHERE source_location->>'source_file_id'=%s",
                               (upload["file_id"],))
                known = [row["owner_id"] for row in cursor.fetchall() if matches(row["owner_id"])]
    known = set(known)
    if len(known) != 1:
        raise MinerUError("source_owner_unresolved", 503)
    return next(iter(known))
