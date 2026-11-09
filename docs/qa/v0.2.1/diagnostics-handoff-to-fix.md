# 引擎不可用诊断与构造异常最小交接

业务源码：`ee7dd7e6c8243e98c9f1bf995a4c57c555611786`。QA 合同提交：`5e752376d8c8855a974be5add9f0902c324fc22d`。

## 范围与实际证据

系统策略分别阻止本地 sklearn 扩展及独立官方客户端的 libssl，详见 [只读诊断](10-Windows执行策略诊断.md)。两者都有 CodeIntegrity 3033/3077，真实 HTTP 为零。官方客户端未导入 Paddle，不能为“解耦”重构原本独立的客户端。系统阻塞本身不是业务代码缺陷，也不授权改变系统策略或依赖。

OBS021-001 为新增可观测性需求：当前通用 ImportError 无法保留安全的组件/不可用原因；新增结构化诊断，不能据异常类型或模糊消息臆断策略。Q021-003 为 P2 可复现代码边界：`DualEngineRouter.parse` 的 `parser_factory()` 构造位于本地 try 之外，合成构造异常会直接逃出，未保存本地失败候选，也无法进入既有授权的远端尝试。它与当前机器的具体策略拒绝分开记录。

8 个最小合成方法在精确业务源码执行：0 PASS、2 FAIL、6 ERROR。5 个错误来自新增诊断模块尚不存在，1 个来自已证实的构造异常逃出；2 个断言失败为页级诊断丢失及 worker 包装异常未保留附件。没有执行真实模型或 HTTP。最初本地 runner 拒绝了 Windows asyncio 的自身 loopback IPC，修正为只允许 loopback IPC 后保留独立证据；正式结论取修正后记录，不把 runner 环境错误算成业务失败。

## 最小接口与行为

新增 `qa_core.document_parsing.diagnostics.engine_unavailable(exc, *, component)`，返回且仅返回 `status/reason/exception_type/component`。`status=LOCAL_ENGINE_UNAVAILABLE`；组件为 `paddle` 或 `mineru_transport`。只有结构化 winerror 577/1260（含 cause/context）支持 `WINDOWS_POLICY_BLOCKED`；其余未证实策略的导入错误记 `LOCAL_DEPENDENCY_ERROR`。受信外部系统日志可在 QA 报告中给出确证分类，不能让 HTTP 自报或异常任意文本提升为策略证据。

诊断字典不能包含异常原文、路径、Token、文书内容或完整栈。原始栈仍仅写本地忽略证据。运行时导入/初始化失败可在既有 IngestionError 上附可 pickle 的 diagnostic，跨 worker 传播；既有错误类型/状态枚举兼容保留。`DocumentParser._error_page` 在 `raw_result.engine_availability` 保留该安全附件。

将本地 parser 构造纳入本地异常处理，持久化失败候选，保留复核信号；继续走原 SHA、授权和预算判断。`quality.routing_trace.local_availability` 保留本地不可用诊断。远端客户端初始化失败且没有发送请求时，`remote_availability.status=BLOCKED`、`api_status=NOT_TESTED`，保留安全 reason/component；不得记 API_FAIL 或调用数大于零。原有 failure_reason 兼容保留。

## 允许与禁止

允许最小诊断 helper、runtime 安全附件、DocumentParser 附件保留及 DualEngineRouter 构造兜底/可观测性修改。Fix 增加必要的成功分支、上下文链和原生产权限正反控制。不得改模型、依赖、数据库/schema、业务阈值、授权清单、预算、域名、生产默认或原始资料；不新建 Python/Docker 环境，不绕过系统策略。真实官方请求仍受既有协调器放行与同一清单/账本限制。

目标命令：`python -B -m unittest tests.test_v021_engine_diagnostics -v`，再按源码变更范围选择既有 DocumentParsing、DualEnginePolicy 和 TEST_BATCH 安全方法。无需为本次纯诊断修改重跑真实模型；新源码须交接完整 Git SHA 后由 QA 独立验证。不要因合成合同转绿宣称已解除 Windows 阻塞、实际 API 已通过或版本质量已达标。
