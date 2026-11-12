# v0.2.3 文档软删除：实现、自测及独立 QA 交接

日期：2026-11-12。状态：**BACKEND_API_PARTIAL，待 QA 独立验收**。未切换 8180，未写正式数据库或正式授权配置。

## 契约与授权

`DELETE /api/documents/{file_id}`，无请求体、无 Idempotency-Key。file_id 为 32 位小写十六进制上传 ID。HTTPBearer 认证；使用现有凭证到 principal/owner 的私密映射，不输出凭证或配置。

必须同时满足有效身份、ADMIN 角色、目标属于本人 owner、显式 `document_delete_owner_scopes` 包含该 owner。新增可选字段默认空，不允许通配符；历史 local-user 不自动授权。REVIEWER 不等于删除权限，ADMIN 单独也不足以删除。未更改任何正式授权名单。

成功 200：

```json
{"file_id":"11111111111111111111111111111111","deleted":true,"deleted_at":"2026-11-12T08:00:00+00:00","disposition":{"mode":"soft_delete","original_bytes":"retained","metadata":"quarantined","related_records":"unchanged"}}
```

失败统一 `{"error":{"code":"机器错误码"}}`，不返回成功回执。重复删除 404，副作用天然幂等；客户端不应把重复删除计为本次成功。

| HTTP | 语义及主要错误码 |
|---|---|
| 401 | 缺失、失效或撤销的凭证，沿用认证错误码 |
| 403 | 无显式删除授权或跨 owner：document_delete_forbidden |
| 404 | 不存在或已删除：document_not_found |
| 409 | 活动任务 document_active_task；任何历史任务 document_evidence_protected；PG/知识库引用 document_referenced；锁冲突 document_busy；归档冲突 document_archive_conflict |
| 422 | file_id 非法：invalid_request；内部校验 invalid_file_id |
| 503 | 存储、引用核查不可用：source_storage_unavailable 或 read_service_unavailable；不得把核查异常当无引用 |

运行期 OpenAPI 与离线 `frontend-openapi-v023-draft3.json` 均为 `frontend-api-v0.2.3-draft-3`，info.version 为 0.2.3-dev，30 个路径；原有文档详情路径新增 DELETE 方法。保留 draft1、draft2 及 v0.2.2 冻结契约。无 batch-delete。

## 数据处置及一致性

选择软删除：在 owner 上传区的私有 `.deleted` 子目录保存原上传元数据及删除准备记录，原始字节保留。活动元数据移动为删除提交点，无数据库 DDL、无新引擎、无正式表结构变更。

删除后 GET 文档列表过滤该上传；GET 文档详情、parse-history、原件 GET/HEAD 均 404。已开始传输的下载可能完成，无法撤回已发送字节。不提供归档元数据或原件的公开旁路读取、恢复或物理清理接口。

为保护证据链，第一版只允许删除尚未形成解析记录的上传：存在任何 SQLite 任务（包括失败/完成任务）即 409，因此不删除任务、解析 artifact、MySQL 审核事件或修订。额外只读核查 PostgreSQL 解析结果的上传 ID/文档 hash，以及 public 知识库所有版本的 source_hash；任意引用即 409，不只检查 ACTIVE。PG/知识库未配置或不可用时 503。正常审核建立在解析结果上，受上述前置阻断；未对绕过正常入口产生的孤立历史 MySQL 事件另做扫描，QA 应核查该业务不变量。

共享文件锁协调本次删除、现有 OCR 任务提交和受支持的入库保存入口；删除后禁止按保留字节重新提交或入库。跨进程使用同一状态根目录。绕过入口的手工 SQL/离线导入不受该锁协调，部署前必须确认维护流程没有此类并行写入。

准备记录包含 operator_id、owner_id、时间、元数据摘要及删除标识；只有“归档元数据存在且活动元数据不存在”才视为已提交。移动前异常保留活动元数据和原件，返回 503；可能留下准备记录或临时文件，不能据此认定删除成功。提交后不再执行可能引发失败回执的磁盘写操作。此文件级方案不宣称跨文件系统断电事务保证，异常关机后的孤立准备记录需人工只读核查。

## 变更文件

- qa_core/api/document_delete.py、principals.py、frontend.py、contracts.py、common.py：接口、显式授权、契约与列表/详情一致性。
- qa_core/api/read_store.py：只读引用核查。
- qa_core/storage/document_lifecycle.py：生命周期锁与隔离元数据。
- qa_core/storage/db.py、qa_core/document_parsing/mineru_service.py：入库及任务入口共享锁、防止重新引用归档上传。
- tests/test_document_delete.py、tests/check_document_delete_http.py：合成数据回归和真实 HTTP 探针。
- docs/integration/frontend-openapi-v023-draft3.json 及本交接说明。

## 源码和候选身份

