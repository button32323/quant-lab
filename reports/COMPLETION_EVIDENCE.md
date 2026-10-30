# 目标完成证据（Objective Completion Evidence）

> 目标：在 $100–$1,000 本金区间内，筛选并回测验证最适合的量化/套利方案，输出可复现报告与分档推荐（不实盘、不碰密钥、不承诺收益）。

## 1. 交付物清单

| 要求 | 交付物 | 证据 |
|---|---|---|
| 筛选候选方案 | `reports/PLAN_100_1000.md` §1 | 6 类方案对比（carry/动量/配对等） |
| 回测验证 | `reports/CARRY_CAPITAL_TIERS.md` 等 | 2024-12→2026-10，含成本/无未来函数 |
| 分档推荐 | `reports/PLAN_100_1000.md` §3 | $100/$300/$500/$1,000/$12k+ 分档 |
| 可复现 | `scripts/` + `tests/` + `docs/OPERATIONS.md` | 37 个单测全过；`scripts/check.ps1` 全 PASS |
| 不实盘 | `paper/` 虚拟账户 | 无账户/密钥/真实订单 |
| 不碰密钥 | `.gitignore` + 文档红线 | 仓库无密钥文件 |
| 不承诺收益 | 报告"风险与局限"章节 | 明确历史≠未来 |

## 2. 核心结论

- **推荐：A0 = Hyperliquid PURR+HYPE 现货-永续资金费 carry（1x delta 中性）**；
- 历史回测：年化 **+18.08%**、最大回撤 **0.74%**、Sharpe **4.95**（2024-12→2026-10-23，含成本）；用 HL 原始数据延长到 2026-10-30：**+18.21%、0.73%、4.84**；两数据源交叉验证一致；
- 当前环境：约 **+9.66%/年**，$100–$1,000 对应年收入约 **$10–$97**；
- 最小可行本金 **≈$26.67**；当前容量约 **$56k**（随成交额波动）；
- 10% 净收益需毛资金费 ≥ **10.34%**，当前差约 0.7pp；
- 淘汰：BTC 90 日动量（MDD 66.7%）、多资产动量（样本外 Sharpe ≤0.69）、多资产小市值分散（4 资产 −4.97%）。

## 3. 验证命令与结果

```text
python -m unittest discover -s tests
→ Ran 37 tests ... OK

scripts/check.ps1
→ OK unit tests / data files / reports / paper state / heartbeat
→ ALL CHECKS PASSED
```

回测复现（报告内数字由以下脚本生成）：
- `scripts/research/carry_capital_tiers.py` → 18.08% / 0.74% / 4.95
- `scripts/research/carry_majors.py` → 11.56% / 0.68% / 10.76
- `scripts/research/carry_combined.py` → 组合配置表
- `scripts/research/carry_validation.py` → 滚动/Bootstrap/压力
- `scripts/research/capacity_tiers.py` / `slippage_depth.py` / `funding_regime.py` / `paper_probability.py` / `order_rounding.py` / `allocation_sensitivity.py` / `carry_multiasset.py`
- `scripts/research/btc_mom90.py` / `multi_asset_momentum.py`（淘汰方案）

## 4. 当前系统状态

- Paper 账户：虚拟 $1,000，2026-10-30T16:40:40Z 启动，runner 每小时更新（`.dsh` 之外独立进程）；
- 报告：[`reports/INDEX.md`](INDEX.md)、[`reports/PLAN_100_1000.md`](PLAN_100_1000.md)；
- 代码仓库：`C:\量化项目`，git 多轮提交，工作区 clean。

## 5. 剩余（不阻塞本目标）

- paper 30 天监控（到期看 `paper/FINAL_REPORT.md` 与 gate）；
- 若环境改善/资金扩大，再按 `docs/OPERATIONS.md` 的 go-live 清单评估实盘（需逐笔授权）。

