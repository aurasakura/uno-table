param([int]$Camera = 2, [int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$pythonExe = 'C:\Users\Woo\.t3\projects\culture-makeathon-common-ground\detector\.venv\Scripts\python.exe'
Set-Location -LiteralPath $PSScriptRoot
& $pythonExe -B -u (Join-Path $PSScriptRoot 'server.py') --camera $Camera --port $Port