原开发分支：codex/backend-improvements-v023。开始基线 228879d735831a07ef6843437bc25014b78847a0；本地 main 为 076d4f968aa2c71133c551007b5d082da96a5929。未重置或合并 main。

业务实现提交：72266d1e44c5092493640fd21fd104144cbae225。OpenAPI 兼容修复及候选冻结源码：**cd3fd89441cf385cf631f0adc7ba096a9743900e**。后续测试/文档提交不改变候选业务源码，最终交接提交 SHA 在交付消息记录。

| 身份项 | 候选隔离验证 | 正式 8180，未修改 |
|---|---|---|
| 后端源码 / OCI revision | cd3fd89441cf385cf631f0adc7ba096a9743900e | 30c4663ceb93cbba302b322f1ecee0d06d80bfb4 |
| 镜像 ID | sha256:80bedbd207c469ae6d0077b2ef0d0dbe6075bea9f877dc5c2a02f4d1c15c3e89 | sha256:e2a94f67ffacef9e780e06bc1484cb5e7dde4b287fa5ef340a666f5e573e52a3 |
| 镜像标签 | market-regulation-workbench:candidate-v023-delete-cd3fd894-f019eeb | market-regulation-workbench:sha-30c4663ceb93cbba302b322f1ecee0d06d80bfb4 |
| 运行容器 | 临时 --rm，无长期候选服务、无宿主端口 | market-regulation-app-1 |
| 实际 HTTP 身份 | draft-3，30 路径，文档 GET + DELETE | 0.2.2-api-candidate，22 路径，文档仅 GET |
| 前端 revision | 019eeb2433d41388737e8c05bab0919ace03538b | 现有固化前端，本任务未替换 |

正式容器 ID：b23198928dda0e75ff7ad40d3ce8170da825cb81922526a1db65e8b5815621c1；启动时间仍为 2026-11-12T00:54:43.04620371Z。8180 不会因本地源码提交自动获得 DELETE。

## 自测证据及限制

- 最终 Linux 候选镜像：110 项 unittest 全部通过，0 跳过。覆盖删除、RBAC、MySQL 独立台账、接口、SQLite、网关及发行保护；业务模块确实从镜像加载，测试文件只读挂载。
- Windows 本地：110 项，109 通过、1 项符号链接权限相关跳过；该项在 Linux 候选通过。
- 隔离 HTTP：合成有效 Bearer，真实 uvicorn 和 HTTP 请求；上传 201、未认证删除 401、删除 200、刷新列表 total=0、详情/历史/原件 GET/HEAD 404、重复删除 404；实际 OpenAPI 含 DELETE 和全部指定错误 schema；Vue 页面响应与候选 dist 一致。
- HTTP 正向引用回调使用明确“无引用”夹具，无正式 PG 连接。PG/知识库引用适配器通过受控测试验证，尚待 QA 用独立真实 PG/知识库引用夹具验证；没有用正式数据试删。
- 测试包括跨 owner 403、无授权 403、活动/历史任务 409、版本引用 409、存储异常 503、失败时原元数据/字节不变、删除与任务创建竞争、并发重复删除、入库防重引、路径隔离和错误脱敏。
- 未执行真实浏览器交互验收；前端 TypeScript 检查和 Vite 构建成功，存在既有大 chunk 提示。
- pytest 兼容测试采用 unittest 执行。当前环境无 pytest；用户虽已允许隔离安装，自动审批仍依据旧准备规则拒绝安装，未绕过。**未声称完成 pytest 命令验收**，由 QA 在获准测试环境补跑。
- git diff --check 及新增变更敏感信息扫描在提交前执行；未安装项目运行依赖、修改前端源码或访问外部 OCR。

## WorkBuddy 与 QA 接入

前端已有逐个 DELETE 方法和运行期方法门控，方法声明部署后可解锁，不需为此改码。实际成功仍取决于显式删除授权、存储可用和证据链检查；403/409/503 必须显示失败，不能本地移除行；仅 2xx 计成功，然后 GET 刷新。

QA 使用上述不可变候选镜像及独立合成数据。核对镜像 ID、OCI、前端 revision 和运行期方法声明，再验收正向删除和全部负向条件、列表真实刷新、原件 GET/HEAD 关闭、失败数据不变、审核角色不自动获删权；补跑 pytest、真实隔离 PG/知识库引用夹具及浏览器流程。只认可对应镜像的独立结论，不沿用 v0.2.2 PASS。

未授权切换正式环境。后续须先取得 QA 结论、确认删除授权名单，检查活动任务/状态挂载/引用存储、保留现有镜像及私密配置，再取得用户最终部署许可。回滚保留正式镜像；如候选实际产生软删除，旧版本不会公开 `.deleted` 元数据，但不得自动恢复上传或删除准备记录，先只读核查。此次未执行切换、恢复或正式删除。
