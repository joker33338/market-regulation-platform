# Docker 本地部署

这是命令行知识库，目前没有网页入口。应用镜像包含 PaddleOCR 3.3.2 / PaddlePaddle 3.2.2 CPU 文档解析环境；生成式大模型需自行配置。

## 镜像及数据

- `python:3.12-slim-bookworm`：构建 Python 3.12 CPU 运行环境。
- `pgvector/pgvector:pg16`：PostgreSQL 16 与 pgvector。
- `mysql:8.4`：独立 MySQL 服务，本机端口 `13306`，数据库 `market_regulation`，用户 `market_app`。
- `redis:7.4-alpine`：独立 Redis 服务，本机端口 `16379`，启用 AOF 持久化和密码验证。
- `market-regulation-app:local`：从本项目 Dockerfile 构建，包含 CPU PyTorch 和 BGE 依赖。

已有 `models` 目录只读挂载，不复制进镜像；法规放入项目 `data` 目录。报告写入 `reports`。数据库使用独立 Docker 数据卷 `market-regulation_postgres_data`，只向本机开放 `15432` 端口。

本机密码保存在已忽略的 `.env.docker`，字段为 `DOCKER_DB_PASSWORD`。迁移到另一台机器时需重新生成该文件。已初始化数据库更改密码需要同步修改数据库角色密码，单改环境文件不会更新已有数据库。

MySQL 应用用户密码为 `DOCKER_MYSQL_PASSWORD`，root 密码为 `DOCKER_MYSQL_ROOT_PASSWORD`；Redis 密码为 `DOCKER_REDIS_PASSWORD`。服务仅绑定 `127.0.0.1`，数据分别保存在 `mysql_data` 和 `redis_data` 卷中。MySQL 和 Redis 已作为独立服务部署；现有知识库仍使用 PostgreSQL，尚未自动接入新增服务。

## 启动和检查

在项目目录执行 PowerShell 命令：

```powershell
docker compose --env-file .env.docker up -d --build
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker exec app python scripts/ingest_legal_documents.py init-db --postgres
```

`app` 保持运行以便执行命令，不提供 HTTP 服务。

## 导入、发布、查询

将自己的法律文件放到 `data` 后执行。版本号每次构建须不同；发布会切换本地库的在线版本。

```powershell
docker compose --env-file .env.docker exec app python scripts/ingest_legal_documents.py ingest --input /app/data --postgres --write --version local-v1
docker compose --env-file .env.docker exec app python scripts/ingest_legal_documents.py publish --postgres --version local-v1
docker compose --env-file .env.docker exec app python scripts/ingest_legal_documents.py query --postgres '需要提交哪些材料？'
```

## 验证和停止

PaddleOCR 已用本地 `PP-OCRv5_mobile_det`、`PP-OCRv5_mobile_rec` 完成容器内 CPU 离线识别验证。测试报告在 `reports/docker-ocr-smoke`；这项验证不代表版面、表格或全部文档类型均已验收。

```powershell
docker compose --env-file .env.docker exec app python scripts/test_document_parsing.py --input /app/reports/ocr-integration/samples/synthetic_legal.png --mode ocr --output-dir /app/reports/docker-ocr-smoke
```

```powershell
docker compose --env-file .env.docker exec app python -m unittest tests.test_postgres_integration -v
docker compose --env-file .env.docker exec app python scripts/smoke_local_model.py
docker compose --env-file .env.docker stop
```

集成测试只在随机隔离 schema 中创建和清理数据；真实模型验证使用单独 SQLite 演示库。不要执行 `down -v`，除非确定要删除本地数据库数据卷。

Docker Hub 超时时可先执行以下命令再构建：

```powershell
docker pull docker.m.daocloud.io/library/python:3.12-slim-bookworm
docker tag docker.m.daocloud.io/library/python:3.12-slim-bookworm python:3.12-slim-bookworm
```
