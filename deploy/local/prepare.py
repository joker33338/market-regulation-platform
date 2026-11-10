"""复用已有 Docker 数据库、模型与环境，准备被忽略的工作台私密配置。"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import psycopg2
from psycopg2.extensions import make_dsn, parse_dsn

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, stderr=subprocess.PIPE)


def runtime_values(values, database_host="db"):
    dsn = parse_dsn(values["PARSING_RESULT_PG_DSN"])
    if dsn.get("host") not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("仅复用已明确配置在本机的 Docker 数据库。")
    dsn.update(host=database_host, port="5432")
    tokens = json.loads(values["PARSING_API_TOKENS_JSON"])
    if not tokens or any(len(token) < 32 or not owner for token, owner in tokens.items()):
        raise ValueError("缺少有效的现有本地访问码。")
    result = {"PARSING_RESULT_PG_DSN": make_dsn(**dsn),
              "PARSING_API_TOKENS_JSON": values["PARSING_API_TOKENS_JSON"]}
    if values.get("MINERU_API_KEY"):
        result["MINERU_API_KEY"] = values["MINERU_API_KEY"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8180)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        raise ValueError("本地入口端口无效。")
    if run("git", "status", "--porcelain").strip():
        raise ValueError("请先保存工作区变更为可追溯提交，再构建工作台。")
    source_commit = run("git", "rev-parse", "HEAD").decode().strip()
    values = json.loads((ROOT / "local/parsing-runtime.json").read_text(encoding="utf-8-sig"))
    runtime = runtime_values(values)
    network = "market-regulation_default"
    network_info = json.loads(run("docker", "network", "inspect", network))[0]
    if not any(item.get("Name") == "market-regulation-db-1" for item in network_info.get("Containers", {}).values()):
        raise ValueError("指定 Docker 网络没有已有数据库容器；未创建或迁移数据库。")
    database = json.loads(run("docker", "inspect", "market-regulation-db-1"))[0]
    mappings = database.get("NetworkSettings", {}).get("Ports", {}).get("5432/tcp") or []
    original = parse_dsn(values["PARSING_RESULT_PG_DSN"])
    if not any(p.get("HostPort") == original.get("port", "5432") and p.get("HostIp") in {"127.0.0.1", "::1"} for p in mappings):
        raise ValueError("配置端口与现有数据库映射不一致，拒绝自动改绑。")
    connection = psycopg2.connect(values["PARSING_RESULT_PG_DSN"], connect_timeout=5)
    try:
        connection.set_session(readonly=True)
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('document_review.documents'), to_regclass('document_review.pages'), to_regclass('document_review.cells')")
            if not all(cursor.fetchone()):
                raise ValueError("数据库缺少既有解析表；本入口不自动执行迁移。")
        connection.rollback()
    finally:
        connection.close()
    common = Path(run("git", "rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip())
    agent = json.loads((common / "agent-local.json").read_text(encoding="utf-8-sig"))
    models = Path(agent["originalRoot"]) / "models"
    from qa_core.document_parsing.config import ParsingConfig
    ParsingConfig(model_root=models / "ocr", enable_tables=True).validate_models("structure")
    if not (models / "bge-m3/config.json").is_file():
        raise ValueError("缺少已准备的 BGE-M3 模型；不会自动下载。")
    base = json.loads(run("docker", "image", "inspect", "market-regulation-app:local"))[0]["Id"]
    source_paths = ("qa_core", "query.py", "deploy/local/Dockerfile", "deploy/local/entrypoint.py", "deploy/local/Dockerfile.dockerignore")
    tree = run("git", "ls-tree", "-r", source_commit, *source_paths)
    identity = hashlib.sha256(base.encode() + tree).hexdigest()[:16]
    image = "market-regulation-workbench:local-" + identity
    root = ROOT / "local/docker-workbench"
    root.mkdir(parents=True, exist_ok=True)
    run("git", "check-ignore", str(root))
    private = root / "runtime.json"
    if private.exists() and json.loads(private.read_text(encoding="utf-8-sig")) != runtime:
        raise ValueError("已有工作台私密配置不同；保留原文件，须先核对再更新。")
    if not private.exists():
        private.write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "state").mkdir(exist_ok=True)
    (root / "state/logs").mkdir(exist_ok=True)
    try:
        existing_image = json.loads(run("docker", "image", "inspect", image))[0]
        source_commit = existing_image.get("Config", {}).get("Labels", {}).get("org.opencontainers.image.revision") or source_commit
    except subprocess.CalledProcessError:
        pass
    deployment = dict(image=image, source_commit=source_commit, base_image_id=base, port=args.port,
                      models_root=models.as_posix(), database_network=network)
    (root / "deployment.json").write_text(json.dumps(deployment, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dict(status="READY", image=image, port=args.port, source_commit=source_commit,
                          database="existing", cloud_transfer_enabled=False), ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # 连接异常可能包含原始凭据，只输出类型；主动验证消息不含凭据。
        print(json.dumps(dict(status="FAILED", error_type=type(exc).__name__,
                              reason=str(exc) if isinstance(exc, ValueError) else "请检查本地配置、Docker及既有环境。"), ensure_ascii=False))
        raise SystemExit(1)
