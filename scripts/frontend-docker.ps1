param(
    [Parameter(Mandatory=$true)][ValidateSet('Build','Start','Status')][string]$Action,
    [string]$FrontendRoot,
    [string]$Image,
    [string]$BaseImage = 'market-regulation-workbench:candidate-v022-4fc4cf124a12',
    [ValidateRange(1024,65535)][int]$Port = 8181
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$compose = Join-Path $repoRoot 'compose.frontend.yaml'
function Assert-NativeSuccess([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step 失败，停止后续操作。" }
}
if ($Action -eq 'Build') {
    if (-not $FrontendRoot) { throw '请指定已有前端目录 FrontendRoot。' }
    $frontendPath = (Resolve-Path -LiteralPath $FrontendRoot).Path
    $revision = (& git -C $frontendPath rev-parse HEAD).Trim()
    Assert-NativeSuccess '读取前端版本'
    $changes = & git -C $frontendPath status --porcelain
    Assert-NativeSuccess '检查前端改动'
    if ($changes) { throw '前端有未提交改动，请先由前端负责人提交，避免源码 SHA 与构建内容不一致。' }
    if (-not $Image) { $Image = 'market-regulation-frontend:v022-' + $revision.Substring(0,12) }
    # 已有镜像不覆盖，保留历史产物便于回滚。
    & docker image inspect $Image *> $null
    if ($LASTEXITCODE -eq 0) { throw '该镜像标签已存在，请复用已有镜像或使用新的唯一标签。' }
    $stage = Join-Path $repoRoot ('local/frontend-build-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stage | Out-Null
    Push-Location -LiteralPath $frontendPath
    try {
        & node node_modules/typescript/bin/tsc --noEmit
        Assert-NativeSuccess '类型检查'
        & node node_modules/vite/bin/vite.js build --outDir (Join-Path $stage 'dist')
        Assert-NativeSuccess '前端构建'
        $afterRevision = (& git rev-parse HEAD).Trim()
        $afterChanges = & git status --porcelain
        if ($afterRevision -ne $revision -or $afterChanges) { throw '构建期间前端源码发生变化，不生成镜像。' }
    } finally { Pop-Location }
    Copy-Item -LiteralPath (Join-Path $repoRoot 'deploy/frontend/server.py') -Destination $stage
    Set-Content -LiteralPath (Join-Path $stage '.dockerignore') -Value "*`n!dist/`n!dist/**`n!server.py" -Encoding ascii
    & docker build -f (Join-Path $repoRoot 'deploy/frontend/Dockerfile') --build-arg "FRONTEND_BASE_IMAGE=$BaseImage" --build-arg "FRONTEND_COMMIT=$revision" -t $Image $stage
    Assert-NativeSuccess '镜像构建'
    & docker image inspect $Image --format '{{.Id}} {{json .RepoTags}} {{json .Config.Labels}}'
    Assert-NativeSuccess '镜像身份检查'
    Write-Host '镜像已构建，未启动或替换运行容器。'
} elseif ($Action -eq 'Start') {
    if (-not $Image) { throw '启动必须指定已验证的镜像标签或 sha256 ID。' }
    $env:LOCAL_FRONTEND_IMAGE = $Image
    $env:LOCAL_FRONTEND_PORT = "$Port"
    # 仅启动前端，不启动依赖，不清理同项目中的既有服务。
    & docker compose -f $compose up -d --no-deps frontend
    Assert-NativeSuccess '前端启动'
} else {
    & docker ps --filter label=com.docker.compose.service=frontend --format '{{.ID}} {{.Image}} {{.Ports}} {{.Status}}'
    Assert-NativeSuccess '前端状态检查'
}
