# 策略最终取舍（Keep / Watch / Drop）

> 基于 2026-11-04 全面回测（carry 全资产 + 65 个方向性策略 + Walk-forward + 多重检验 + 容量 + 数据质量筛查）。
> 详细证据：[ALL_BACKTESTS.md](ALL_BACKTESTS.md)、[ALL_BACKTESTS_CARRY.md](ALL_BACKTESTS_CARRY.md)、[ALL_BACKTESTS_DIRECTIONAL.md](ALL_BACKTESTS_DIRECTIONAL.md)、[ALL_BACKTESTS_ADVANCED.md](ALL_BACKTESTS_ADVANCED.md)。

## 1. 结论表

| 决策 | 策略 | 关键证据 | 说明 |
|---|---|---|---|
| ✅ **保留（核心）** | **A0：PURR+HYPE carry** | 2024-12→2026-11：年化 +18.2%、Sharpe 4.85、MDD 0.73%；容量中位 ~$57k | 小资金首选；paper 验证中 |
| ✅ **保留（扩容/低波）** | **B0：BTC+ETH carry** | 2023-05→2026-11：年化 +11.5%、Sharpe 10.75、MDD 0.68%；容量百万级 | 年化低但最平滑；> $12k 资金后可切换/分散 |
| ✅ **保留（折中）** | **ALL4：PURR+HYPE+BTC+ETH carry** | 年化 +13.1%、Sharpe 6.45、MDD 0.37%、容量 ~$113k | 收益/回撤/容量折中 |
| 👀 观察，不建议投钱 | BTC 90 日 TSMOM | 连续 OOS：+76.9%、Sharpe 0.77、MDD 27.7%（vs B&H 0.66）；但全样本 MDD 66.7% | 修正旧 OOS 误报后仍不满足 30% 回撤门槛；regime 依赖强 |
| 👀 观察，不建议投钱 | ETH/BNB 单资产 TSMOM | 2024+ OOS Sharpe 0.8–0.96，但全样本 MDD 68–81% | 样本内好看、回撤不可接受 |
| ❌ 放弃 | 多资产动量轮动（ROT） | 全样本 Sharpe 最高 1.6，但 MDD 56%；walk-forward 后 MDD 71%、样本外 0.72 | 多重检验后无稳定优势；日频成本高 |
| ❌ 放弃 | RSI / 布林带均值回归 | BTC：年化 +2.4%/+2.6%，Sharpe 0.25 左右 | 扣除成本后无优势 |
| ❌ 放弃 | BTC-ETH 配对（含 walk-forward） | 配对 WF：年化 −8.2%、Sharpe −0.61；OOS −13.2% | 扣成本/借币成本后为负 |
| ❌ 放弃 | 小市值长尾 carry（AZTEC/BERA/MON/PUMP/STABLE/TRUMP） | 现货日成交额 $0–3.8k，价格有 13–18x 异常跳变 | 回测收益不可交易（虚假/不可执行） |
| ❌ 放弃 | 杠杆 > 1.5x | 2x 历史年化 +30% 但资金费转负时 −34%/回撤 53%；3x 压力 −64%/85% | 尾部风险不可接受 |
| ❌ 放弃 | 网格/DCA/AI 交易机器人 | 无公开可复现 edge；单边行情爆仓 | 不投入 |

## 2. 最终建议（$100–$1,000）

1. **A0 为核心**：PURR+HYPE carry，1x、delta 中性；
2. 想更平滑：可把 20–30% 资金分给 BTC/ETH carry（B0/ALL4），代价是年化下降；
3. **先 paper 30 天**（当前 4 个账户在跑），再看实盘；
4. **不碰**：方向性动量、均值回归、配对、长尾小市值、杠杆 >1.5x；
5. 资金 >$12k 后再考虑 B0 扩容；容量按 p5 保守估计（PURR 单资产 p5 约 $20k 资本）。

## 3. 需要跟踪的风险

- 资金费转负（当前环境 10–15%，历史均值 18%，已走弱）；
- basis 波动（paper 中已出现 MTM 回吐）；
- 交易所/账户风险（单交易所 Hyperliquid）；
- 数据/执行差异（paper 无真实滑点/延迟；实盘需小额验证）；
- 多重检验/选择偏差：候选池是 2026-10 筛选的，历史排序不能外推。

## 4. 复现命令

```powershell
python scripts/data/refresh_all.py
python scripts/research/run_carry_suite.py
python scripts/research/run_directional_suite.py
python scripts/research/run_advanced_validation.py
python scripts/research/build_all_backtests_report.py
python -m unittest discover -s tests
```
