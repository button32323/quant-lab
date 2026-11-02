# Changelog

所有版本的变更记录。版本号遵循语义化版本（SemVer）：`v主版本.次版本.修订号`。
完整代码与报告索引见 [reports/INDEX.md](reports/INDEX.md)。

## v0.2.0 — 2026-11-03

### 新增
- **$100 多账户 paper 验证**：`a0_100`（PURR+HYPE carry）、`e_100`（75/25 分散）、`b0_100`（BTC+ETH carry），独立 state/hourly/report/reconcile，最小下单与 szDecimals 取整已校验；
- 多账户引擎 `src/quantlab/paper_multi.py` + runner `scripts/paper/paper_multi_runner.ps1`（每小时更新、每 6h 对账、每 24h gate）；
- 加杠杆测算 `scripts/research/carry_leverage.py` → `reports/CARRY_LEVERAGE.md`（收益/回撤/压力测试）；
- GitHub 开源项目借鉴清单 `reports/GITHUB_LEARNINGS.md`；
- 数据刷新脚本 `scripts/data/refresh_daily.py`（Binance Vision + HL，429 退避）；
- 多账户/取整测试（总测试数 41）。

### 变更
- 报告索引 `reports/INDEX.md`、状态快照 `reports/STATUS.md` 持续更新；
- `docs/OPERATIONS.md` 补充 paper 验证工具与多账户说明。

## v0.1.0 — 2026-10-31

### 新增
- 研究框架：数据（Binance Vision / Hyperliquid 公开 API）、回测（无未来函数、次日开盘执行）、统一成本模型、指标；
- 候选方案回测与对比：A0（PURR+HYPE）年化 +18.08%、回撤 0.74%、Sharpe 4.95；BTC/ETH carry、组合配置、动量类淘汰方案；
- 稳健性验证：滚动/Bootstrap/压力测试、容量、L2 滑点实测、下单取整、资金费环境与风控阈值、paper 通过概率；
- $1,000 paper 账户（PURR+HYPE carry）+ 每小时 runner + gate/final/alerts/reconcile；
- 文档：设计原则、套利研究、paper 计划、运行手册、FAQ、完成证据；
- 测试：37 个单元测试；自检脚本 `scripts/check.ps1`（数据/报告/链接/密钥扫描/心跳）。
