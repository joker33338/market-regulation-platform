param([Parameter(Mandatory=$true)][ValidateSet('Update','Rollback','Status','Stop')][string]$Action,
      [string]$Image)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$container=(& docker inspect market-regulation-app-1 | ConvertFrom-Json)[0]
if ($LASTEXITCODE -ne 0) { throw '无法确认现有容器，停止。' }
if ($Action -eq 'Status') {
    & docker inspect market-regulation-app-1 --format '{{.Id}} {{.Image}} {{.State.Status}} {{json .State.Health}}'
    exit $LASTEXITCODE
}
# 只读检查任务，存在活动任务时不允许切换或停止。
$probe = @'
import sqlite3
c=sqlite3.connect('file:/state/parsing/tasks.sqlite3?mode=ro',uri=True)
print(c.execute('SELECT count(*) FROM parse_tasks WHERE status IN (?,?,?,?)',('created','uploading','pending','running')).fetchone()[0])
'@
$active=& docker exec market-regulation-app-1 python -B -c $probe
if ($LASTEXITCODE -ne 0 -or "$active".Trim() -ne '0') { throw '有活动任务或无法核验任务，停止操作。' }
$mounts=$container.Mounts
$runtime=($mounts | Where-Object Destination -eq '/private/runtime.json').Source
$state=($mounts | Where-Object Destination -eq '/state').Source
$models=($mounts | Where-Object Destination -eq '/models').Source
if (-not $runtime -or -not $state -or -not $models) { throw '挂载不完整，停止操作。' }
if ((Split-Path -Leaf $runtime) -ne 'runtime.json' -or (Split-Path -Parent $state) -ne (Split-Path -Parent $runtime)) { throw '挂载根目录不匹配。' }
$env:LOCAL_WORKBENCH_ROOT=Split-Path -Parent $runtime
$env:LOCAL_MODELS_ROOT=$models
$env:LOCAL_APP_IMAGE=$Image
$env:LOCAL_APP_PORT='8180'
$env:LOCAL_DATABASE_NETWORK=($container.NetworkSettings.Networks.PSObject.Properties | Select-Object -First 1).Name
$compose=Join-Path $root 'compose.local.yaml'
if ($Action -eq 'Stop') {
    & docker stop --time 60 market-regulation-app-1
    exit $LASTEXITCODE
}
if (-not $Image) { throw '必须指定已核验的镜像。' }
& docker image inspect $Image *> $null
if ($LASTEXITCODE -ne 0) { throw '指定镜像不存在。' }
$record=Join-Path $root ('local/release-switch-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'.json')
@{previous_image_id=$container.Image;previous_image=$container.Config.Image;target_image=$Image;mounts=$mounts} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $record -Encoding utf8
& docker compose -f $compose up -d --no-deps --no-build --pull never --wait --wait-timeout 90 app
if ($LASTEXITCODE -ne 0) { throw '更新未就绪，保留现场，请用记录中的previous_image执行Rollback。' }
