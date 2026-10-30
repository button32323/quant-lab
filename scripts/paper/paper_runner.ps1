# paper 运行器：每小时更新一次虚拟 carry 账户（只读公开数据）
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
    $i++
    if ($i % 24 -eq 0) {
        $out2 = & $py $script reconcile 2>&1
        L "reconcile exit=$LASTEXITCODE :: $((($out2 -join ' ') -replace '\s+',' ').Trim())"
    }
    Start-Sleep -Seconds 3600
}