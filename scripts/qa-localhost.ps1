param([ValidateSet('start','stop','status','restart','rebuild','cloud-client')][string]$Action = 'status',
      [string]$Python = '')
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $workspace
try {
    $env:QA_LOCAL_ROOT = (Join-Path $workspace 'local/qa-localhost').Replace('\','/')
    $composeArgs = @('compose','--project-name','market-regulation-qa-localhost','-f','compose.qa-localhost.yaml')
    function Invoke-Compose([string[]]$Arguments) {
        & docker @composeArgs @Arguments
        if ($LASTEXITCODE -ne 0) { throw '独立Compose操作失败；未操作原服务。' }
    }
    if ($Action -in @('start','rebuild','cloud-client')) {
        if (-not $Python) {
            $sharedPath = (& git rev-parse --path-format=absolute --git-common-dir).Trim()
            $agentConfig = Get-Content -LiteralPath (Join-Path $sharedPath 'agent-local.json') -Raw -Encoding UTF8 | ConvertFrom-Json
            $Python = Join-Path $agentConfig.originalRoot '.venv/Scripts/python.exe'
        }
        if (-not (Test-Path -LiteralPath $Python)) { throw '请用-Python指定已有环境；本脚本不安装Python依赖。' }
        New-Item -ItemType Directory -Path $env:QA_LOCAL_ROOT -Force | Out-Null
        $routeFile = Join-Path $env:QA_LOCAL_ROOT 'host-routes.json'
        @(Get-NetRoute -AddressFamily IPv4 | Select-Object -ExpandProperty DestinationPrefix) | ConvertTo-Json | Set-Content -LiteralPath $routeFile -Encoding UTF8
        & $Python -B deploy/qa-gateway/prepare_local.py --root $env:QA_LOCAL_ROOT --host-routes $routeFile
        if ($LASTEXITCODE -ne 0) { throw '本地准备或安全前检失败。' }
    }
    if ($Action -eq 'rebuild') {
        & docker tag sha256:b4010953b65e06c2d1000fdcd129f6fcceeed9b9a5d48a12266d3365a610a2b1 market-regulation-qa-base:b4010953
        if ($LASTEXITCODE -ne 0) { throw '基础镜像不存在或不匹配。' }
        & docker build --pull=false -f deploy/qa-gateway/Dockerfile -t market-regulation-qa-gateway:v0.2.1-nft1 .
        if ($LASTEXITCODE -ne 0) { throw '新独立镜像构建失败。' }
        Write-Output '新镜像已构建；未自动重建正在运行的任务。'
    } elseif ($Action -eq 'start') {
        $cloud = & docker @composeArgs --profile cloud ps --status running --services
        if ($cloud -match 'client') { throw '独立云测试客户端正在运行；先安全完成任务并停止。' }
        $running = @(& docker @composeArgs --profile local ps --status running --services)
        if ($running.Count -gt 0) {
            Write-Output '已有本地QA服务运行；本次只显示状态，不重建或中断任务。'
            Invoke-Compose -Arguments @('--profile','local','ps')
            return
        }
        Invoke-Compose -Arguments @('--profile','local','up','-d','--no-build','--pull','never','app','ingress')
        Write-Output '独立本地QA入口：http://127.0.0.1:8180；默认仅匿名Mock。'
    } elseif ($Action -eq 'cloud-client') {
        throw '真实云客户端须由QA确认无运行任务后显式启动cloud profile；普通入口脚本不会自动开启外传。'
    } elseif ($Action -eq 'stop') {
        Invoke-Compose -Arguments @('--profile','local','--profile','cloud','stop')
    } elseif ($Action -eq 'restart') {
        throw '先完成当前任务，再运行stop与start；本脚本不会强制中断任务。'
    } else {
        Invoke-Compose -Arguments @('--profile','local','--profile','cloud','ps','-a')
    }
} finally {
    Pop-Location
}
