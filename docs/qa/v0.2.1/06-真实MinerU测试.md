# TEST_BATCH 官方 API 最新真实验证

截至2026-11-09 08:52 UTC。业务源码 `67709c4989781594dd6c4723666fdb2c21caaa7b`，业务交接 `949bc4b109e98ddd6f8b939971b1ac2dbf9955ae`；Linux部署配置 `04ea352cb60a43f429f09415fad455be74067787`，代理修复 `6ae4e19aa67853e0e54ce85faf105a6822706c12`，QA续跑入口 `396c7cf`。

**S00007完整官方链路PASS，首批整体PARTIAL，质量及Dual仍BLOCKED。** 本节取代后文历史Windows阶段“真实HTTP为零”的现状描述。

## 隔离与独立验收

沿用用户固定19SHA的“均为自有都可以上传”“已经检查，没有敏感内容”声明、原期限、owner及批次ID；私有清单ACL已核，未扩大未来范围。经明确批准新增独立Linux环境，未改Windows SAC。固定镜像为`sha256:b18606a0402b488fd31e277c5d15fed51ac7453637deeda06c4c42e1f366db9e`。

网关及客户端实际nft inet qa_guard三链双栈DROP、优先级-150，在Docker DNS DNAT前拦截通用DNS。网关仅允许三个原官方域审核公网IP:443；客户端只到固定代理。PID1 UID65534，五组capabilities为0、NoNewPrivs=1，DNS和直连外网负向实测拒绝。Token仅stdin传给已降权进程内存；网关无Token/语料挂载。纯云环境不挂模型、禁止Paddle/sklearn导入，不伪造本地OCR成功。

