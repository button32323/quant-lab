# 运行手册（Operations）

> 项目：`C:\量化项目` ｜ 目标：$100–$1,000 本金方案研究 + paper 验证（不实盘、不碰密钥）。

## 1. 当前系统状态

| 组件 | 位置 | 说明 |
|---|---|---|
| Paper 运行器 | `scripts/paper/paper_runner.ps1` | 每小时整点后 75s 运行，每 24 轮 reconcile + final |
| Paper 数据 | `paper/state.json`、`paper/hourly.csv` | 虚拟 $1,000，PURR+HYPE carry |
| Paper 报告 | `paper/REPORT.md`、`paper/FINAL_REPORT.md` | 每次更新/每日刷新 |
| 告警 | `paper/ALERTS.md` | 回撤 >5% 或连续 12 次负费率时写入 |
| 心跳 | `paper/heartbeat.txt` | 最近一次运行时间 |
| 日志 | `paper/runner.log` | 运行/门禁/对账记录 |

### 2.1 资金费验证工具

| 工具 | 用途 |
|---|---|
| `scripts/paper/predict_settlement.py` | 结算前预登记下一小时预期入账（写 `paper/expected_settlement.json`） |
| `scripts/paper/verify_settlement.py` | 结算后对比预期 vs 实际（PASS/FAIL/PENDING） |
| `scripts/paper/journal.py` | 生成按日汇总的 `paper/JOURNAL.md` |

建议顺序：整点前运行 predict → 整点后 runner 捕获 → 运行 verify。

## 2. Paper 操作

```powershell
# 查看状态
python src/quantlab/paper.py status
# 门禁评估（30 天到期看结论）
python src/quantlab/paper.py gate
# 独立对账
python src/quantlab/paper.py reconcile
# 生成最终报告
python src/quantlab/paper.py final

# 停止：创建 STOP 文件，runner 下一轮退出
New-Item paper/STOP -ItemType File -Force
# 启动（隐藏窗口）
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\量化项目\scripts\paper\paper_runner.ps1"
```

> 电脑重启后 runner 不会自动恢复：按上面命令手动启动一次。

## 3. 研究复现

```powershell
# 单元测试
python -m unittest discover -s tests -v

# 数据（Binance Vision，公开无需密钥）
python scripts/data/fetch_btc_daily.py

# 回测与报告
python scripts/data/refresh_all.py               # 全量数据刷新
python scripts/research/run_carry_suite.py         # 全面 carry 套件
python scripts/research/run_directional_suite.py   # 全面方向性套件
python scripts/research/run_advanced_validation.py   # Walk-forward/多重检验/容量
python scripts/research/build_all_backtests_report.py  # 汇总报告
python scripts/research/carry_capital_tiers.py    # A0 分档
python scripts/research/carry_majors.py           # BTC/ETH carry
python scripts/research/carry_combined.py         # 组合配置
python scripts/research/carry_validation.py       # 滚动/Bootstrap/压力
python scripts/research/capacity_tiers.py         # 容量
python scripts/research/slippage_depth.py         # L2 滑点
python scripts/research/funding_regime.py         # 资金费环境
python scripts/research/paper_probability.py      # paper 通过概率
python scripts/research/order_rounding.py         # 下单取整
python scripts/research/allocation_sensitivity.py # 配比敏感性
python scripts/research/btc_mom90.py              # BTC 90 日动量（修正版，未采用）
python scripts/research/multi_asset_momentum.py   # 多资产动量（淘汰）
```

数据依赖：
- `data/raw/BTCUSDT_1d.csv`、`ETHUSDT_1d.csv`（Binance Vision 下载）
- `data/raw/R174A/`（旧项目归档解压，PURR/HYPE 等 8 资产资金费与 K 线）
- `data/raw/hl/`（Hyperliquid BTC/ETH 资金费与日线）

> 旧项目归档：`C:\量化备份\quant_archive.zip`（文本版）；完整数据在 `quant_remaining.zip`（136.9GB，含钱包私钥，最高敏感）。

## 4. 常见问题

| 问题 | 处理 |
|---|---|
| 网络超时/代理失效 | 脚本会自动清理 HTTP(S)_PROXY；Hyperliquid/Binance Vision 可直连 |
| Binance Vision 404 | 未上市月份/当日未生成，脚本已快速跳过 |
| pandas 3.0 链式赋值不生效 | 用 `.iat` / `.loc`，不要 `df.iloc[i][col] = x` |
| runner 无心跳 | 检查进程是否在跑；重启 runner |
| paper 数据异常 | 先 `reconcile`；差异 ≠0 时停止并检查 funding 拉取 |

## 5. Go-Live 检查清单（仅在 paper PASS 后，且逐笔授权）

- [ ] 交易所账户：仅开启**交易**权限，**关闭提现**权限；
- [ ] 本金 ≤ $1,000，1x、不加杠杆、不借钱；确认现货+永续统一账户/跨保证金；
- [ ] PURR/HYPE 现货+永续可交易、最小下单 ≥$10、szDecimals 已知；
- [ ] 下单脚本先 dry-run 打印订单，人工核对后再发；
- [ ] 记录每笔订单/资金费/对账，日终检查；
- [ ] 风控：回撤 5% 停止、连续 12 次负费率平仓、API 异常立即停止；
- [ ] 税务/合规/地区限制自行确认；
- [ ] 不把密钥写入代码/仓库/聊天。

## 6. 红线

- 本仓库不保存任何私钥/助记词/API 密钥；
- 不做未经 paper 验证的策略实盘；
- 不承诺收益：历史回测 ≠ 未来表现。





