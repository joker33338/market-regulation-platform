param([string]$Python = '', [string]$ApiPackages = '', [switch]$DualEngine)
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
# Independent QA checkouts need to reuse an existing API environment instead
# of silently skipping every API case when no source-local venv exists.
$apiCandidates = @($ApiPackages, (Join-Path $workspaceRoot '.venv-api/Lib/site-packages'))
if ($env:PYTHONPATH) { $apiCandidates += $env:PYTHONPATH -split [IO.Path]::PathSeparator }
$apiPath = $apiCandidates | Where-Object { $_ -and (Test-Path -LiteralPath (Join-Path $_ 'fastapi') -PathType Container) } | Select-Object -First 1
if (-not $apiPath) { throw 'Existing API dependencies required; pass -ApiPackages. No environment was installed or changed.' }
$env:PYTHONPATH = $apiPath
# Full regression is synthetic by default. Live DB testing is a separate opt-in.
$env:MVP_TEST_PG_DSN = ''
$env:PARSING_TEST_PG_DSN = ''
$env:PARSING_RESULT_PG_DSN = ''
$env:QA_ISOLATED_PG_DSN = ''
if ($DualEngine) { $env:MARKET_REGULATION_DUAL_ENGINE_TEST_ADAPTER = 'tests.dual_engine_adapter:run_scenario' }
& $Python -B tests/run_round01_validation.py --source . --include-source-tests --result-json reports/fix-regression.json *> reports/fix-regression.log
$testExit = $LASTEXITCODE
Get-Content reports/fix-regression.log -Tail 9
exit $testExit
