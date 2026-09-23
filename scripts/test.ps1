$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDir
& '.\.venv\Scripts\python.exe' -m pytest -q
exit $LASTEXITCODE

