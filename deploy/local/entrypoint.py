"""从只读私密文件加载本地工作台配置，不在镜像或日志内存放凭据。"""
import json
import os
from pathlib import Path


def configuration(path):
    values = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    allowed = {"PARSING_API_TOKENS_JSON", "PARSING_RESULT_PG_DSN", "MINERU_API_KEY"}
    if (not isinstance(values, dict) or set(values) - allowed
            or not all(isinstance(value, str) for value in values.values())
            or not all(values.get(key) for key in ("PARSING_API_TOKENS_JSON", "PARSING_RESULT_PG_DSN"))):
        raise RuntimeError("本地工作台配置无效；请重新运行准备脚本。")
    return {**values, "MINERU_ENABLED": "1", "MINERU_MODE": "local", "MINERU_PROVIDER": "self_hosted",
            "MINERU_API_URL": "", "MINERU_RESULT_DIR": "/state/parsing", "DUAL_OCR_ENABLED": "1",
            "DUAL_OCR_CLOUD_ENABLED": "0", "DUAL_OCR_AUTHORIZATION_MODE": "FILE_SHA",
            "DUAL_OCR_ENVIRONMENT": "production", "OCR_MODEL_ROOT": "/models/ocr",
            "OCR_ENABLE_TABLES": "1", "EMBEDDING_MODEL_PATH": "/models/bge-m3"}


def main():
    # 不继承任何测试连接或旧批次授权；外传仍由现有服务端权限控制，默认关闭。
    for key in ("MVP_TEST_PG_DSN", "PARSING_TEST_PG_DSN", "QA_ISOLATED_PG_DSN",
                "OFFLINE_APPROVED_PG_DSN", "PG_DSN", "SOURCE_PG_DSN", "DUAL_OCR_GRANTS_FILE", "DUAL_OCR_TEST_BATCH_MANIFEST",
                "DUAL_OCR_TEST_BATCH_OWNER", "DUAL_OCR_TEST_BATCH_ID"):
        os.environ.pop(key, None)
    os.environ.update(configuration("/private/runtime.json"))
    os.environ["HOME"] = "/tmp/workbench-home"
    os.environ["XDG_CACHE_HOME"] = "/tmp/workbench-cache"
    Path(os.environ["HOME"]).mkdir(exist_ok=True)
    os.execvp("python", ["python", "-B", "-m", "uvicorn", "qa_core.document_parsing.mineru_api:create_app",
                        "--factory", "--host", "0.0.0.0", "--port", "8180", "--workers", "1",
                        "--log-level", "warning", "--no-access-log"])


if __name__ == "__main__":
    main()
