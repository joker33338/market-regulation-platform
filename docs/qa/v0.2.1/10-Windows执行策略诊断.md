# Windows 执行策略与客户端隔离诊断

源码 `ee7dd7e6c8243e98c9f1bf995a4c57c555611786`。本次仅使用既有环境读取元数据、系统日志，并构造不联网的官方客户端；不加载模型、不上传、不重试失败任务、不更改环境或执行策略。

## 两条独立阻塞

| 链路 | 最小定位 | 证据 | 状态 |
|---|---|---|---|
| 本地 Paddle | PaddleOCR → PaddleX → sklearn.cluster → `_k_means_common.cp312-win_amd64.pyd` | 首任务完整 worker 栈，CodeIntegrity 3033/3077 | LOCAL_ENGINE_UNAVAILABLE / WINDOWS_POLICY_BLOCKED |
| 官方客户端 | OfficialMinerUClient → httpx → ssl → `_ssl`，实际拒绝 `libssl-3-x64.dll` | 无网络构造完整栈，CodeIntegrity 3033/3077 | WINDOWS_POLICY_BLOCKED |

两个系统事件均明确签名/完整性策略拒绝；补充3077 XML的PolicyName为VerifiedAndReputableDesktop，表明Smart App Control执行链。不能笼统称已确证企业自定义WDAC，也不能说依赖已损坏。LOCAL_DEPENDENCY_ERROR 当前未证实。具体二进制路径、SHA256、完整栈、事件消息与策略标识仅在本地忽略证据内，供管理员核验。

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

## 政策类型与可行方案更正

根协调器只读3077 XML记录PolicyName=VerifiedAndReputableDesktop，PolicyGUID与PolicyID分别保存，后者的值为27555.1000.240208，不把版本样式字段与GUID混同。CiTool只读列表返回非0，未成功列出全部策略、未提权或更改策略。微软文档将该friendly name对应SAC执行模式，3077为阻止事件。[Microsoft Learn](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/test-your-app-with-smart-app-control)

SAC目前不提供单个应用例外，因此撤回“管理员加hash白名单即可放行”的笼统方案。管理员应先确认本机策略类型和受支持的信任方式，核验供应方可信签名依赖的可得性与兼容性；不自行签名、替换/复制DLL、关闭策略、改注册表或换解释器。任何安装/版本变更须另行批准，本次不实施。[Microsoft Support FAQ](https://support.microsoft.com/en-gb/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions)

另一方向仅为待明确批准的合规独立测试环境：不能自行把Docker或换环境当策略绕过方案。原解释器的核准后断网验证材料默认不执行、先核验原二进制SHA；若合法供应方变更使SHA不同，应重新审核材料，不继续原验证脚本。管理员包保留具体文件/签名/事件，已同步更正上述方案。

最新业务源码67709c4989781594dd6c4723666fdb2c21caaa7b的111项合成定向通过，只证明代码诊断和兜底正确，不证明系统限制解除或真实API通过。未重复加载受阻模块、未运行模型/云端；本地与HTTPS仍WINDOWS_POLICY_BLOCKED。
