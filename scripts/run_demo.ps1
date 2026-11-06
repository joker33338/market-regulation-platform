$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Run the installation commands in README.md to create .venv first.'
}
Push-Location -LiteralPath $projectRoot
try {
    & $pythonPath -X utf8 scripts/smoke_local_model.py
    if ($LASTEXITCODE -ne 0) { throw 'Local model demo failed.' }
} finally {
    Pop-Location
}

