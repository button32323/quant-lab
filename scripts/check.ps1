# 项目自检：测试 + 数据完整性 + 报告存在性
$ErrorActionPreference = 'Continue'
$proj = 'C:\量化项目'
$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
$env:PYTHONPATH = Join-Path $proj 'src'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location $proj
$fail = 0

function Check($name, $cond) {
    if ($cond) { Write-Output "OK   $name" } else { Write-Output "FAIL $name"; $script:fail++ }
}

Write-Output "=== 单元测试"
& $py -m unittest discover -s tests 2>&1 | Select-Object -Last 3
Check "unit tests exit=0" ($LASTEXITCODE -eq 0)

Write-Output "`n=== 数据文件"
foreach ($f in @('data/raw/BTCUSDT_1d.csv', 'data/raw/ETHUSDT_1d.csv', 'data/raw/SOLUSDT_1d.csv',
                  'data/raw/R174A/data/panels/daily_PURR.csv', 'data/raw/hl/funding_BTC.json')) {
    Check $f (Test-Path (Join-Path $proj $f))
}

Write-Output "`n=== 报告"
foreach ($f in @('reports/PLAN_100_1000.md', 'reports/CARRY_VALIDATION.md', 'reports/CAPACITY_TIERS.md',
                  'reports/SLIPPAGE_DEPTH.md', 'reports/ORDER_ROUNDING.md')) {
    Check $f (Test-Path (Join-Path $proj $f))
}

Write-Output "`n=== Paper"
Check "paper state exists" (Test-Path (Join-Path $proj 'paper/state.json'))
$hb = Join-Path $proj 'paper/heartbeat.txt'
if (Test-Path $hb) {
    $last = (Get-Item $hb).LastWriteTime
    Check ("heartbeat recent (<6h): " + $last) (((Get-Date) - $last).TotalHours -lt 6)
} else { Check "heartbeat exists" $false }

Write-Output "`n=== 密钥泄露扫描（tracked files）"
Push-Location $proj
$secretHits = git grep -nE "BEGIN [A-Z ]*PRIVATE KEY|0x[0-9a-fA-F]{64}|[a-z]+ ([a-z]+ ){11,23}[a-z]+" -- . 2>$null
Pop-Location
if ($secretHits) {
    Write-Output "疑似密钥/助记词命中："
    $secretHits | Select-Object -First 5
    Check "no secrets in tracked files" $false
} else {
    Check "no secrets in tracked files" $true
}

Write-Output "`n=== 结果"
if ($fail -eq 0) { Write-Output "ALL CHECKS PASSED" } else { Write-Output "$fail CHECK(S) FAILED"; exit 1 }