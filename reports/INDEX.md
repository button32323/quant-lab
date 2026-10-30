# 报告索引与核心结论

> 项目：$100–$1,000 本金量化/套利方案筛选与回测验证。所有报告可复现，数据/脚本/测试均在仓库内。

## 核心结论（先看这个）

1. **最适合 $100–$1,000 本金的方案：Hyperliquid 现货-永续资金费 carry（A0：PURR+HYPE，1x delta 中性）**；
2. 历史回测（2024-12→2026-10）：**年化 +18.08%、最大回撤 0.74%、Sharpe 4.95、正资金费占比 97.2%**；
3. **当前资金费环境约 +9.66%/年**（近 30 天），对应 $100 本金约 **$10/年**、$1,000 约 **$97/年**——收益绝对值很小，适合练手/验证，不是收入来源；
4. 10% 净收益门槛需要毛资金费 ≥ **10.34%**，当前环境差约 0.7pp；
5. **paper 30 天大概率不过 10% 年化门禁**（一次建仓成本 −0.34% 被 30 天窗口年化放大），paper 主要用于验证执行/对账；
6. 淘汰方案：BTC 90 日动量（MDD 66.7%、样本外 Sharpe 0.31）、多资产动量（样本外 Sharpe ≤0.69、MDD 48–67%）、多资产小市值分散（4 资产近 254 天 −4.97%）。

## 快速问答

常见问题（收益为什么只有 9.7%、资金费转负怎么办、最低多少钱、安全吗……）见 [FAQ.md](FAQ.md)。

## 报告清单

| 报告 | 内容 | 关键结论 |
|---|---|---|
| [PLAN_100_1000.md](PLAN_100_1000.md) | **总报告**：候选对比、分档推荐、容量/滑点/取整/环境 | A0 最优；$27 起可跑；当前 ~9.7%/年 |
| [CARRY_CAPITAL_TIERS.md](CARRY_CAPITAL_TIERS.md) | A0 分本金档位回测 | 收益率与本金无关；$27+ 可行 |
| [CARRY_MAJORS.md](CARRY_MAJORS.md) | BTC/ETH carry | +11.56%/年、回撤 0.68%，适合大资金 |
| [CARRY_COMBINED.md](CARRY_COMBINED.md) | 小市值+主流组合配置 | 75/25 组合 +15.54%、回撤 0.55% |
| [CARRY_VALIDATION.md](CARRY_VALIDATION.md) | 滚动/Bootstrap/压力测试 | 资金费转负时可能 −12.5%/回撤 22% |
| [CAPACITY_TIERS.md](CAPACITY_TIERS.md) | 容量与可部署上限 | 当前 PURR 容量约 $21k 名义，A0 上限约 $56k |
| [SLIPPAGE_DEPTH.md](SLIPPAGE_DEPTH.md) | L2 滑点实测 | $100–$1,000 滑点 9–17bps，与回测假设一致 |
| [ORDER_ROUNDING.md](ORDER_ROUNDING.md) | 下单取整/最小下单 | szDecimals 导致小资金轻微欠配 |
| [FUNDING_REGIME.md](FUNDING_REGIME.md) | 资金费环境 | 小市值负费率仅 3.6–3.8%/天；主流 12% |
| [PAPER_PROBABILITY.md](PAPER_PROBABILITY.md) | paper 30 天通过概率 | 当前环境约 25%（近 180 天口径） |
| [ALLOCATION_SENSITIVITY.md](ALLOCATION_SENSITIVITY.md) | PURR/HYPE 配比敏感性 | 收益 16.8–19.4%，对配比不敏感 |
| [FUNDING_TIMING.md](FUNDING_TIMING.md) | 资金费环境分位/风控阈值 | 当前处历史偏低区间（后 10–13%） |
| [CARRY_MULTIASSET.md](CARRY_MULTIASSET.md) | 多资产分散检验 | 加入 AZTEC/STABLE 反而恶化，维持 A0 |
| [BTC_MOM90_REPORT.md](BTC_MOM90_REPORT.md) | BTC 90 日动量（淘汰） | 全样本 MDD 66.7%，样本外 Sharpe 0.31 |
| [MULTI_ASSET_MOMENTUM.md](MULTI_ASSET_MOMENTUM.md) | 多资产动量（淘汰） | 样本外不如 BTC 买入持有 |

## 文档

| 文档 | 内容 |
|---|---|
| [../docs/DESIGN.md](../docs/DESIGN.md) | 研究流程与原则 |
| [../docs/ARBITRAGE_RESEARCH.md](../docs/ARBITRAGE_RESEARCH.md) | 套利类型/成功案例/可行性路线 |
| [../docs/PAPER_PLAN.md](../docs/PAPER_PLAN.md) | 30 天 paper 验证计划与门禁 |
| [../docs/OPERATIONS.md](../docs/OPERATIONS.md) | 运行手册（启停/复现/go-live 清单） |

## Paper 状态

- 启动：2026-10-30T16:40:40Z（虚拟 $1,000，PURR+HYPE carry）；
- 实时报告：[../paper/REPORT.md](../paper/REPORT.md)、最终报告 [../paper/FINAL_REPORT.md](../paper/FINAL_REPORT.md)、告警 [../paper/ALERTS.md](../paper/ALERTS.md)；
- 30 天到期后看 gate：`python src/quantlab/paper.py gate`。


