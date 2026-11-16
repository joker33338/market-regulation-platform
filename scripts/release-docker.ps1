param([Parameter(Mandatory=$true)][ValidateSet('Update','Rollback','Status','Stop')][string]$Action,
      [string]$Image,[string]$RuntimeJson)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
if ($Action -eq 'Status') { & docker inspect market-regulation-app-1 --format '{{.Id}} {{.Image}} {{.State.Status}} {{json .State.Health}}'; exit $LASTEXITCODE }
if ($Action -eq 'Stop') { throw '请先使用部署工具核对活动任务后显式停止，禁止通过旧入口直接停服务。' }
if (-not $Image) { throw '必须指定已核验镜像。' }
$info=(& docker image inspect $Image | ConvertFrom-Json)[0]
if ($LASTEXITCODE -ne 0) { throw '镜像不存在。' }
$revision=$info.Config.Labels.'org.opencontainers.image.revision'
$python=Join-Path $root '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python='python' }
$arguments=@((Join-Path $root 'scripts/deploy_release.py'),'--image',$Image,'--revision',$revision,'--apply')
if ($RuntimeJson) { $arguments+=@('--runtime',$RuntimeJson) }
if ($Action -eq 'Rollback') { $arguments+='--rollback' }
& $python @arguments
exit $LASTEXITCODE
