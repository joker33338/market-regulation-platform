# 市场监管法规知识库平台 v0.2.3

本地统一入口：http://127.0.0.1:8180/login 。Vue 3 与 FastAPI 同源部署，支持账号密码、ADMIN/REVIEWER/USER、文档与OCR任务、追加式MySQL审核台账、法规及案例只读目录、检索与知识库治理。

唯一长期源码目录为本仓库原始工作目录；最终 main、v0.2.3 标签及镜像 OCI 必须一致。开发、联调与自测由 Agent C 统一负责，不宣称独立QA验收。

PostgreSQL保存文档、法规、案例及知识库，MySQL仅保存独立审核历史，SQLite保留解析任务。无ACTIVE时检索和业务目录返回合法未发布空态，不自动批准或发布候选资料。

部署、权限、真实测试范围与限制见 [v0.2.3发布指南](docs/v0.2.3-release-guide.md)。v0.2.2历史及回滚依据保留在 [旧版指南](docs/release/v0.2.2/guide.md)。口令、runtime、真实文件、模型、数据库和日志均不进入Git。
