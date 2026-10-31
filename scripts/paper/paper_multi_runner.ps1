# 多账户 paper 运行器：$100 档候选策略并行验证（只读公开数据）
$ErrorActionPreference = 'Continue'
$proj = 'C:\量化项目'
$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
$script = Join-Path $proj 'src\quantlab\paper_multi.py'
$paperDir = Join-Path $proj 'paper'
$log = Join-Path $paperDir 'accounts\runner.log'
$hb = Join-Path $paperDir 'accounts\heartbeat.txt'
$stopFlag = Join-Path $paperDir 'accounts\STOP'
$env:PYTHONPATH = Join-Path $proj 'src'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location $proj

function L($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg"
    Add-Content -LiteralPath $log -Value $line -Encoding utf8
}

New-Item -ItemType Directory -Force -Path (Join-Path $paperDir 'accounts') | Out-Null
L "accounts runner started (pid=$PID)"
$i = 0
while ($true) {
    if (Test-Path $stopFlag) { L "STOP flag found, exiting"; break }
    $out = & $py $script run 2>&1
    $code = $LASTEXITCODE
    Set-Content -LiteralPath $hb -Value (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') -Encoding utf8
    $trim = (($out -join ' ') -replace '\s+', ' ').Trim()
    if ($trim.Length -gt 400) { $trim = $trim.Substring(0, 400) }
    L "run exit=$code :: $trim"
    $i++
    if ($i % 6 -eq 0) {
        $out2 = & $py $script reconcile 2>&1
        $t2 = (($out2 -join ' ') -replace '\s+', ' ').Trim(); if ($t2.Length -gt 400) { $t2 = $t2.Substring(0,400) }
        L "reconcile exit=$LASTEXITCODE :: $t2"
    }
    if ($i % 24 -eq 0) {
        $out3 = & $py $script gate 2>&1
        $t3 = (($out3 -join ' ') -replace '\s+', ' ').Trim(); if ($t3.Length -gt 600) { $t3 = $t3.Substring(0,600) }
        L "gate exit=$LASTEXITCODE :: $t3"
    }
    $now = Get-Date
    $next = $now.Date.AddHours($now.Hour + 1).AddSeconds(75)
    $sleep = [int]($next - $now).TotalSeconds
    if ($sleep -lt 60) { $sleep = 60 }
    Start-Sleep -Seconds $sleep
}