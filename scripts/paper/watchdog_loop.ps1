# 看门狗循环：每 10 分钟检查一次 runner/面板
param([int]$IntervalMinutes = 10)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$inner = Join-Path $here 'watchdog.ps1'
while ($true) {
    try { & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $inner } catch {}
    Start-Sleep -Seconds ($IntervalMinutes * 60)
}
