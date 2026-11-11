param([string]$ConfigFile = 'local/parsing-runtime.json', [int]$Port = 8180,
      [string]$Python = '', [string]$ApiPackages = '')
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $workspaceRoot
$configuration = Get-Content -LiteralPath $ConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($property in $configuration.PSObject.Properties) {
    if ($property.Name -in @('MVP_TEST_PG_DSN','PARSING_TEST_PG_DSN','QA_ISOLATED_PG_DSN','OFFLINE_APPROVED_PG_DSN')) {
        throw 'QA_TEST_DSN_NOT_ALLOWED: Use the dedicated QA entry for test database configuration.'
    }
    [Environment]::SetEnvironmentVariable($property.Name, [string]$property.Value, 'Process')
}
foreach ($testConnection in @('MVP_TEST_PG_DSN','PARSING_TEST_PG_DSN','QA_ISOLATED_PG_DSN','OFFLINE_APPROVED_PG_DSN')) {
    [Environment]::SetEnvironmentVariable($testConnection, $null, 'Process')
}
$pythonPath = if ($Python) { $Python } else { Join-Path $workspaceRoot '.venv-api/Scripts/python.exe' }
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Specify an existing validated Python environment; this launcher never installs dependencies.' }
if ($ApiPackages) {
    if (-not (Test-Path -LiteralPath (Join-Path $ApiPackages 'fastapi'))) { throw 'The API packages directory must contain fastapi.' }
    $env:PYTHONPATH = (@($ApiPackages, $env:PYTHONPATH) | Where-Object { $_ }) -join [IO.Path]::PathSeparator
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { throw 'Requested port is already in use; no service was stopped.' }
$reportDirectory = Join-Path $workspaceRoot 'reports'
New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null
$arguments = @('-B','-m','uvicorn','qa_core.document_parsing.mineru_api:create_app','--factory',
    '--host','127.0.0.1','--port',"$Port",'--workers','1','--log-level','warning','--no-access-log')
$process = Start-Process -FilePath $pythonPath -ArgumentList $arguments -WorkingDirectory $workspaceRoot -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $reportDirectory 'parsing-app.out.log') `
    -RedirectStandardError (Join-Path $reportDirectory 'parsing-app.err.log') -PassThru
Write-Output "Parsing application started on http://127.0.0.1:$Port (PID $($process.Id))."
