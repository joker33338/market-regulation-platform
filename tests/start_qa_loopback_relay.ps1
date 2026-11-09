# 仅供审查的 QA 辅助入口；未指定 -Enable 时绝不启动监听。
[CmdletBinding()]
param(
    [switch]$Enable,
    [switch]$CompileOnly,
    [string]$EvidenceDirectory,
    [string]$StopFile = (Join-Path $env:TEMP 'market-qa-loopback-relay.stop')
)
$ErrorActionPreference = 'Stop'
$expectedId = '5d4e53add19f23947b1535cb2445d812c5a396511964a5d25d3aa68b656ce02c'
$expectedSource = 'ee7dd7e6c8243e98c9f1bf995a4c57c555611786'
$docker = (Get-Command docker.exe -ErrorAction Stop).Source
# 固定目标与固定程序；不解析 HTTP，不提供 CONNECT、shell 或可选目标。
$python = @'
import socket,sys,threading,os
s=socket.create_connection(('127.0.0.1',8180),timeout=5)
s.settimeout(10)
def receive():
    try:
        while True:
            b=s.recv(65536)
            if not b:break
            sys.stdout.buffer.write(b);sys.stdout.buffer.flush()
    finally:os._exit(0)
threading.Thread(target=receive,daemon=True).start()
try:
    while True:
        b=sys.stdin.buffer.read1(65536)
        if not b:break
        s.sendall(b)
