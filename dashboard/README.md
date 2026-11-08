# Quant Monitor（Apple 风格监控窗口）

本地面板，只读 `paper/` 数据，不涉及交易和密钥。

## 打开

双击 / 运行：

```powershell
powershell -ExecutionPolicy Bypass -File C:\量化项目\dashboard\start.ps1
```

会做两件事：

1. 若 8765 端口没服务，启动 `server.py`；
2. 用 Chrome 的 **app 模式**打开 `http://127.0.0.1:8765`（无地址栏，像一个独立窗口）。

也可以直接浏览器访问 http://127.0.0.1:8765 。

## 面板内容

- **总资产 / 累计收益 / 累计资金费**（4 个账户合计）；
- **主账户 $1,000**：NAV、收益、资金费、年化、MTM、回撤、建仓成本覆盖、正费率占比、NAV 走势；
- **3 个 $100 账户**：NAV、收益、资金费、年化、覆盖、第 x/30 天、迷你走势；
- **系统状态**：两个 runner 心跳（>90 分钟显示 OFFLINE）、对账 4/4 PASS、告警、30 天 gate 进度；
- 每 10 秒自动刷新；右上角可切换深/浅色；`?theme=light` 可直接打开浅色。

## 数据来源

| 数据 | 文件 |
|---|---|
| 主账户状态 | `paper/state.json` |
| 主账户小时 NAV | `paper/hourly.csv` |
| $100 账户 | `paper/accounts/<id>/state.json`、`hourly.csv` |
| 对账 | `paper/reconcile.json`、`paper/accounts/<id>/reconcile.json` |
| 告警 | `paper/ALERTS.md`、`paper/accounts/<id>/ALERTS.md` |
| runner 心跳 | `paper/heartbeat.txt`、`paper/accounts/heartbeat.txt` |

## 可靠性

- `scripts/paper/watchdog.ps1`：心跳超过 90 分钟自动重启对应 runner；面板服务掉线也会拉起；
- `scripts/paper/watchdog_loop.ps1`：每 10 分钟执行一次看门狗；
- 已放入用户启动目录：`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\QuantWatchdog.lnk`（登录后自动运行）。

> 背景：2026-11-07 16:01 runner 意外停止（无 STOP 标记），11-08 09:46 重启并补记了约 16 小时资金费；watchdog 就是为这种情况加的。
