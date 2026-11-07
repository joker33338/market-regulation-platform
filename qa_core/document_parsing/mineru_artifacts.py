"""Bounded archive validation, atomic result storage and existing-schema adapter."""
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
import zipfile

from qa_core.utils import file_sha256
from .mineru_client import MinerUError
from .schemas import DocumentResult, PageResult, LayoutBlock, TableResult
from .normalizer import normalize_text, table_from_html


def unpack(payload: bytes, config) -> dict[str, bytes]:
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = archive.infolist()
            if len(members) > config.max_members or sum(item.file_size for item in members) > config.max_expanded_bytes:
                raise MinerUError("archive_too_large", 413)
            result, names = {}, set()
            for item in members:
                # ZipInfo.filename is already normalized/truncated on some
                # platforms; validate the original archive entry as well.
                name = item.orig_filename
                path = PurePosixPath(name)
                canonical = path.as_posix().casefold()
                if (not name or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name
                        or any(part.endswith((".", " ")) or any(ord(c) < 32 for c in part) for part in path.parts)
                        or any(part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *("COM"+str(n) for n in range(1,10)), *("LPT"+str(n) for n in range(1,10))} for part in path.parts)
                        or canonical.split("/")[0] in {"artifact.bin", "normalized.json"}
                        or stat.S_ISLNK(item.external_attr >> 16) or item.flag_bits & 1):
                    raise MinerUError("unsafe_archive_path")
                if canonical in names:
                    raise MinerUError("duplicate_archive_path")
                names.add(canonical)
                if not item.is_dir():
                    result[path.as_posix()] = archive.read(item)  # CRC verified by ZipFile
            required = set()
            if config.provider == "official":
                required.add("full.md")
                lists = [name for name in result if name == "content_list.json" or name.endswith("_content_list.json")]
                if len(lists) != 1:
                    raise MinerUError("ambiguous_official_content_list")
                required.add(lists[0])
            else:
                for fmt in config.output_formats:
                    required.update({"default": {"markdown.md", "structured_content.json", "middle_json.json"},
                                     "latex": {"document.tex"}, "docx": {"document.docx"}, "html": {"document.html"}}[fmt])
            if not required <= result.keys():
                raise MinerUError("incomplete_artifacts")
            return result
    except (zipfile.BadZipFile, RuntimeError, OSError):
        raise MinerUError("invalid_archive") from None


def store_artifacts(payload, directory: Path, config):
    if config.output_formats in {("docx",), ("html",)}:
        # These are single-file downloads in the Tasks contract.
        result = {"document." + config.output_formats[0]: payload}
        if config.output_formats == ("docx",):
            try:
                with zipfile.ZipFile(io.BytesIO(payload)) as docx:
                    if (sum(item.file_size for item in docx.infolist()) > config.max_expanded_bytes
                            or len(docx.infolist()) > config.max_members
                            or "word/document.xml" not in docx.namelist() or docx.testzip()):
                        raise MinerUError("invalid_docx")
            except zipfile.BadZipFile:
                raise MinerUError("invalid_docx") from None
    else:
        result = unpack(payload, config)
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in {"artifact.bin": payload, **result}.items():
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.resolve().is_relative_to(directory.resolve()) or target.is_symlink():
            raise MinerUError("unsafe_result_path")
        # A ZIP member can itself be called e.g. markdown.md.part. An exclusive
        # temporary file avoids clobbering it during another member's write.
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".mineru-", suffix=".part", delete=False) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(data)
            except BaseException:
                stream.close()
                temporary.unlink(missing_ok=True)
                raise
        try:
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    return result


