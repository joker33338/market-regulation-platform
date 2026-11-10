# v0.2.1 本地 Docker 入口

本机入口：`http://127.0.0.1:8180`。访问码在忽略目录 `local/workbench-access-code.txt`，不要提交或放进聊天。
当前是等待 QA 放行的本地候选部署，不表示生产验收通过。

## 一个项目、四个容器

Docker Desktop 统一显示 `market-regulation`：

| 服务 | 用途 | 本机端口 |
| --- | --- | --- |
| app | 上传、原生/PaddleOCR/PP-Structure 解析与结果入库 | 8180 |
| db | 既有 PostgreSQL + pgvector，保留原数据库卷 | 15432 |
| mysql | 用户要求保留，当前解析代码尚未使用 | 13306 |
| redis | 用户要求保留，当前解析代码尚未使用 | 16379 |

所有发布端口只绑定本机回环。三个既有数据服务未重建；应用使用已有数据库网络，通过容器内 `db:5432` 访问同一个库。
应用镜像 `market-regulation-workbench:local-f6affa00a3702d5a`，业务源码版本为
`a8f7031bfd3bdc6cc7df5f9adb190a75eee8a968`；其中包含本轮 QFA-001～004 修复。
后续项目合并与启动校验的脚本提交不改变镜像内业务源码。

## 启动和持久化

在 Fix 工作区使用：

```powershell
./scripts/local-workbench.ps1 -Action status
./scripts/local-workbench.ps1 -Action start
./scripts/local-workbench.ps1 -Action build
./scripts/local-workbench.ps1 -Action stop
```

脚本只管理 `compose.local.yaml` 的 app 服务；三个数据服务由既有 `compose.yaml` 保留在同一项目中。
Compose 可能提示三个服务未在本地应用文件内声明；它们是需要保留的已有服务，不要使用 `--remove-orphans`、`down -v` 或 prune 清理。
不要用原始 `compose.yaml` 的休眠 app 配置覆盖当前工作台。不要同时启动历史 QA 8180 入口。

应用 restart 策略为 `unless-stopped`。Docker 引擎恢复后按该策略恢复；整机重启、Desktop 登录启动仍须独立确认，未冒充实测。
准备脚本要求 Git 工作区干净，校验现有数据库、端口映射、表和离线模型，不创建表、不安装依赖、不下载模型。
镜像只叠加当前源码，基础镜像或代码内容不变时复用已有镜像，不因报告提交重复构建。

如需回滚应用，先完成当前任务并只停止 app，保留 state 目录和全部数据卷，再从已验证 Git 提交构建并启动。
本次没有数据库迁移，无须回滚 Schema。不要使用清库、删除卷、硬重置或覆盖原工作树的方式回滚。

应用为非 root、只读根文件系统、无额外 capabilities。模型只读挂载；私密文件不进入镜像：

- `local/parsing-runtime.json`：原有本机配置，保留。
- `local/docker-workbench/runtime.json`：应用只读私密配置，容器内数据库地址已正确转换。
- `local/docker-workbench/state/`：任务 SQLite、上传文件和解析工件，合并项目后继续使用同一目录。
- `local/docker-workbench/state/logs/`：Paddle 子进程日志的持久目录。
- `local/docker-workbench/deployment.json`：镜像、源版本、模型目录与端口，不提交 Git。

## 实测与权限边界

已实测认证、上传一份合成两页 PDF、本地解析、PostgreSQL 提交、幂等、容器重启和项目迁移后读取原任务。
数据库由 8 份增加到 9 份：仅新增一份明确的合成验证记录，未删除原数据、执行 DDL 或清理数据库。
实际非 root 容器从只读模型目录完成一次合成图片 PaddleOCR，识别 24 字，结果保留人工复核要求；没有下载模型或外传。

MinerU 使用官方 API，无需本地 MinerU 服务镜像。本次令牌检查仅 GET 读取一个历史完成任务：HTTP 200、业务码 0；
未创建远端任务、上传文件或恢复过期授权批次。工作台的云端自动回退默认关闭，浏览器勾选不能自行授予外传权限。
PP-Structure 表格模型配置与已有模型已检查；本次没有再次执行全量真实表格性能或 BGE/数据库生命周期测试。

复用基础镜像中实际 FastAPI 为 0.162.0、uvicorn 为 0.54.0；宿主完整回归复用的 API 环境为 0.115.12/0.34.2。
没有升级/重装任何一边。镜像已有 HTTP/入库/OCR 实测；完整独立 QA 仍需覆盖镜像环境，不能将宿主回归直接当作镜像全量通过。

## 清理记录与 QA

按用户要求移除 13 个旧 QA、测试/休眠应用及重复工作台实例；PostgreSQL、MySQL、Redis 原容器未移除。
3 个历史 QA 数据库卷全部保留，未删除任何卷、原始文档、模型、真值或云调用账本。
旧 QA 网关镜像和两个旧候选镜像已移除；保留当前应用、重建基础、Python、PostgreSQL、MySQL、Redis 镜像。
需要恢复历史隔离 QA 时须重新创建临时容器并沿用原数据/授权，不能把已移除的运行资源写为当前可用。
私密容器清单及数据卷映射在 `local/docker-cleanup-20261110/`，证据在 `local/v021-qfa-fix/`。

QA 复测要求和版本 SHA 见 `docs/qa/v0.2.1/handoff-to-qa.md`；独立 QA 闸门仍为 BLOCKED，未 Push 或合并 main。