finally:s.close()
'@
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($python))
# 命令行只含固定常量和 base64，不调用 shell。
$arguments = 'exec -i ' + $expectedId + ' python -B -c "import base64;exec(base64.b64decode(''' + $encoded + '''))"'
$native = @'
using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
public static class MarketQaFixedRelay {
  static long lastActivity;
  static async Task Pump(Stream input, Stream output) {
    byte[] buffer = new byte[65536];
    while (true) {
      int n = await input.ReadAsync(buffer, 0, buffer.Length);
      if (n == 0) return;
      await output.WriteAsync(buffer, 0, n);
      await output.FlushAsync();
      Interlocked.Exchange(ref lastActivity, DateTime.UtcNow.Ticks);
    }
  }
  public static void Run(string docker, string args, string stopFile) {
    // 串行中继，最多一个活跃连接；系统 backlog 可能短暂排队。
    TcpListener listener = new TcpListener(IPAddress.Loopback, 8180);
    listener.ExclusiveAddressUse = true;
    DateTime deadline = DateTime.UtcNow.AddMinutes(10);
    listener.Start(1);
    try {
      while (DateTime.UtcNow < deadline && !File.Exists(stopFile)) {
        if (!listener.Pending()) { Thread.Sleep(100); continue; }
        using (TcpClient client = listener.AcceptTcpClient())
        using (Process process = new Process()) {
          process.StartInfo = new ProcessStartInfo(docker, args) {
            UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardInput = true, RedirectStandardOutput = true,
            RedirectStandardError = true
          };
          // 子进程不继承语料、API 密钥、数据库或模型配置。
          string[] keys = new string[process.StartInfo.EnvironmentVariables.Keys.Count];
          process.StartInfo.EnvironmentVariables.Keys.CopyTo(keys, 0);
          foreach (string k in keys) {
            string u = k.ToUpperInvariant();
            if (u.Contains("DSN") || u.Contains("TOKEN") || u.Contains("SECRET") ||
                u.Contains("PASSWORD") || u.Contains("API_KEY") || u.Contains("CORPUS") || u.Contains("MODEL"))
              process.StartInfo.EnvironmentVariables.Remove(k);
          }
          process.Start();
          // 排空并丢弃错误流，不持久记录请求字节、请求头或 Token。
          Task errorDrain = process.StandardError.BaseStream.CopyToAsync(Stream.Null);
          Interlocked.Exchange(ref lastActivity, DateTime.UtcNow.Ticks);
          DateTime connectionLimit = DateTime.UtcNow.AddSeconds(60);
          Task up = Pump(client.GetStream(), process.StandardInput.BaseStream);
          Task down = Pump(process.StandardOutput.BaseStream, client.GetStream());
          try {
            while (!up.IsCompleted && !down.IsCompleted && !process.HasExited &&
                   DateTime.UtcNow < connectionLimit && DateTime.UtcNow < deadline &&
                   DateTime.UtcNow.Ticks - Interlocked.Read(ref lastActivity) < TimeSpan.FromSeconds(10).Ticks &&
                   !File.Exists(stopFile)) {
              while (listener.Pending()) { using (TcpClient rejected = listener.AcceptTcpClient()) {} }
              Thread.Sleep(100);
            }
          } finally {
            client.Close();
            try { process.StandardInput.Close(); } catch {}
            // 关闭标准输入，使 docker exec 内的固定 socket 程序退出。
            if (!process.WaitForExit(3000)) { try { process.Kill(); } catch {} }
            process.WaitForExit(3000);
            // 回收流任务异常，不打印请求资料。
            try { Task.WaitAll(new Task[] {up, down, errorDrain}, 1000); } catch {}
          }
        }
      }
    } finally { listener.Stop(); }
  }
}
'@
if (-not ('MarketQaFixedRelay' -as [type])) { Add-Type -TypeDefinition $native -Language CSharp }
if ($CompileOnly) { Write-Output '本机辅助类型编译成功；未修改 Docker，未启动监听。'; return }
$detail = & $docker inspect $expectedId
if ($LASTEXITCODE -ne 0) { throw '固定 QA 容器不可用。' }
$container = ($detail | ConvertFrom-Json)[0]
if ($container.Id -ne $expectedId -or -not $container.State.Running) { throw '容器身份或运行状态不匹配。' }
if ($container.Config.Labels.'market.qa.source' -and $container.Config.Labels.'market.qa.source' -ne $expectedSource) { throw '源码标签不匹配。' }
if (-not $EvidenceDirectory) { throw '必须提供已核验的最终源码证据目录；未启动监听。' }
$manifestFile = Join-Path $EvidenceDirectory 'snapshot-manifest.json'
if ((Get-FileHash -LiteralPath $manifestFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'e925925018b1dd0a9da58ee8e2aaf764d74d8ae7b034ce3ae6f48e023bfaba2b') { throw '冻结源码清单摘要不匹配。' }
$manifest = Get-Content -LiteralPath $manifestFile -Raw -Encoding UTF8 | ConvertFrom-Json
$sourceMounts = @($container.Mounts | Where-Object { $_.Destination -eq '/source' })
if ($sourceMounts.Count -ne 1 -or $sourceMounts[0].RW -or $sourceMounts[0].Type -ne 'bind') { throw '要求唯一的只读源码绑定挂载。' }
$attest = "import pathlib,hashlib,json;p=pathlib.Path('/source');print(json.dumps({str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in p.rglob('*') if f.is_file()},sort_keys=True))"
$attestEncoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($attest))
$actualJson = & $docker exec $expectedId python -B -c "import base64;exec(base64.b64decode('$attestEncoded'))"
if ($LASTEXITCODE -ne 0) { throw '实际源码内容核验失败。' }
$actual = $actualJson | ConvertFrom-Json
if (@($actual.PSObject.Properties).Count -ne @($manifest.PSObject.Properties).Count) { throw '实际源码文件集合不匹配。' }
foreach ($property in $manifest.PSObject.Properties) {
    if ($actual.PSObject.Properties[$property.Name].Value -ne $property.Value) { throw '实际源码内容摘要不匹配。' }
}
if ($container.Config.User -ne '65534:65534' -or -not $container.HostConfig.ReadonlyRootfs -or
    $container.HostConfig.SecurityOpt -notcontains 'no-new-privileges') { throw '所需容器加固条件不满足。' }
$expectedCommand = @('-B','-m','uvicorn','qa_core.document_parsing.mineru_api:create_app','--factory','--host','0.0.0.0','--port','8180','--workers','1','--log-level','info','--no-access-log')
if (($container.Config.Entrypoint -join ',') -ne 'python' -or
    ($container.Config.Cmd -join '|') -ne ($expectedCommand -join '|')) { throw '实际固定 ASGI 命令不匹配。' }
$networks = @($container.NetworkSettings.Networks.PSObject.Properties)
if ($networks.Count -ne 1) { throw 'QA 应用必须仅连接一个内部网络。' }
$netJson = & $docker network inspect $networks[0].Name
if ($LASTEXITCODE -ne 0 -or -not ($netJson | ConvertFrom-Json)[0].Internal) { throw '网络隔离条件未核实。' }
if (Test-Path -LiteralPath $StopFile) { throw '停止文件已存在；请审查后再明确移除。' }
if (Get-NetTCPConnection -LocalPort 8180 -State Listen -ErrorAction SilentlyContinue) { throw '端口冲突；未停止任何既有服务。' }
if (-not $Enable) { Write-Output '预检通过，未启动监听；显式 -Enable 需要启用批准。'; return }
Write-Output 'QA 固定中继已启用：一个活跃连接、空闲10秒、单请求60秒、总生命期10分钟；可创建 StopFile 停止。'
[MarketQaFixedRelay]::Run($docker, $arguments, [IO.Path]::GetFullPath($StopFile))
