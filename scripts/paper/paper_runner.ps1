# paper 运行器：整点对齐运行（只读公开数据）
$ErrorActionPreference = 'Continue'
$proj = 'C:\量化项目'
$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
$script = Join-Path $proj 'src\quantlab\paper.py'
$paperDir = Join-Path $proj 'paper'
$log = Join-Path $paperDir 'runner.log'
$hb = Join-Path $paperDir 'heartbeat.txt'
$stopFlag = Join-Path $paperDir 'STOP'
$env:PYTHONPATH = Join-Path $proj 'src'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location $proj

function L($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg"
    Add-Content -LiteralPath $log -Value $line -Encoding utf8
}

L "paper runner started (pid=$PID)"
$i = 0
while ($true) {
    if (Test-Path $stopFlag) { L "STOP flag found, exiting"; break }
    $out = & $py $script run 2>&1
    $code = $LASTEXITCODE
    Set-Content -LiteralPath $hb -Value (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') -Encoding utf8
    $trim = (($out -join ' ') -replace '\s+', ' ').Trim()
    if ($trim.Length -gt 300) { $trim = $trim.Substring(0, 300) }
    L "run exit=$code :: $trim"
    $g = & $py $script gate 2>&1
    $gline = (($g -join ' ') -replace '\s+', ' ').Trim()
    if ($gline.Length -gt 300) { $gline = $gline.Substring(0, 300) }
    L "gate :: $gline"
    $i++
    if ($i % 6 -eq 0) {
        $out2 = & $py $script reconcile 2>&1
        L "reconcile exit=$LASTEXITCODE :: $((($out2 -join ' ') -replace '\s+',' ').Trim())"
    }
    if ($i % 24 -eq 0) {
        $out3 = & $py $script final 2>&1
        L "final exit=$LASTEXITCODE :: $((($out3 -join ' ') -replace '\s+',' ').Trim())"
        $out4 = & $py (Join-Path $proj 'scripts\paper\journal.py') 2>&1
        L "journal exit=$LASTEXITCODE"
    }
    # 对齐到下一个整点后 75 秒
    $now = Get-Date
    $next = $now.Date.AddHours($now.Hour + 1).AddSeconds(75)
    $sleep = [int]($next - $now).TotalSeconds
    if ($sleep -lt 60) { $sleep = 60 }
    Start-Sleep -Seconds $sleep
}