"""整页修订生成审核正文副本，不写回任何原始解析记录。"""
from copy import deepcopy

from qa_core.document_parsing.mineru_client import MinerUError
from qa_core.document_parsing.schemas import DocumentResult, LayoutBlock


def export_reviewed_result(source, state, ledger, owner):
    result = DocumentResult.from_dict(deepcopy(source["original_result"]))
    if not state.get("current_revision"):
        return result
    events = []
    page = 1
    while True:
        response = ledger.events(owner, source["parse_id"], page, 100)
        if "total" not in response:
            raise MinerUError("reviewed_revision_export_required", 409)
        current = response["list"]
        if not current:
            break
        if any(event["version"] > state["version"] for event in current):
            raise MinerUError("review_version_conflict", 409)
        events.extend(current)
        if len(events) >= response["total"]:
            break
        page += 1
    revisions = [event for event in events if event["action"] == "save-revision"]
    if not revisions or revisions[0].get("revision_id") != state["current_revision"]:
        raise MinerUError("reviewed_revision_export_required", 409)
    latest = {}
    for event in revisions:
        body = event.get("request", {})
        number = body.get("page")
        if number in latest:
            continue
        if body.get("revision_scope") != "page_body_v1" or not event.get("operator_id"):
            raise MinerUError("reviewed_revision_export_required", 409)
        content = body.get("content")
        if not isinstance(content, str) or not content.strip() or any(ord(c) < 32 and c not in "\n\r\t" for c in content):
            raise MinerUError("invalid_page_revision", 409)
        latest[number] = event
    pages = {page.page_number: page for page in result.pages}
    if not latest.keys() <= pages.keys():
        raise MinerUError("review_page_not_found", 409)
    provenance = []
    for number, event in sorted(latest.items()):
        page = pages[number]
        content = event["request"]["content"]
        protected = [block for block in page.layout_blocks if block.kind in
                     {"table", "image", "header", "footer", "number", "footnote"}]
        location = {"page": number, "revision_id": event["revision_id"], "revision_scope": "page_body_v1"}
        block = LayoutBlock("reviewed-page-" + str(number), "text", content, source_location=location)
        page.layout_blocks = [block, *protected]
        page.raw_text = "\n".join(block.raw_text for block in page.layout_blocks)
        page.normalized_text = content
        page.markdown_content = content
        page.source_location = {**page.source_location, **location}
        provenance.append({**location, "operator_id": event["operator_id"], "version": event["version"]})
    result.quality["reviewed_page_revisions"] = provenance
    return result
