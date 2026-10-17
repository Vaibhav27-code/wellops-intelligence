param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$DatasetPath,

    [Parameter(Mandatory = $true, Position = 1)]
    [string]$QuestionsJson,

    [Parameter(Position = 2)]
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw 'Python was not found. Install Python or create the repository .venv first.'
    }
    $python = $pythonCommand.Source
}

$arguments = @(
    (Join-Path $PSScriptRoot 'test_day.py'),
    $DatasetPath,
    $QuestionsJson
)
if ($OutputDirectory) {
    $arguments += @('--output-dir', $OutputDirectory)
}

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
