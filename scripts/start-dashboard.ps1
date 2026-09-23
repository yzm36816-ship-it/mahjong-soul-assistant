$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectDir '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $python)) { throw '请先按 README 安装项目 Python 环境。' }
$health = 'http://127.0.0.1:8765/api/health'
$running = $false
try { $running = (Invoke-RestMethod -Uri $health -TimeoutSec 2).local_only -eq $true } catch { }
if (-not $running) {
    Start-Process -FilePath $python -ArgumentList '-m mahjong_assistant.web' -WorkingDirectory $projectDir -WindowStyle Hidden | Out-Null
    for ($attempt = 0; $attempt -lt 15; $attempt++) {
        Start-Sleep -Milliseconds 300
        try { if ((Invoke-RestMethod -Uri $health -TimeoutSec 2).local_only) { $running = $true; break } } catch { }
    }
}
if (-not $running) { throw '本地看板未启动。请运行 .venv\Scripts\python.exe -m mahjong_assistant.web 查看错误。' }
Start-Process -FilePath 'http://127.0.0.1:8765/'
