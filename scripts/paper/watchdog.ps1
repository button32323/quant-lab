# 量化 paper 看门狗：runner 心跳超过 90 分钟则重启；顺带确保监控面板服务在线
$ErrorActionPreference = 'Continue'
$proj = 'C:\量化项目'
$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
$paper = Join-Path $proj 'paper'
$log = Join-Path $paper 'watchdog.log'
$mainHb = Join-Path $paper 'heartbeat.txt'
$acctHb = Join-Path $paper 'accounts\heartbeat.txt'

function L($msg) {
    Add-Content -LiteralPath $log -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg" -Encoding utf8
}

function Age-Min($path) {
    if (-not (Test-Path $path)) { return 9999 }
    return ((Get-Date) - (Get-Item $path).LastWriteTime).TotalMinutes
}

function Runner-Running($pattern) {
    $p = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match $pattern -and $_.CommandLine -notmatch 'Get-CimInstance' }
    return [bool]$p
}

function Start-Runner($script) {
    $cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd }
    L "started $(Split-Path $script -Leaf) pid=$($r.ProcessId)"
}

# 主账户 runner
$ageMain = Age-Min $mainHb
if ($ageMain -gt 90 -and -not (Runner-Running 'paper_runner\.ps1')) {
    Start-Runner (Join-Path $proj 'scripts\paper\paper_runner.ps1')
} elseif ($ageMain -gt 90) {
    L "main runner process exists but heartbeat stale ($([math]::Round($ageMain,0)) min) — skip restart"
}

# 多账户 runner
$ageAcct = Age-Min $acctHb
if ($ageAcct -gt 90 -and -not (Runner-Running 'paper_multi_runner\.ps1')) {
    Start-Runner (Join-Path $proj 'scripts\paper\paper_multi_runner.ps1')
} elseif ($ageAcct -gt 90) {
    L "accounts runner process exists but heartbeat stale ($([math]::Round($ageAcct,0)) min) — skip restart"
}

# 监控面板服务
$portOpen = $false
try {
    $c = New-Object Net.Sockets.TcpClient
    $c.Connect('127.0.0.1', 8765)
    $c.Close()
    $portOpen = $true
} catch {}
if (-not $portOpen) {
    $cmd = "`"$py`" `"$proj\dashboard\server.py`""
    Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd } | Out-Null
    L "dashboard server started"
}

L "ok (main=$([math]::Round($ageMain,1))min acct=$([math]::Round($ageAcct,1))min)"
