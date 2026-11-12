# 前端优化请求后端交接：MySQL审核台账批次

日期：2026-11-12。开发位置：唯一主目录 market-regulation-platform；分支 `codex/backend-improvements-v023`，从正式main `076d4f968aa2c71133c551007b5d082da96a5929` 创建。

依据为前端 `docs/agent-c-backend-improvement-handoff-2026-11-12.md` 与 `docs/frontend-readonly-label-fix-note-2026-11-12.md`。用户明确将原先的SQLite审核台账方案改为复用现有MySQL容器的独立审核台账；SQLite解析任务和PostgreSQL document_review/public均保持不变。

## 1. 本批已实现

| 请求 | 实现 | 完整源码提交 |
|---|---|---|
| A-P0 / B-1 | 四个审核写接口、独立MySQL追加式事件/修订、运行期能力、版本锁、幂等、owner与写授权 | `9726693ae32ba4e857f1fa2b9195bd362489aa83` |
| A-P1监控 / B-3、B-6 | API进程真实资源、数据库不可用原因、开发版与契约名分别标明 | 同上 |
| A-P2文档筛选 | 日期闭区间、时区校验、白名单排序及稳定分页 | `a47e6ea37fcf42015c6cfcc8d8615ce7d6033e4a` |
| A-P1审计日志 | 从真实审核事件查询owner范围日志，不返回修订正文、不编造历史事件 | `4b667a741154a3cc604cc1422f841401669815a5` |
| 修订正文完整性 | 保存前导空格和换行，不静默裁剪人工正文 | `d2d61107f4938f7c6f2ce758654babc35ffe8086` |

本批开发OpenAPI版本 `0.2.3-dev`，`info.x-contract-version=frontend-api-v0.2.3-draft-1`，29路径。离线真实导出为 `frontend-openapi-v023.json`，不覆盖v0.2.2冻结快照。

## 2. 审核接口与字段

沿用Bearer认证。操作者由Token映射的owner确定，客户端不能指定operator。对象存在性和owner权限先由既有PostgreSQL只读查询核验，跨owner仍404；已认证且拥有对象但未被配置为审核写入者返回403。401表示缺失/无效凭证，不把跨owner改成403以免泄露存在性。

| 方法 | 路径 | 请求及响应 |
|---|---|---|
| POST | `/api/review/{parse_id}/approve` | 公共请求字段；记录审核通过，不授予发布权限 |
| POST | `/api/review/{parse_id}/reject` | 公共字段+必填reason；记录退回，不自动创建解析任务 |
| POST | `/api/review/{parse_id}/mark-error` | 公共字段+必填reason、page；span可选 |
| POST | `/api/review/{parse_id}/save-revision` | 公共字段+必填page、content；每次追加新revision_id |
| GET | `/api/review/{parse_id}/events` | page/page_size；返回本对象审核事件及修订内容，owner隔离 |
| GET | `/api/system/audit-logs` | page/page_size，可选action四动作枚举；仅本owner审核摘要，不含修订正文 |

公共写请求头必填 `Idempotency-Key`（1–128字符）。body必填 `base_result_id`（必须等于路径parse_id）、`expected_version`（首次0，之后使用详情的review_ledger.version）。额外字段拒绝422。page必须对应原始解析结果中的真实page_number。

```json
{"base_result_id":"<parse_id>","expected_version":0,"page":1,"content":"人工修订正文"}
```

返回200回执：event_id、parse_id、base_result_id、action、operator、timestamp、version、revision_id、status、before、write_performed；`original_result_modified=false`、`publish_authorized=false`、`reparse_task_created=false`。同键同请求返回原回执；同键异请求409。不同请求并发写相同expected_version仅一个成功，其余409。源正文/原解析结果变动也拒绝409。理由、页码或修订字段缺失422；未配置台账503；存储异常503且脱敏。

事务将事件插入与头版本更新共同提交/回滚。账号只可SELECT元数据、SELECT/INSERT/UPDATE头记录、SELECT/INSERT事件，不能UPDATE/DELETE历史事件或执行DDL。修订不覆盖原始文件、OCR正文、PostgreSQL记录。

详情GET `/api/review/{parse_id}` 新增 `review_ledger`：available、reason、version、status、current_revision；只有台账可查询且当前owner在服务端writers名单中，`review_write_supported=true`。未配置/故障/未获写授权时不置true。原始`requires_review`继续表示OCR来源的复核信号，不能用它推导台账状态；批准台账记录不解除既有入库/发布门禁。

状态：首次unreviewed；保存修订pending；标错flagged；退回rejected；通过approved。每次有效动作均增加审核台账version；revision_id仅保存修订时生成，其他动作引用最近修订。前端需把修订内容作为不可信文本安全渲染。

## 3. 查询、资源和错误语义

