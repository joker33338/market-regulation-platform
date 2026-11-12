# v0.2.2 本地源码统一报告

日期：2026-11-12。LOCAL_CONSOLIDATION：PASS（源码集成与必要构建）。

唯一长期主目录：原始 market-regulation-platform，main；本次从干净工作树安全切换，未覆盖用户修改。

- 已验收后端 `4fc4cf124a120762593064676ea5f8dbe2394119`，交接分支 HEAD `20bfeef57e101f08a2f37bd4a73b6ed4237dcba5`。合并后 qa_core 与 requirements.txt 相比验收版无差异。
- 前端业务 `63bbcc07a6b6d12a6be56fa7b0e81731c3917a45`，交接 `a6939742903f45fdaf13a858d45014ef04b7df71`；二者差异为三份文档，无业务变化。
- QA最终提交 `8ae8c238ff66e6d37a367a3c5b1efe3e899e1d4b`。QA旧分支直接合并预演出现旧业务代码冲突，因此只以 -x cherry-pick 集成843c64d之后六个新增验收提交；完整QA历史独立保留。
- Agent C部署分支 `2b3c7930fe08c80e8b969750a033ca844afc5def` 已保留合并记录；后端正式交接、前端交接均通过非快进合并保留历史。旧Fix分支历史业务已在v0.2.1基线中，不重复引入旧源码。
- 合并后 test_frontend_api/test_mineru_api/test_schema_identity/test_frontend_gateway 共30项通过，无跳过；前端 tsc 与 Vite build 通过，仅有资源体积提示。

更新清单以本轮 main Git merge/cherry-pick/diff 为准：qa_core/api、相关任务接口与SQLite适配、frontend 全部源码及锁文件、docs/integration、docs/qa/v0.2.2、最终闭环安全脚本；新增正式部署适配层、更新/停止/回滚脚本及本版维护指南。业务未重写，数据库未迁移。

删除文件清单：空。未能证明无引用或承担回滚作用的历史内容一律保留，不以整理为名删除。旧HTML工作台业务源仍保留供历史镜像回滚，正式入口由部署层替换。

保留清单：所有数据库、上传和解析结果、模型、缓存、授权账本、.env与私密runtime配置、历史QA证据和迁移、历史镜像、所有Git分支及工作树。

工作树盘点：backend-api位于codex/backend-api-v0.2.2且干净；frontend位于feat/frontend-api-v0.2.2且干净；qa位于codex/qa-v0.2.1，有一份未跟踪F01响应文档，不代为提交；fix实际位于codex/frontend-api-integration，有两份业务修改、未跟踪API目录/测试/维护报告，来源及验收身份不明，原样保留。备份目录不是Git仓库，仅归档候选，当前不删除。历史orchestrator与archive工作树保留。

运行数据仍由Fix目录下既有ignored状态承载，该目录暂时不能删除。未跟踪QA响应和Fix初稿不计入已验收源码，也不推送。后续不得在旧工作树并行维护主线。
