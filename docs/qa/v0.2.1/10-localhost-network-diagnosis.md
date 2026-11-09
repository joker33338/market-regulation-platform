# Windows 到 Docker localhost 诊断与待启用方案

日期：2026-11-09。只读诊断完成，未调整环境或启动中继。本报告安全重建UTF-8，替代此前编码损坏内容。

## 实测根因

Docker context 为 desktop-linux，本机 named pipe，Client/Server 29.4.1，Docker Desktop Linux/WSL2。Uvicorn PID1 确实监听 0.0.0.0:8180；内部 HTTP 已通过。

网络为 internal bridge。Options 只有 enable_ipv4=true、enable_ipv6=false，没有配置 gateway_mode，默认是 nat，不能误称显式 isolated。容器 endpoint.Gateway 为空，只有直连路由，没有默认网关。

HostConfig.PortBindings 保留127.0.0.1:8180请求，但实际 NetworkSettings.Ports 对应空列表；Windows无8180监听且无端口冲突。Test-NetConnection=False，Invoke-WebRequest 报 System.Net.WebException“无法连接到远程服务器”，未到应用或认证路由。

三个防火墙配置均开启且未修改。当前 Docker 未生成发布映射，证据不支持先归因防火墙。Docker及防火墙读取正常，没有 SANDBOX_RESTRICTION 或审批拒绝。

上游维护者解释端口通过容器默认网关网络发布；只有 internal 网络的容器无默认网关，因此发布请求保留但实际不生效。与本机事实一致：[Moby讨论](https://github.com/moby/moby/discussions/53256)、[Docker官方文档](https://docs.docker.com/engine/network/port-publishing/)。

EXPOSE、再次修改正确的监听地址、关闭防火墙不是修复。普通第二bridge会引入出站；双网络代理也会给予代理出站能力，不直接使用。没有启用host网络、privileged、Docker socket挂载、任意代理或全局防火墙修改。

## 可审查的定目标中继

辅助入口：`tests/start_qa_loopback_relay.ps1`。这只是Windows本机测试通道，不是Docker NAT恢复或生产方案。

```text
powershell -NoProfile -File tests/start_qa_loopback_relay.ps1 -CompileOnly
powershell -NoProfile -File tests/start_qa_loopback_relay.ps1 -EvidenceDirectory <最终完整基线证据目录>
# 仅明确批准启用后，才能添加 -Enable。
```

默认只预检、不监听。CompileOnly只编译.NET类型。启用后仅绑定127.0.0.1:8180，每连接只使用固定真实容器完整ID的docker exec，运行固定标准库socket代码连接容器127.0.0.1:8180。无shell、无可指定目标、不实现CONNECT/SOCKS、不启动第二个服务，不读取或记录HTTP体与Token。stdout仅作为内存字节流。

预检固定容器ID/running、精确Uvicorn CMD、只读source bind、非root/只读根目录/no-new-privileges和唯一internal网络。可选源码label若存在须匹配；替代证明为冻结manifest摘要与实际容器全部文件内容哈希、文件集合逐一相符，不要求重建容器补label。不可核验就阻塞。

固定源码ee7dd7e6c8243e98c9f1bf995a4c57c555611786，manifest SHA256：`e925925018b1dd0a9da58ee8e2aaf764d74d8ae7b034ce3ae6f48e023bfaba2b`。

串行最多一个活跃连接；OS backlog可能短暂排队，轮询发现额外连接时接受并关闭，不宣称绝对无排队。空闲10秒、单连接60秒、总生命期10分钟。StopFile出现即停止；关闭stdin使固定socket程序退出，超时回收docker CLI。短超时不适合长时间真实OCR，仅用于合成启动验证。

参数仅Enable、CompileOnly、EvidenceDirectory、StopFile，没有任意目标/容器/命令参数。不安装依赖或创建Python环境；不改变应用出站、网络、数据库或原应用服务。

## 已做检查及未验证边界

PowerShell 5.1 AST无错误；Add-Type编译成功。用冻结证据执行默认预检，真实源码内容、CMD、internal网络和硬化核验通过，明确输出no listener started。未传Enable，未启动后台或监听。双向TCP、停止/回收、宿主可达性运行测试尚未执行，不能声称localhost已修复。

启用批准后再验证Test-NetConnection、Invoke-WebRequest、认证、合成上传/解析、重启、断连/空闲/额外连接及隔离。原OpenAPI禁用，不新增endpoint凑测试。容器间访问和专用PG仍需独立测试，中继不代表它们通过；不重跑191项或模型。

## 获批启用后的真实工具阻塞

用户已明确批准限时启用和网络回归。随后尝试通过 Start-Process 隐藏启动已审脚本，但执行工具在 CreateProcess 阶段返回 `rejected: blocked by policy`，整条启动命令没有执行。因此没有创建后台中继、没有建立监听，也没有取得宿主 HTTP 成功结果；没有换 shell、编码或启动方式绕过。

此新增阻塞记作 **SANDBOX_RESTRICTION（仅指已经观察到的执行工具策略拒绝）**。它与此前 Docker internal-only 无默认网关而不发布端口是两个独立问题。没有证据证明 Windows 防火墙、WDAC 或本机 PowerShell 自身拒绝了中继，不能把工具拒绝归因给它们。

后续只读核对排除了诊断命令自身：`-File ...start_qa_loopback_relay.ps1` 后台进程数为0，Windows 8180监听数为0。未再次尝试启用，没有遗留需要停止的中继进程。应用容器的内部服务不受影响，宿主访问仍为BLOCKED。

## 用户在 Windows 宿主手动执行的同一入口

以下命令从本轮独立 QA v0.2.1 工作树根目录运行，证据目录是已实际通过预检的最终完整基线目录。无需管理员提权，不建议更改执行策略或使用 ExecutionPolicy Bypass；仍服从本机既有安全策略。若本机策略拒绝，应保留错误并由用户决定，不绕过。

先在第一个普通 PowerShell 窗口前台启动（最多10分钟；此命令没有由代理执行）：

```powershell
$evidence = (Resolve-Path '.\local\full-baseline-20261109T024252Z-723c3532').Path
$stopFile = Join-Path $env:TEMP 'market-qa-loopback-relay.stop'
& '.\tests\start_qa_loopback_relay.ps1' -EvidenceDirectory $evidence -StopFile $stopFile -Enable
```

若停止文件已存在，脚本会安全拒绝。仅在确认它来自先前已结束的测试后，由用户明确处理；不在命令中自动删除。

在第二个普通 PowerShell 窗口检查真实宿主连通：

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 8180
(Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8180/' -TimeoutSec 15).StatusCode
```

这两个命令预期分别为 TcpTestSucceeded=True、200；当前尚未在启用通路后执行，不能预写为PASS。根页面不需要Token，避免在测试命令里展示凭据。

完成后在第二个窗口主动停止：

```powershell
$stopFile = Join-Path $env:TEMP 'market-qa-loopback-relay.stop'
New-Item -ItemType File -Path $stopFile -ErrorAction Stop | Out-Null
Get-NetTCPConnection -LocalPort 8180 -State Listen -ErrorAction SilentlyContinue
```

脚本会观察停止文件、结束转发并关闭监听；也有10分钟总上限。即使用户手动验证成功，也只是限时本机定目标通路，不代表 Docker NAT 已恢复、容器可任意出站、OpenAPI已开放或数据库阶段通过。
