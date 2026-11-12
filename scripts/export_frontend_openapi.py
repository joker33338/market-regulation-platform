"""从真实应用导出脱敏 OpenAPI；不启动 worker、模型或外部服务。"""
import argparse
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def export(destination):
    from qa_core.document_parsing.mineru_api import create_app
    from qa_core.document_parsing.mineru_config import MinerUConfig
    from qa_core.document_parsing.dual_engine import DualEngineConfig
    with tempfile.TemporaryDirectory() as directory:
        app = create_app(MinerUConfig(result_dir=Path(directory)),
                         tokens={"synthetic-openapi-token-0000000000": "synthetic-owner"},
                         dual_config=DualEngineConfig(enabled=False))
        destination.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    export(parser.parse_args().destination)
