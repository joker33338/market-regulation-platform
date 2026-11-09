# Windows 执行策略与客户端隔离诊断

源码 `ee7dd7e6c8243e98c9f1bf995a4c57c555611786`。本次仅使用既有环境读取元数据、系统日志，并构造不联网的官方客户端；不加载模型、不上传、不重试失败任务、不更改环境或执行策略。

## 两条独立阻塞

| 链路 | 最小定位 | 证据 | 状态 |
|---|---|---|---|
| 本地 Paddle | PaddleOCR → PaddleX → sklearn.cluster → `_k_means_common.cp312-win_amd64.pyd` | 首任务完整 worker 栈，CodeIntegrity 3033/3077 | LOCAL_ENGINE_UNAVAILABLE / WINDOWS_POLICY_BLOCKED |
| 官方客户端 | OfficialMinerUClient → httpx → ssl → `_ssl`，实际拒绝 `libssl-3-x64.dll` | 无网络构造完整栈，CodeIntegrity 3033/3077 | WINDOWS_POLICY_BLOCKED |

两个系统事件均明确违反企业签名级别或代码完整性策略，不能将其说成已经证实的包损坏。LOCAL_DEPENDENCY_ERROR 当前未证实。具体二进制路径、SHA256、完整栈、事件消息与策略标识仅在本地忽略证据内，供管理员核验。

官方客户端构造前、后 `sys.modules` 中 paddle、paddleocr、paddlex、sklearn 模块均为空；这四族 import 审计事件也为零。诊断在任何潜在网络组件导入前安装 socket/DNS 拒绝守卫，实际网络尝试为零。官方客户端已与模型初始化分离，无需为此重构客户端。父进程 SSL 受阻与子进程 sklearn 受阻必须分别处理。

本次 MINERU_API 为 NOT_TESTED，集成状态 BLOCKED；不是 MINERU_API_FAIL。没有 API HTTP 响应、上传或官方收据。DUAL_ENGINE 为 BLOCKED；没有新的端到端质量结论。

## 版本和兼容性边界

| 组件 | 当前元数据版本 |
|---|---|
| CPython | 3.12.16 |
| paddlepaddle | 3.2.2 |
| paddleocr | 3.3.2 |
| paddlex | 3.3.10 |
| scikit-learn | 1.9.1 |
| numpy | 2.5.4 |
| scipy | 1.18.1 |
| httpx / httpcore | 0.28.1 / 1.0.9 |

上述项目固定版本与 requirements.txt 相符。已读取安装元数据 Requires-Dist 并保留本地证据；版本存在和满足静态约束不等于二进制运行兼容。历史成功页的证据未记录完整解释器及依赖指纹，不能凭历史成功认定当前环境相同，也不能断言是谁、何时改变了策略或依赖。原虚拟环境和模型未被本轮修改。

## 需要管理员决定的最小方案

1. 对当前确切二进制 SHA256、签名和系统事件进行核准，按组织现有执行策略允许必要组件。不得直接关闭策略、替换/复制 DLL、换解释器或关闭网络保护来规避拒绝。
2. 若策略管理员明确认可，可评估既有隔离 Linux 测试镜像承载独立官方 API 对照：不安装新包、不加载模型，只允许固定官方 HTTPS 来源出站，继续使用同一私有清单、实际文件 SHA 与持久账本；先证明其现有依赖可用和权限边界。该方案尚未执行，不因镜像存在就视为获准绕过 Windows 策略。

两个方案均不新建批次重置 32 调用/3 内容预算，不复制真实原文件，不重发不确定 POST。诊断错误分类是新增可观测性需求，应经最小回归交接实现；系统阻塞本身不是业务源码缺陷。
