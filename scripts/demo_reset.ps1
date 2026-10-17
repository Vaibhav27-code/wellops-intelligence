$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ([string]::IsNullOrWhiteSpace($env:ASSET_INTELLIGENCE_DATASET)) {
    $env:ASSET_INTELLIGENCE_DATASET = Join-Path $repoRoot 'data\raw\flytbase-ahc-swe-asset-intelligence-dataset'
}
$env:ASSET_INTELLIGENCE_DB = Join-Path $repoRoot 'data\demo.db'
$env:LLM_CACHE_PATH = Join-Path $repoRoot 'data\demo_llm_cache.db'
$pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) { $pythonExe = (Get-Command python -ErrorAction Stop).Source }
& $pythonExe (Join-Path $PSScriptRoot 'demo_reset.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
