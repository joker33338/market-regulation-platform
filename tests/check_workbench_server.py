"""短期真实HTTP界面夹具，仅合成文件及临时SQLite，后台引擎不运行。"""
import argparse
from contextlib import asynccontextmanager
from pathlib import Path
import os
import tempfile

import fitz
import uvicorn
from fastapi.testclient import TestClient

from deploy.release.application import VueFiles
from qa_core.document_parsing.mineru_api import create_app
from qa_core.document_parsing.mineru_config import MinerUConfig


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18186)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--login-fixture", action="store_true")
    args = parser.parse_args()
    for key in ("PARSING_RESULT_PG_DSN", "PG_DSN", "KNOWLEDGE_WRITE_PG_DSN",
                "REVIEW_MYSQL_CONFIG_JSON", "AUTH_ACCOUNTS_FILE", "PARSING_API_TOKENS_JSON"):
        os.environ.pop(key, None)
    with tempfile.TemporaryDirectory() as state:
        config = MinerUConfig(enabled=True, result_dir=Path(state))
        app = create_app(config, tokens={"a"*32: "alice", "b"*32: "bob"})
        if args.login_fixture:
            from scripts.provision_auth_accounts import provision
            password = os.environ['LOGIN_TEST_PASSWORD']
            filename = Path(state) / 'synthetic-accounts.json'
            provision(filename, 'synthetic-login-admin', password)
            app.state.account_store.filename = str(filename)
        @asynccontextmanager
        async def isolated_lifespan(application):
            # 页面测试只提交持久化任务，不将合成夹具送入引擎。
            yield
            await application.state.service.client.close()
        app.router.lifespan_context = isolated_lifespan
        with TestClient(app) as client:
            for index in range(25):
                document = fitz.open()
                page = document.new_page()
                page.insert_text((50, 50), f"Synthetic browser file {index:02}")
                payload = document.tobytes()
                document.close()
                response = client.post("/api/parse/files", params={"file_name": f"synthetic-{index:02}.pdf"},
                    headers={"Authorization": "Bearer " + "a"*32}, content=payload)
                assert response.status_code == 201, response.status_code
        app.router.routes[:] = [route for route in app.router.routes if getattr(route, "path", None) != "/"]
        app.mount("/", VueFiles(directory=str(args.dist.resolve()), html=True))
        uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