标准httpcore固定Accept:*/*被辅助代理错误拒绝，Q021-005红测10方法9PASS/1ERROR。最小固定值兼容修复在独立Git快照10/10PASS；非固定值、重复头和原安全边界仍拒绝。精确httpx transport无Key探针TLS成功并在源站HTTP写入前终止。续跑入口子集、防重发边界4/4PASS，两组工具检查不与原业务111项相加。

## 首批三份真实结果

| 样本 | 页数 | 实际结果 | 处理 |
|---|---:|---|---|
| S00014 | 1 | 早期代理CONNECT403，源站HTTP确证0 | FAILED_NO_ORIGIN_HTTP，保留POST占位1、不重发 |
| S00007 | 7 | API POST、上传信息GET、OSS PUT、轮询GET、CDN下载GET共5次HTTP200 | 完整官方链路PASS，云质量告警，保留两候选 |
| S00010 | 5 | POST、上传信息GET、OSS PUT及两次轮询GET均200；下一轮询ConnectTimeout | 结果未下载，保留本地候选，不再POST |

原canonical账本累计**12/32预留、3/3唯一SHA**；每任务仍8次、轮询至少10秒。12包含早期代理拒绝预留1和正式官方调用尝试11；HTTP200响应10、连接超时1。超时请求是否到达源站未知，不能写源站实发11。成功上传PUT为2，不等于两份解析均已完成。无未知POST重发、第二账本或换批次清零。

## 已保存产物及实际质量

S00007保存Markdown11359字节及两个JSON200377/283458字节，摘要仅留匿名本地证据；归一化为document-parsing-v1，输入SHA绑定正确，页1～7完整。Native和云端、原始和规范化产物均保留，真实产物不进Git。

Native7页成功、3595字符/4表，路由reasons为空；云端7页、1971字符/4表，needs_review且reasons=[table_alignment_review]。现有云候选原因数不多于本地的条件未满足，因此remote_quality_insufficient并保留Native，未改阈值或强选云。这是质量选择而非API失败。runner粗略local_engine_status=BLOCKED指无OCR模型，不覆盖Native成功事实。

S00007第4页同SHA已审标准为1表14行4列30单元格。对已存943字节HTML作有界离线解析：行列、位置和rowspan/colspan严格一致**1/1**；结构及全部文本同时一致**0/1**；按相同位置和跨度，文本严格匹配**25/30**单元格。规范化cells未展开记**NOT_AVAILABLE**：源码明确保留远端HTML、避免不可信跨度展开并要求复核，HTML未丢失，不把空cells算官方识别率0%，不为此制造Bug。本次未完成云Markdown结构语义或同页全文CER，不把单元格文本匹配率当全文CER。

S00010保留Native5页、10017字符，needs_review原因为layout_enhancement_failed，无模型条件的版面增强失败可见，不冒充OCR成功。远端结果未下载，不能算该文件云质量。S00014无真实云预测，未完成整个测试集各引擎覆盖。

## 停止与恢复

未重跑模型、完整回归或数据库。事后源SHA重新检查**3/3不变**。确认无活动任务后正常停止client/gateway，使用现有脚本恢复app/ingress，实际127.0.0.1:8180根页HTTP200、HTML；没有Push/生产操作/部署。

后续仅经协调器复核原期限、SHA、账本及远端任务状态后恢复S00010已有任务轮询，不得新POST；本轮未恢复。S00014保留失败不重发。Dual仍BLOCKED、业务阈值未定义、整版继续BLOCKED。

---

## 以下为历史阶段记录，不代表最新状态

# TEST_BATCH 官方 API 真实验证（历史）

受测源码：`ee7dd7e6c8243e98c9f1bf995a4c57c555611786`。Fix 交接：`e16b4e241651a0641bdccac8420a64290e40869f`。

## 授权和独立安全验收

用户针对当前固定 19 个正常候选声明“均为自有都可以上传”，随后确认“已经检查，没有敏感内容”。私有清单按这些原始声明记录来源、第三方外传权及人工敏感检查；不将授权扩大到未来文件、异常文件或其它数据。原文件 SHA256 重新计算后 19/19 一致。

最终源码独立授权安全验收为 38/38 PASS，无失败、错误或跳过。包含批次授权、实际字节校验、过期/撤销、owner 隔离、伪造拒绝、HTTP 副本、持久预算及工厂绑定守卫。此前源码 2158077 的 3 个工厂控制失败属于 QTB-001；最终源码已修复并独立复验。安全 Mock 不代表真实 API 成功。

清单位于 Git 忽略的专用私有目录。Windows ACL 实际读回：继承关闭，仅当前操作员可写。清单不在 HTTP 上传目录。源码按 Windows 换行规范化后与 Git 内容一致，交接报告 Git blob SHA256 核验通过；清单未过期、未撤销。

## 首批预检和实际执行

| 匿名样本 | 类型 | 页数 |
|---|---|---:|
| S00014 | 低质量扫描 PDF | 1 |
| S00007 | 有框线表格 PDF | 7 |
| S00010 | 复杂排版 PDF | 5 |

共 3 个唯一 SHA、13 页。正式入口 dry-run 为 READY，零请求。协调器已复核放行同一批次逐文件 auto → remote。Key 只在当前进程内存读取，未写入报告或 Git。

每任务上限仍为 8 次请求、50 页；批次跨任务、模式和重启累计上限 32 次请求、3 个唯一内容。轮询至少 10 秒。6 个模式若均进入云端，最少约 24 次请求；轮询可能先耗尽预算，不保证所有模式均能完成。不确定 POST、429 或预算耗尽即停止，不新建批次重置额度。

固定 HTTPS 来源仅为既有官方 API 与两个既有上传/下载来源；不接受任意 URL，不通过重定向扩展白名单。Paddle 在独立 spawn worker 中先安装离线保护再导入模型；父进程官方客户端不安装该保护。

本次实际仅启动 S00014 auto，随后安全停止：

- 本地 worker 导入 paddlex → sklearn.cluster._k_means_common 时 DLL 加载失败，系统提示应用程序控制策略阻止该文件。该页未完成真实 OCR；候选的 paddle_ocr 标识不等于推理成功。
- routing_trace.failure_reason=ImportError 来自云链路捕获。现有完整栈只证明上述本地异常，尚不能证明两处异常同源；云链路导入原因待无网络诊断确认。
- 真实 HTTP 审计事件 0、上传 0、持久请求账本尚未创建；没有 POST 占位或官方收据。未启动 remote 或其它两个样本。
- 原始失败栈、任务检查点和运行记录仅留本地忽略证据；不修改失败候选，不安装依赖、更换 DLL、关闭保护或绕过系统策略重试。

真实官方链路当前 **BLOCKED**，尚无真实 MinerU 质量或费用证据，不宣称已完成真实回退。

## 指标边界与下一步

没有新的 Paddle、Structure 或 MinerU 完整集预测。历史选页结果仍绑定原始源码与文件 SHA；选页缓存不能冒充整个 PDF 的生产候选，也不能直接与云端全文计算 CER。auto 若本地足够好不上传，须如实报告零回退；remote 对照不等于自动回退已覆盖。

先定位云链路独立 ImportError；本地执行策略需管理员核准既有组件后恢复，不得绕过。恢复仍沿用同一批次、任务与账本，先核验 POST 状态。生产默认、主分支和服务配置均不改变。业务尚无验收阈值，本轮只提供有分母、来源和覆盖边界的技术指标，版本继续 BLOCKED。


## 最新无网络诊断

官方客户端独立构造已确认httpx→ssl的libssl被Windows执行策略拒绝，与Paddle的sklearn扩展拒绝分别有CodeIntegrity 3033/3077佐证。导入审计未加载Paddle，网络尝试为零。LOCAL_DEPENDENCY_ERROR未证实；MinerU为NOT_TESTED/BLOCKED，Dual为BLOCKED，不是API_FAIL。见[Windows执行策略诊断](10-Windows执行策略诊断.md)。新增8项合成诊断合同（0通过、2失败、6错误）和构造异常Q021-003已正式交接，不能通过代码修改解除系统策略，也不能把合同转绿当真实API成功。


## 最终诊断修复独立复验

源码67709c4989781594dd6c4723666fdb2c21caaa7b，报告运输949bc4b109e98ddd6f8b939971b1ac2dbf9955ae，111/111定向PASS（包含11正式诊断/IO合同与38授权安全方法，不与历史191或Fix108相加）。Q021-003/004关闭；普通文件缺失/EACCES及已就绪引擎输入I/O不再误报依赖。安全附件和真实加载错误控制保持通过。未运行模型/真实HTTP，Windows SAC仍BLOCKED、MinerU为NOT_TESTED。网络仅ee7限时中继PASS且已停止，NAT未修复。
