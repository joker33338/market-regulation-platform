param([Parameter(Mandatory=$true)][ValidateSet('QA','Fix')][string]$Role)
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $workspaceRoot
$branch = (& git branch --show-current).Trim()
$expected = if ($Role -eq 'QA') { @('qa/round1', 'codex/qa-v0.2.1') } else { @('fix/round1', 'codex/fix-v0.2.1') }
if ($branch -notin $expected) { throw "Expected branch $($expected -join ' or '); found $branch" }
$common = (& git rev-parse --path-format=absolute --git-common-dir).Trim()
$configFile = Join-Path $common 'agent-local.json'
if (-not (Test-Path -LiteralPath $configFile)) { throw 'Missing local agent configuration.' }
$config = Get-Content -LiteralPath $configFile -Raw -Encoding UTF8 | ConvertFrom-Json
$env:MARKET_REGULATION_TEST_CORPUS = $config.corpus
$env:EMBEDDING_MODEL_PATH = Join-Path $config.originalRoot 'models/bge-m3'
$env:OCR_MODEL_ROOT = Join-Path $config.originalRoot 'models/ocr'
$env:MARKET_REGULATION_PYTHON = Join-Path $config.originalRoot '.venv/Scripts/python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:API_BASE = ''
$env:API_KEY = ''
$env:PG_DSN = ''
$env:SOURCE_PG_DSN = ''
$env:MVP_TEST_PG_DSN = ''
Write-Host "Workspace ready: $Role ($branch). Corpus access is read-only by workflow contract."
Write-Host 'Read AGENTS.md and docs/qa/round01/README.md before starting.'
if (Get-Command codex -ErrorAction SilentlyContinue) { & codex } else { Write-Host 'Open a separate Codex session in this workspace; this terminal is configured.' }
