$ErrorActionPreference = 'Stop'
$pidFile = Join-Path $PSScriptRoot 'server.pid'
if (-not (Test-Path -LiteralPath $pidFile)) { Write-Host 'No background bridge PID saved.'; return }
$bridgePid = [int](Get-Content -LiteralPath $pidFile)
$bridgeProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $bridgePid"
$serverFile = Join-Path $PSScriptRoot 'server.py'
if ($bridgeProcess -and $bridgeProcess.CommandLine.Contains($serverFile)) {
    Stop-Process -Id $bridgePid
    Write-Host 'Camera bridge stopped.'
} else { Write-Host 'Saved bridge is no longer running.' }
