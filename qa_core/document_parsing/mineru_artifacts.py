"""远端解析产物的安全校验、落盘与统一协议转换。

限制压缩成员数量及展开体积，拒绝路径穿越和歧义文件，再使用临时文件替换
写入产物。仅已知结构化块可进入法律正文，不根据 Markdown 猜测未知结构。"""
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
    """校验压缩包后返回文件名到字节内容的映射，不直接把压缩成员解压到磁盘。

    同时校验原始名称、规范化名称、重复路径、链接及加密标记，并限制成员数
    和展开体积。官方与自托管产物按不同协议检查必需文件；CRC 或 ZIP 结构
    异常转为固定业务错误，避免把外部异常正文回显给用户。"""
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = archive.infolist()
            if len(members) > config.max_members or sum(item.file_size for item in members) > config.max_expanded_bytes:
                raise MinerUError("archive_too_large", 413)
            result, names = {}, set()
            for item in members:
                # 部分平台已对 ZipInfo.filename 做规范化或截断，
                # 所以还必须校验压缩包条目的原始名称。
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
                    result[path.as_posix()] = archive.read(item)  # 由 ZipFile 校验 CRC
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
    """校验完整产物后逐文件写入受控结果目录，并返回已验证的内容映射。

    每个文件使用独占临时文件再原子替换，禁止符号链接或目录逃逸。
    原子性仅针对单个文件，不代表整个产物目录具有跨文件事务；失败时调用方
    仍需依据任务状态决定重试，不能将部分文件视为完整成功。"""
    if config.output_formats in {("docx",), ("html",)}:
        # Tasks 契约规定这些产物以独立文件下载。
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
        # 压缩包成员本身也可能叫 markdown.md.part，因此使用独占的
        # 临时文件，避免写入其他成员时覆盖它。
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
    """按官方或自托管结构化协议转换产物，不从未知 Markdown 段落猜测法律正文。"""
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
    # 保留供应商版本相关的原始结构，未知格式必须人工复核。
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
            # 保留远端 HTML，不展开不可信的 rowspan/colspan 网格。
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
