$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
$appName = Split-Path -Leaf $projectDir
$outputName = $appName + '-v0.3'
Set-Location -LiteralPath $projectDir
$flags = @('--noconfirm', '--windowed', '--onedir', '--name', $outputName, '--paths', 'src', '--exclude-module', 'PyQt5', '--exclude-module', 'PyQt6', '--exclude-module', 'PySide2', '--exclude-module', 'tkinter', '--exclude-module', 'matplotlib', '--exclude-module', 'scipy', '--exclude-module', 'pandas', '--exclude-module', 'IPython', '--distpath', 'dist', '--workpath', 'build', '--specpath', 'build')
$promoted = $false
foreach ($mode in @('3p', '4p')) {
    $report = Join-Path $projectDir "data\models\$mode\report.json"
    if (Test-Path -LiteralPath $report) {
        if ((Get-Content -LiteralPath $report -Raw -Encoding UTF8 | ConvertFrom-Json).promoted) { $promoted = $true }
    }
}
if (-not $promoted) { $flags += @('--exclude-module', 'torch') }
& '.\.venv\Scripts\python.exe' -m PyInstaller @flags scripts/entrypoint.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
$distribution = Join-Path (Join-Path $projectDir 'dist') $outputName
$templateOutput = Join-Path $distribution 'data'
New-Item -ItemType Directory -Path $templateOutput -Force | Out-Null
if (Test-Path -LiteralPath 'data\templates') {
    Copy-Item -LiteralPath 'data\templates' -Destination $templateOutput -Recurse -Force
}
if (Test-Path -LiteralPath 'data\samples\sample-2.png') {
    $sampleOutput = Join-Path $templateOutput 'samples'
    New-Item -ItemType Directory -Path $sampleOutput -Force | Out-Null
    Copy-Item -LiteralPath 'data\samples\sample-2.png' -Destination $sampleOutput -Force
}
Copy-Item -LiteralPath 'README.md' -Destination $distribution -Force
if ($promoted) {
    $modelOutput = Join-Path $templateOutput 'models'
    Copy-Item -LiteralPath 'data\models' -Destination $templateOutput -Recurse -Force
}
Write-Host 'Build complete. Keep the exe and _internal directory together.'
