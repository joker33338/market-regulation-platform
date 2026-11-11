# Q021-004：文档 I/O 被误归为引擎依赖不可用

P2，诊断修复第 2 轮。受测源码 `0770e65578b6cf128cb497afbd521901b59e6719`，测试提交 `38837ea464717d943a46cb4e1917c12b5688d1df`。系统策略阻塞不是此代码缺陷；本缺陷仅为新诊断的错误归因。

独立只读快照、既有断网非 root 镜像运行 110 个唯一方法：107 PASS、3 FAIL、0 ERROR/SKIP。原正式 8 合同及 Fix 104 个受影响方法均通过，另 3 个 QA HTTP 边界也通过；新增 3 个文档 I/O 控制失败。8 和 104 存在包含关系，不相加。无模型、真实 HTTP、数据库、语料或密钥。

复现与期望：

1. `_error_page(1, 'ocr', {}, FileNotFoundError(errno.ENOENT, ...))`：应保留失败，但不附引擎不可用诊断。
2. `_error_page(1, 'structure', {}, PermissionError(errno.EACCES, ...))`：无结构化策略码时只是文档读取权限错误，不应记依赖不可用。
3. worker 已缓存成功初始化的 engine，`engine.predict` 因输入临时页不存在抛 FileNotFoundError：应保留一般解析失败，不应推断 LOCAL_DEPENDENCY_ERROR。

实际：三处都产生 LOCAL_ENGINE_UNAVAILABLE / LOCAL_DEPENDENCY_ERROR。根因是 `attached_diagnostic` 将任意 OSError 当加载错误，而页处理与 worker 全部推理异常又复用了它。

允许最小修复：只有明确加载边界可推断普通 OSError 为依赖错误；文档/推理边界只传播经过正规化的可信诊断、明确结构化策略证据或适用的导入错误。保留 577/1260 初始化、ImportError、cause/context、跨 worker pickle、Native 候选、构造/enter 失败兜底以及四字段脱敏控制。不更改解析失败/复核语义，不放宽权限或改变系统策略。

命令：`python -B -m unittest tests.test_v021_document_io_diagnostics -v`，再运行前轮 8 合同和受影响定向方法。最多 3 轮策略不变。修复后交接完整真实 Git SHA，由 QA 独立复验；本轮不全 191、不执行模型/云调用、不变更依赖或数据库。

Fix 报告运输原 d627 中存在乱码路径和空 blob 哈希，已另行更正为 fd9fd3e1234438f2556ebbebb57ef29fa5ead229；源码仍为 0770。本交接不因报告修复而忽略代码失败。版本保持 BLOCKED，Windows 与实际 MinerU 尚未通过。
