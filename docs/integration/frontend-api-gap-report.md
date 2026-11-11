# v0.2.2 后端接口缺口与交付边界

审计依据：维护基线 `5dd44b97710db0d3bdb84bcec6e1624dd70205dc` 实际 FastAPI factory、全仓路由扫描、现有 Vue 七页面及 apiCapabilities/parse/documentFiles 适配层。仓库仅一个 FastAPI factory，无其他 APIRouter。原基线 9 个 API，匿名 OpenAPI 关闭；已有根路径上传工作台。

## 原有缺口及处理顺序

| 优先级 | 缺口 | 最小方案 | 不扩展范围 |
|---|---|---|---|
| P0 | 无原文件 HTTP 读取，artifact 不能预览原文 | owner 身份目录+真实 Hash 校验，GET/HEAD/Range | 不允许任意路径，不修改原件 |
| P0 | 任务文件、上传、PG parse_id 不能混用 | 沿用 source_file_id/database_parse_id 映射并显式输出 | 不推导 ID |
| P1 | 无文档/任务列表、分页与筛选 | 现有上传元数据和 SQLite 只读适配 | 不迁移数据，不建新任务系统 |
| P1 | 无完整待复核 HTTP 查询 | documents.requires_review + owner 条件 | 不仅依赖 v_review_queue，不新增状态机 |
| P1 | 无结构/Chunk/版本 HTTP 预览 | 授权结果引用+已有 preview_chunks，public 版本查询 | 不直接暴露任意文件路径，不入库/发布 |
| P1 | 无检索 HTTP | 已有 keyword_search/retrieve 适配，public ACTIVE | 不使用 QA Schema，不生成回答 |
| P2 | 无真实首页/健康查询 | 明确统计来源/窗口，只读健康 | 不模拟进度，不推理/云请求 |
| P2 | 无可用 OpenAPI | 认证读取实际 OpenAPI + 离线导出 | 不开放匿名内部文档 |

## 暂不实现与原因

- 审核四个写按钮：缺少正式修订、操作者与审计契约，不新增数据库/状态机，必须禁用。
- 入库批次、发布、回滚：已有 CLI 授权和审核门禁不能由前端需求绕过；本轮交付预览及版本只读。
- 日志/资源监控、引擎实际在线探测：没有可信持久记录或将触发昂贵/远程动作；本轮只暴露已证实的配置/查询结果。
- 发行机关、法效日期、历史版本检索：当前检索投影没有足够可靠来源，拒绝伪造或静默忽略筛选。
- 浏览器端完整联调：用户明确前端只读。WorkBuddy 必须接入真实适配层与开关后进行独立验证；后端测试不等价于页面通过。

## 开发隔离

独立后端工作树 `market-regulation-platform-backend-api`，分支 `codex/backend-api-v0.2.2`。原始 main 不动；历史 Fix 的初稿已做逐文件 SHA256 备份，前端全目录未跟踪状态保持原样。前端旧分支不自动改名或切换；新前端/联调分支尚未创建，不声称已通知 WorkBuddy。

## 测试与证据

基线审查与初稿 15 项合成接口测试已执行通过，但不替代各模块提交后的独立测试。最终实际测试、完整源码 SHA、修改文件与仍待 QA 的项目随模块记录更新，不沿用 v0.2.1 签发结论作为新功能 PASS。
