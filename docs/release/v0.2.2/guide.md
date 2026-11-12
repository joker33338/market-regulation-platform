# v0.2.2 正式维护指南

唯一长期主工作目录为原始 `market-regulation-platform`，分支 main。其他工作树仅保留分支历史、未提交成果或运行数据，不删除。

## 架构与技术栈

Vue 3 / TypeScript / Vite 提供七页面；FastAPI 复用 OCR、审核只读和 RAG Service；SQLite 持久化任务，PostgreSQL 的 document_review/public 保持不变。保留 PaddleOCR、PP-StructureV3、MinerU 和 BGE-M3；不迁移数据库，不引入 MySQL。已有未用于核心业务的历史 MySQL/Redis 容器保留。

正式入口统一为 http://127.0.0.1:8180 ，无需 Vite 服务。部署工厂为 deploy.release.application:create_app，仅替换旧根页面并增加 Vue History 回退，/api 认证与 OpenAPI 保持原契约。旧业务工厂仍保留以便历史镜像回滚。

## 依赖、API 与环境

Python 固定版本见 requirements.txt；前端版本锁见 frontend/package-lock.json。现有 node_modules 只读复用，不重新安装模型。API 方法、参数、错误码和空数据语义见 docs/integration/frontend-api-contract.md，实际认证文档为 /api/openapi.json，匿名 OpenAPI 不开放。审核写入及正式知识库发布不在本版 HTTP 承诺内。

配置继续由现有 /private/runtime.json 只读挂载提供；变量 PARSING_API_TOKENS_JSON、PARSING_RESULT_PG_DSN、MINERU_API_KEY 不进镜像或Git。状态 /state、日志 /app/reports、模型 /models 的既有宿主路径不变。状态当前仍在历史 Fix 工作树 ignored local 下，因此该工作树不能删除；主维护目录统一不意味着擅自搬迁运行数据。

## 构建、更新、停止与回滚

前端执行 `node node_modules/typescript/bin/tsc --noEmit` 与 `node node_modules/vite/bin/vite.js build`。然后从干净主线构建：

```powershell
$revision = git rev-parse HEAD
docker build --pull=false -f deploy/release/Dockerfile --build-arg "SOURCE_COMMIT=$revision" -t "market-regulation-workbench:sha-$revision" .
./scripts/release-docker.ps1 -Action Update -Image "market-regulation-workbench:sha-$revision"
./scripts/release-docker.ps1 -Action Status
./scripts/release-docker.ps1 -Action Stop
./scripts/release-docker.ps1 -Action Rollback -Image market-regulation-workbench:candidate-v022-4fc4cf124a12
```

更新和停止前检查活动任务，为零才执行；同时需遵守QA冻结及更新批准规则。脚本从现有容器读取挂载，保留所有数据服务和卷；切换记录写在 ignored local。不得使用 prune、remove-orphans、down -v。回滚使用旧镜像和相同挂载；旧镜像显示历史工作台属于回滚行为。

旧 scripts/local-workbench.ps1、deploy/local/Dockerfile 是历史构建链，保留但不用于正式 Vue 更新。旧8181前端容器可停止并保留作为回滚，不作为正式入口。

## QA 与协作

最终验收见 docs/qa/v0.2.2-final-acceptance.md，源码后端4fc4cf1、前端63bbcc0；V022-F01与V022-E01已关闭。历史报告不改写。收尾仅做合并后定向测试和部署验证，不重复云OCR、隔离写闭环或真实数据测试。Agent C 管理统一镜像，Fix提交最小修复，QA按不可变版本独立验收，WorkBuddy维护前端；所有后续开发以主目录main为共同基线。
