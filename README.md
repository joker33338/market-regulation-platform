# 市场监管智能文档解析与法规知识库平台

当前正式版本 **v0.2.1**，已通过指定后端 MVP 与候选镜像的本地集成验收。原始工程现为日常代码维护入口；Fix、QA、前端和历史工作树继续保留。生产实例切换、Windows 整机恢复和独立前端完整联调不属于此次 PASS。

## 功能与技术栈

FastAPI 管理上传、异步任务、鉴权、状态和结果；文字 PDF、DOCX 优先原生解析，图片和扫描页使用 PaddleOCR，复杂版面及表格使用 PP-StructureV3。DualEngineRouter 按质量和服务器授权选择 MinerU 官网 v4 增强，保留本地／云候选，低质结果要求人工复核。原始文件以 SHA256 关联，不静默改写。

法规清洗、结构提取及父子 Chunk 处理后，可用 BGE-M3 生成1024维向量，显式构建知识库候选；发布与回滚单独操作。解析结果保存、切分预览与正式知识库发布是三个阶段，不会上传后自动发布法规。

## 目录

| 目录 | 用途 |
| --- | --- |
| qa_core/document_parsing | 原生／OCR／云解析、质量、路由、任务 API 与 SQLite |
| qa_core/indexing | 法规结构、清洗、切分、预览和离线构建 |
| qa_core/retrieval | 本地向量模型及混合检索 |
| qa_core/storage、governance | PG 持久化、版本和授权发布／回滚 |
| scripts、deploy/local | 显式 CLI、启动和本地 Docker 入口 |
| tests | 已验收基线的测试与契约夹具，不是生产返回值替代实现 |
| docs/current | 当前有效操作说明 |
| docs/releases/v0.2.1 | 正式验收快照 |
| docs/qa | 各历史时点的开发／验收记录，不能一概当作当前门禁 |

## 环境、安装与模型

使用 Python 3.12、现有已验证环境及 Docker Desktop。依赖统一在 requirements.txt；本次同步不安装或升级。新环境可执行 `python -m pip install -r requirements.txt`，CPU torch 的构建方式见 Dockerfile。已有 OCR 位于 models/ocr、BGE 位于 models/bge-m3；模型不纳入 Git、不随应用启动下载。首次准备须明确执行模型准备工具，不要在现有机器重复下载。

## 配置与启动

配置只通过进程环境或显式私密 JSON 加载，不自动读取旧 .env。`.env.example` 是变量索引，不含真实 Token。访问码、PG 连接和 MinerU Key 放在忽略的 local 私密文件；不要把凭据提交、截图或贴进日志。

```powershell
# 指定已存在且经过核对的私密配置与 Python；不会自动安装依赖。
./scripts/start_parsing_app.ps1 -ConfigFile $ConfigFile -Python $Python
```

该命令默认监听 http://127.0.0.1:8180；端口占用时拒绝启动，不停止现有服务。普通 API 禁止 QA 写入连接。模型、持久任务目录及运行模式由显式配置决定；请先阅读[完整操作手册](docs/current/v0.2.1-guide.md)。本次仅迁移代码入口，现有运行状态仍保留在原位置，没有自动迁移私密配置、SQLite 或运行容器。

## Docker、数据库与 API

本地部署采用已有基础镜像、只读模型／私密配置和持久 state，详见[操作手册](docs/current/v0.2.1-guide.md#部署与恢复)。固定宿主 PostgreSQL 为127.0.0.1:15432/market_regulation，容器内 db:5432 是同一库。document_review 存解析结果，public 存法规知识库，mvp_test_* 是同库测试域。不得把测试 ACTIVE 复制到 public。

主要接口为 POST /api/parse/files、POST /api/parse/tasks、GET /api/parse/tasks/{task_id} 和 GET /api/parse/tasks/{task_id}/results；Bearer 鉴权及任务所有者检查在服务器执行。MinerU 官方 v4 与自建4.1 Tasks不是同一个服务；云端默认关闭，Key 不等于文件外传授权。

## 测试与常见问题

```powershell
& $Python -B -m unittest tests.test_release_safety tests.test_final_cache_recovery tests.test_schema_identity -v
```

真实 PG／云调用须使用专门授权入口，不能直接把业务 DSN 注入测试 discover。收到401先检查访问码；未见知识库数据先区分 document_review 和 public；低质结果保留复核；超限图片 SAFE_REJECT，不通过缩放或云端绕过。遇到模型路径错误先核对 UTF-8 路径、权重、HOME 和可写日志，不重装全部模型。

## 文档索引

- [当前架构、API、配置与运维](docs/current/v0.2.1-guide.md)
- [正式验收及边界](docs/releases/v0.2.1/README.md)
- [版本变更](CHANGELOG.md)
- [原始工程同步报告](docs/project-maintenance/v0.2.1-original-project-sync-report.md)

历史集成设计及未验收计划仍保留；独立前端、全局历史审核队列、外部来源契约和整机自动恢复不要描述为本版本已完成能力。

- [最终 Git 维护归档](docs/project-maintenance/v0.2.1-final-git-archive.md)
