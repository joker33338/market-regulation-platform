param([ValidateSet('start','build','status','stop')][string]$Action = 'status',
      [int]$Port = 8180, [string]$Python = '')
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $workspace
try {
    $root = Join-Path $workspace 'local/docker-workbench'
    $deploymentFile = Join-Path $root 'deployment.json'
    if ($Action -in @('start','build')) {
        if (-not $Python) {
            $common = (& git rev-parse --path-format=absolute --git-common-dir).Trim()
            $config = Get-Content -LiteralPath (Join-Path $common 'agent-local.json') -Raw -Encoding UTF8 | ConvertFrom-Json
            $Python = Join-Path $config.originalRoot '.venv/Scripts/python.exe'
        }
        & $Python -B deploy/local/prepare.py --port $Port
        if ($LASTEXITCODE -ne 0) { throw '本地工作台准备失败；已有服务未改变。' }
    }
    if (-not (Test-Path -LiteralPath $deploymentFile)) { throw '请先运行 -Action build，复用现有环境准备本地工作台。' }
    $deployment = Get-Content -LiteralPath $deploymentFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $env:LOCAL_WORKBENCH_ROOT = $root.Replace('\','/')
    $env:LOCAL_MODELS_ROOT = $deployment.models_root
    $env:LOCAL_APP_IMAGE = $deployment.image
    $env:LOCAL_APP_PORT = [string]$deployment.port
    $env:LOCAL_DATABASE_NETWORK = $deployment.database_network
    $composeArgs = @('compose','--project-name','market-regulation','-f','compose.local.yaml')
    if ($Action -in @('start','build')) {
        & docker image inspect $deployment.image *> $null
        if ($LASTEXITCODE -ne 0) {
            $buildPreference = $ErrorActionPreference
            try {
                $ErrorActionPreference = 'Continue'
                & docker build --pull=false --build-arg "SOURCE_COMMIT=$($deployment.source_commit)" `
                    -f deploy/local/Dockerfile -t $deployment.image .
                $buildExit = $LASTEXITCODE
            } finally { $ErrorActionPreference = $buildPreference }
            if ($buildExit -ne 0) { throw '工作台镜像构建失败；没有替换运行中的服务。' }
        }
        if ($Action -eq 'start') {
            # 不自动替换不同镜像的运行服务，防止中断正在执行的解析。
            $runningImage = & docker @composeArgs ps --status running --format '{{.Image}}'
            if ($runningImage -and $runningImage -ne $deployment.image) {
                throw '工作台仍在运行旧镜像；请完成任务后先 stop，再 start。'
            }
            & docker @composeArgs up -d --no-build --pull never --wait --wait-timeout 90
            if ($LASTEXITCODE -ne 0) { throw '工作台未就绪；请查看本项目容器健康状态。' }
            Write-Output "本地持久入口：http://127.0.0.1:$($deployment.port)；访问码见 local/workbench-access-code.txt。"
        }
    } elseif ($Action -eq 'stop') {
        & docker @composeArgs stop
        if ($LASTEXITCODE -ne 0) { throw '工作台停止失败。' }
    } else {
        & docker @composeArgs ps -a
        if ($LASTEXITCODE -ne 0) { throw '工作台状态查询失败。' }
    }
} finally { Pop-Location }
