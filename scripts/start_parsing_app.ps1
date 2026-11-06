param([string]$ConfigFile = 'local/parsing-runtime.json', [int]$Port = 8180)
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $workspaceRoot
$configuration = Get-Content -LiteralPath $ConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($property in $configuration.PSObject.Properties) {
    [Environment]::SetEnvironmentVariable($property.Name, [string]$property.Value, 'Process')
}
$pythonPath = Join-Path $workspaceRoot '.venv-api/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create the isolated API environment first; see integration documentation.' }
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { throw 'Requested port is already in use; no service was stopped.' }
$reportDirectory = Join-Path $workspaceRoot 'reports'
New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null
$arguments = @('-B','-m','uvicorn','qa_core.document_parsing.mineru_api:create_app','--factory',
    '--host','127.0.0.1','--port',"$Port",'--workers','1','--log-level','warning','--no-access-log')
$process = Start-Process -FilePath $pythonPath -ArgumentList $arguments -WorkingDirectory $workspaceRoot -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $reportDirectory 'parsing-app.out.log') `
    -RedirectStandardError (Join-Path $reportDirectory 'parsing-app.err.log') -PassThru
Write-Output "Parsing application started on http://127.0.0.1:$Port (PID $($process.Id))."
