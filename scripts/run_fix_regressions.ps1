param([string]$Python = '')
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $workspaceRoot
if (-not $Python) {
    $commonDir = (& git rev-parse --path-format=absolute --git-common-dir).Trim()
    $agentConfig = Get-Content -LiteralPath (Join-Path $commonDir 'agent-local.json') -Raw | ConvertFrom-Json
    $Python = Join-Path $agentConfig.originalRoot '.venv/Scripts/python.exe'
}
$env:TEMP = Join-Path $workspaceRoot 'reports/fix-test-temp'
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
$env:TMP = $env:TEMP
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = Join-Path $workspaceRoot '.venv-api/Lib/site-packages'
# Full regression is synthetic by default. Live DB testing is a separate opt-in.
$env:MVP_TEST_PG_DSN = ''
$env:PARSING_TEST_PG_DSN = ''
& $Python -B -m unittest discover -s tests -v *> reports/fix-regression.log
$testExit = $LASTEXITCODE
Get-Content reports/fix-regression.log -Tail 9
exit $testExit