def normalize_artifacts(task, file, artifacts, *, mock=False):
    """Only known structured-content blocks become legal source lines; no Markdown guessing."""
    official = task.get("provider") == "official"
    try:
        if official:
            names = [name for name in artifacts if name == "content_list.json" or name.endswith("_content_list.json")]
            if len(names) != 1:
                raise MinerUError("ambiguous_official_content_list")
            original = json.loads(artifacts[names[0]])
            pages_by_idx = {}
            for block in original:
                if isinstance(block, dict) and type(block.get("page_idx")) is int:
                    page = pages_by_idx.setdefault(block["page_idx"], {"page_idx": block["page_idx"], "blocks": []})
                    page["blocks"].append({**block, "content": block.get("text", block.get("table_body", ""))})
            structured = {"pages": list(pages_by_idx.values()), "original_content_list": original}
            middle = json.loads(artifacts.get("layout.json", b"{}"))
            markdown = artifacts["full.md"].decode("utf-8")
        else:
            structured = json.loads(artifacts["structured_content.json"])
            middle = json.loads(artifacts["middle_json.json"])
            markdown = artifacts["markdown.md"].decode("utf-8")
    except (KeyError, ValueError, UnicodeError):
        raise MinerUError("invalid_default_artifacts") from None
    # Preserve arbitrary/version-specific structure; unknown shapes require review.
    source = {"file_path": file["source_path"], "file_sha256": file["sha256"],
              "mineru_task_id": task["remote_id"], "mineru_file_id": file["remote_id"],
              "source_file_id": file.get("source_file_id", file["id"]),
              "parser_name": "mineru-mock" if mock else "mineru-official" if official else "mineru",
              "parser_version": file.get("parse", {}).get("parser_version") or (middle.get("_version_name") if official else None),
              "model_version": file.get("parse", {}).get("model_version"),
              "parsing_tier": file.get("parse", {}).get("tier"),
              "raw_result_location": file["result_path"], "created_at": task["created_at"]}
    pages = {}
    entries = []
    if isinstance(structured, dict):
        for page in structured.get("pages", []):
            if not isinstance(page, dict) or type(page.get("page_idx")) is not int:
                continue
            for block in page.get("blocks", []):
                if isinstance(block, dict):
                    entries.append({**block, "page_idx": page["page_idx"]})
    for entry in entries:
        if not isinstance(entry, dict) or type(entry.get("page_idx")) is not int or entry["page_idx"] < 0:
            continue
        number = entry["page_idx"] + 1
        page = pages.setdefault(number, PageResult(number, "mineru", source_location={**source, "page_number": number}))
        kind = entry.get("type")
        if kind == "table":
            markup = entry.get("content", "")
            # Preserve remote HTML without expanding untrusted rowspan/colspan grids.
            page.tables.append(TableResult(str(len(page.tables)), html=markup if isinstance(markup, str) else "",
                                           bbox=entry.get("bbox"), source_location=source,
                                           warnings=["Remote table structure retained for review; legal ingestion is blocked."]))
        elif kind in {"text", "title"} and isinstance(entry.get("content"), str):
            page.layout_blocks.append(LayoutBlock(str(len(page.layout_blocks)), kind, entry["content"], entry.get("bbox"),
                                                  reading_order=len(page.layout_blocks), source_location=source))
    for page in pages.values():
        page.raw_text = "\n".join(block.raw_text for block in page.layout_blocks)
        page.normalized_text = normalize_text(page.raw_text)
        page.markdown_content = page.raw_text
    result = DocumentResult(file["sha256"], file["file_name"], Path(file["file_name"]).suffix, source,
                            pages=sorted(pages.values(), key=lambda page: page.page_number),
                            parsing_status="needs_review", requires_review=True,
                            quality={"structured_content": structured, "middle_json": middle, "markdown": markdown,
                                     "images": [name for name in artifacts if name.startswith("images/")],
                                     "unknown_structure": not bool(pages), "mock": mock})
    return result


def reviewed_legal_document(result: DocumentResult, *, reviewer, law_name, law_id=None):
    from .bridge import to_legal_document
    source = Path(result.source_location["file_path"])
    if result.quality.get("mock"):
        raise MinerUError("mock_result_cannot_enter_knowledge_base", 400)
    if not source.is_file() or file_sha256(source) != result.document_id:
        raise MinerUError("source_integrity_mismatch", 409)
    return to_legal_document(result, reviewer=reviewer, law_name=law_name, law_id=law_id)
