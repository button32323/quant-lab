# 启动量化监控面板（Apple 风格）

$ErrorActionPreference = 'Continue'
$proj = 'C:\量化项目'
$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe'
$server = Join-Path $proj 'dashboard\server.py'
$url = 'http://127.0.0.1:8765'

function Test-Port {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $c.Connect('127.0.0.1', 8765)
        $c.Close()
        return $true
    } catch { return $false }
}

if (-not (Test-Port)) {
    $cmd = "`"$py`" `"$server`""
    Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd } | Out-Null
    Start-Sleep -Seconds 2
    Write-Output "监控服务已启动: $url"
} else {
    Write-Output "监控服务已在运行: $url"
}

# 用 Chrome 的 app 模式打开（无地址栏，像独立窗口）
$chrome = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
if (Test-Path $chrome) {
    Start-Process $chrome "--app=$url --window-size=1440,960"
} else {
    Start-Process $url
}
