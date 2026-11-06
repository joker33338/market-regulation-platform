"""Fetch public government test materials; create clearly labelled scan derivatives."""
from __future__ import annotations
import argparse
import json
import ssl
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qa_core.config.settings import ROOT
from qa_core.utils import file_sha256

URL = "https://www.samr.gov.cn/cms_files/filemanager/1647978232/attach/20239/f44d033281344549a7499fb6bd1e2368.pdf"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/ocr-integration/samples")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / "samr_guidance_2023.pdf"
    if not target.exists():
        try:
            import truststore
            context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        except ImportError:
            context = ssl.create_default_context()
        request = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.samr.gov.cn/"})
        with urllib.request.urlopen(request, timeout=60, context=context) as response:
            target.write_bytes(response.read())
    import fitz
    with fitz.open(target) as original:
        single = fitz.open()
        single.insert_pdf(original, from_page=0, to_page=0)
        single.save(args.output_dir / "samr_page1_native.pdf")
        single.close()
        image_path = args.output_dir / "samr_page1_scan.png"
        pixmap = original[0].get_pixmap(matrix=fitz.Matrix(160 / 72, 160 / 72), alpha=False)
        pixmap.save(image_path)
        scan = fitz.open()
        page = scan.new_page(width=original[0].rect.width, height=original[0].rect.height)
        page.insert_image(page.rect, filename=str(image_path))
        scan.save(args.output_dir / "samr_page1_scan.pdf")
        scan.close()
        mixed = fitz.open()
        mixed.insert_pdf(original, from_page=0, to_page=0)
        page = mixed.new_page(width=original[0].rect.width, height=original[0].rect.height)
        page.insert_image(page.rect, filename=str(image_path))
        mixed.save(args.output_dir / "samr_mixed.pdf")
        mixed.close()
        metadata = {"source_url": URL, "title": "市场监管总局关于规范市场监督管理行政处罚裁量权的指导意见",
                    "source_pages": len(original), "source_sha256": file_sha256(target),
                    "derivatives": "page 1 extracted unchanged; rasterized at 160 DPI for scan/mixed tests",
                    "usage": "Parsing tests only; no assertion about current legal validity or labelled OCR accuracy."}
    (args.output_dir / "sources.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