- `/api/documents` 新增date_from/date_to（必须包含时区，闭区间）；sort_by允许uploaded_at/file_name/size_bytes/status，order允许asc/desc。默认uploaded_at倒序。同值按file_id稳定排序。缺时区、反向区间、非法排序返回422；历史metadata_mtime仍如实标明，不包装成确定上传时间。
- `/api/system/resources` 认证GET，scope固定api_process。实测memory_rss_bytes、cpu_user_seconds/cpu_system_seconds（累计CPU秒，非利用率）、uptime_seconds、threads和sampled_at。不是宿主机、容器整体、GPU或模型推理监控。失败available=false、reason与null指标，不用0伪装健康。
- `/api/stats/overview` 的parsed_documents不可用时继续available=false及null计数，新增review_store_not_configured/review_store_unavailable原因；成功reason=null。保留原文件/任务/解析记录的不同统计口径。
- 错误保持 `{error:{code}}` 兼容，不重写为前端早期建议的另一种结构。认证、403写授权、404对象不可见、409冲突、422参数、503不可用在实际OpenAPI中标明。

## 4. 初始化与运行配置

新增可选依赖 `requirements-review.txt`，PyMySQL[rsa]固定1.2.4。官方版本与连接接口依据：[PyPI](https://pypi.org/project/PyMySQL/1.2.4/)、[连接API](https://pymysql.readthedocs.io/en/latest/modules/connections.html)。原OCR依赖未升级。

审核API运行时不执行DDL。正式新库初始化工具 `scripts/provision_review_mysql.py` 需要管理员在本机安全设置REVIEW_MYSQL_ADMIN_JSON，再显式指定新库、配置输出、API容器连接主机和授权owner。工具拒绝已有库，拒绝覆盖配置，失败保留现场，不自动删除或迁移。

```powershell
python scripts/provision_review_mysql.py --database market_review --config-out local/review-runtime.json --api-host mysql --writer '<已确认的owner>'
```

管理员JSON通过本机环境提供，不放命令行或Git。生成的是专用最小权限API账号；root只允许初始化工具使用。把生成文件内容作为私密runtime.json的可选字符串值 `REVIEW_MYSQL_CONFIG_JSON` 配置。格式含host、port、database、user、password、writers；writers是owner名单，不是Token。开发host与Docker网络host不能混用。

正式运行默认无该配置，仍禁用写入。本批只创建随机独立测试库及账号，未创建/启用正式market_review、未向正式runtime注入账号。切换需在候选镜像、挂载和回滚验证后单独批准，不能把源码存在当成8180已可写。

## 5. 实际验证

命令：`python -m unittest tests.test_mysql_review tests.test_api_improvements.APIImprovementTests tests.test_frontend_api tests.test_mineru_api tests.test_schema_identity tests.test_frontend_gateway -q`。

40项通过，0失败/错误/跳过；其中6项真实MySQL隔离库测试：追加修订/批准/幂等、认证/owner/写授权、标错/退回/源变更/分页、并发版本分配及回滚、只读审计摘要owner隔离、运行账号无法改写事件。其余包括4项新查询/资源/版本测试和既有30项回归。PG原结果为模拟，只在临时SQLite与全新随机MySQL测试库写入合成内容，不声称真实PG+浏览器联合写验收通过。

隔离配置由REVIEW_MYSQL_TEST_CONFIG指向ignored文件；测试代码强制数据库名以market_review_test_开头。测试库、账号与证据保留未清理，凭据不入库、不输出。未配置该变量时MySQL测试显式跳过，不能将跳过当通过。依赖检查与git diff --check通过。

## 6. 正式8180身份与配套边界

只读核验：容器market-regulation-app-1，ID `b23198928dda0e75ff7ad40d3ce8170da825cb81922526a1db65e8b5815621c1`，running/healthy；正式镜像 `market-regulation-workbench:v0.2.2`，ID `sha256:e2a94f67ffacef9e780e06bc1484cb5e7dde4b287fa5ef340a666f5e573e52a3`，源码/OCI revision `30c4663ceb93cbba302b322f1ecee0d06d80bfb4`，另有对应sha标签。入口仍127.0.0.1:8180；Vue业务revision为63bbcc07a6b6d12a6be56fa7b0e81731c3917a45。

本批没有构建/替换正式镜像、重启8180、修改正式ACTIVE、PostgreSQL结构或旧任务；没有合并main或推送GitHub。前端本地文案修复仍须由前端负责人明确提交后集成，不复制未提交产物，不为一句文案单独重启。

## 7. 尚未交付的请求

- 入库批次、发布/回滚：没有在本批把审核台账状态冒充正式入库授权。须复用并核对既有授权/审核/发布门禁后另批实现，正式ACTIVE不变。
- 任务阶段日志、API访问日志、错误日志：现有存储没有完整持久事件来源，本批不根据当前状态编造过去事件。新审核审计来源已交付。
- total_steps/current_step/百分比：没有可确认总工作量，不给模拟进度。累计CPU秒也不冒充利用率。
- 模型真实探活：不触发推理或真实云调用，UNKNOWN/NOT_CONFIGURED保持事实。
- 检索机关/效力/历史版本筛选及新增首页指标：缺可靠字段来源/口径，未放宽后静默忽略参数，也不向正式库灌测试ACTIVE。
- C-3已停止8181容器继续保留作回滚，未删除；正式入口唯一8180。
- 本批未做浏览器写按钮验证，仍待获准隔离前端+后端联验，不冒充新QA PASS。

当前状态：本批源码与隔离测试已交付，整体优化清单为PARTIAL。WorkBuddy可按新契约准备适配，写按钮必须以实际服务能力和审核详情为准，当前正式8180不能提前解锁。
