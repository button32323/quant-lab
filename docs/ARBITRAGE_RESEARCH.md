# 套利研究：机制、成功案例与可行路线

> 研究笔记（2026-10-30）。目标：搞清楚"套利到底怎么赚钱、谁在做、我们能不能做"。
> 结论先行：**套利不是无风险，是"低风险 + 执行风险"；主流价差已被高频/机构吃掉，剩下的是资金费/基差、长尾资产、跨所运维、做市与链上机会——都需要资本、速度或精细化运营。**

## 1. 套利的本质

套利 = 同一资产/等价资产在不同市场、不同期限、不同形式之间的价格差，扣掉全部成本后仍有净收益。

赚钱的来源只有四类：

| 来源 | 举例 | 谁有优势 |
|---|---|---|
| 价格差（空间） | 同一币 A 所买、B 所卖 | 低延迟、多账户、预置资金 |
| 时间差（期限/资金费） | 现货 + 永续空，收资金费 | 资本成本低、能加杠杆的机构 |
| 流动性提供 | 做市赚价差+返佣 | 专业做市团队、协议金库 |
| 信息/结构差 | 新币上线、稳定币脱锚、跨链桥价差、清算 | 快速监控+链上执行 |

**套利的"免费午餐"为什么还在**：因为每一种套利都对应一种风险（对手方、执行、库存、合约、监管、资金占用），收益就是对承担这些风险的补偿。当竞争变多，收益会被压缩到接近无风险利率 + 风险溢价。

## 2. 主流套利类型与门槛

| 类型 | 机制 | 所需资本 | 速度要求 | 门槛/竞争 | 现实可行性（个人/小资金） |
|---|---|---|---|---|---|
| **资金费率套利**（现货+永续空） | 正资金费时空头收钱，delta 中性 | 中（容量受限） | 低（小时级） | 收益随环境波动，已较拥挤 | ★★★★ 可做（容量小） |
| **期现基差**（期货 vs 现货，CME 等） | 期货升水，持有到期收敛 | 高 | 低 | 需机构账户/通道；2024 高收益后 2025 收窄、部分机构撤出 | ★★ 个人难（通道/资金） |
| **跨所价差**（CEX-CEX） | A 所买 B 所卖 | 中高（需两边预置） | **毫秒级** | 主流币价差基本消失；长尾币有但提币/风控复杂 | ★★ 运维门槛高 |
| **CEX-DEX 套利** | 链上价格 vs 中心化价格 | 中 | 秒级/区块级 | gas、MEV、抢跑、桥延迟；新机制（如 1 秒 subslot）进一步压缩窗口 | ★ 门槛高 |
| **三角套利**（同所多币对） | A→B→C→A 循环 | 小 | 毫秒级 | 学术研究显示扣费后基本不可行 | ☆ 不建议 |
| **统计套利/配对** | 相关币对价差均值回归 | 中 | 分钟~小时级 | 需要模型与风控；拥挤度中等 | ★★★ 可研究 |
| **做市**（market making） | 双边报价赚价差/返佣 | 高（库存风险） | 毫秒~秒级 | 专业团队 + 低延迟 + 风控；协议金库模式（HLP） | ★★ 小资金只能模拟/长尾 |
| **稳定币/跨链/清算** | 脱锚回归、跨链价差、清算奖励 | 中 | 事件驱动 | 合约/桥风险；机会偶发 | ★★ 事件型 |
| **MEV**（链上） | 抢跑、回撤、清算、三明治 | 高（节点/搜索者） | 区块级 | 基础设施+资本；监管与道德争议 | ☆ 不建议个人 |

## 3. 市面上"成功"的项目/机构在做什么

> 以下为公开报道中的案例，用于理解商业模式，不代表可复制。

| 案例 | 模式 | 为什么成功 |
|---|---|---|
| **Wintermute / B2C2 / GSR / Amber** 等做市商 | 中心化+链上做市，赚价差与返佣 | 低延迟基础设施、做市返佣、库存与风控、规模效应；[做市策略介绍](https://docs.ccxt.com/blog/market-making-with-ccxt) |
| **Abraxas**（伦敦 FCA 监管对冲基金） | 在 Hyperliquid 上做 **delta 中性策略**（现货/永续对冲 + 做市），巨量成交、持有大额空头对冲 | 中性化 + 平台深度 + 专业风控；[拆解文章](https://foresightnews.pro/article/detail/101102) |
| **Hyperliquid HLP 金库** | 协议做市金库：为永续提供流动性，承担库存风险换收益 | 平台流量与费用分成；规模增长快（[报道](https://www.coindesk.com/business/2025/06/05/hyperliquid-s-market-making-vault-grows-by-usd250m-in-2-months-despite-jelly-fiasco)），但也承担清算/库存风险（JELLY 事件） |
| **CME/ETF 基差交易台** | 买入现货 ETF/现货 + 做空期货，赚基差 | 机构资金成本低、通道便利；2024 年收益高，2025 年收窄、部分机构撤出（[报道](https://www.htx.com.gl/news/the-end-of-the-arbitrage-era-wall-street-withdraws-from-bitc-2dOYi4Cd/)、[Bitcoin.com](https://api.news.bitcoin.com/bitcoin-arbitrage-yields-shrink-as-institutions-pull-back/)） |
| **CEX-DEX 套利团队** | 链上监听 + 中心化对冲 | 低延迟、gas 优化、资金预置；竞争激烈（[实践长文](https://new.bitpush.news/articles/7547687)、[学术讨论](https://browse-export.arxiv.org/abs/2601.00738)） |
| **MEV 搜索者/做市机器人** | 链上套利、清算、回撤 | 节点/内存池访问、算法与资本门槛 |

**共同点**：没有一个是"看到价差就点鼠标"——都是**基础设施（延迟/资金/风控）+ 规模 + 持续运维**的生意。

## 4. 收益预期（诚实的量级）

| 类型 | 公开可见的收益量级 | 备注 |
|---|---|---|
| 资金费/基差（中性） | 年化 **5%~20%**（随环境大幅波动） | 2024 年高、2025 年收窄；容量有限（我们此前实测 HL PURR/HYPE 约 $12k 容量） |
| 跨所价差（主流币） | 接近 0（被高频吃掉） | 需要毫秒级 |
| 长尾币跨所/CEX-DEX | 单次 0.1%~数个百分点，但不连续 | 提币限制、滑点、失败风险 |
| 做市 | 取决于规模与返佣，头部规模效应明显 | 库存风险大 |
| 统计套利 | 年化 5%~15%（不稳定） | 需要研究与风控 |

> 参考：我们自己的历史回测（Hyperliquid 现货-永续资金费 carry）年化约 18%、回撤 <1%，但**容量只有 $12–14k**——这正是"套利收益 = 风险补偿 + 容量有限"的现实例子。

## 5. 套利的真实成本与风险

1. **交易成本**：手续费、滑点、gas、提币费——很多"价差"扣完成本为负；
2. **执行风险**：单腿成交、延迟、交易所限频、链上拥堵、桥延迟；
3. **资金占用与划转**：跨所需要预置资金，提币有时间与限额；
4. **对手方/合约风险**：交易所、DEX 合约、跨链桥、稳定币脱锚；
5. **拥挤与窗口消失**：2025 年主流基差/跨所套利收益收窄就是例子；
6. **监管与合规**：KYC/税务/地区限制；做市返佣可能涉及协议条款；
7. **操作风险**：API 权限、密钥安全、脚本 bug（单腿裸奔=方向性赌博）。

## 6. 我们能做什么（按可行性排序）

| 优先级 | 方向 | 需要什么 | 预期 |
|---|---|---|---|
| **P1** | **资金费/基差扫描器**（跨所、跨资产、含真实成本） | 公开 API + 成本模型 | 低风险、容量小；可先 paper |
| **P2** | **跨所价差监控（长尾币）** | 多交易所账户、提币规则、延迟监控 | 需要运维；机会零散 |
| **P3** | **统计套利/配对交易**（BTC/ETH/SOL 等） | 研究+回测+风控 | 中等；样本外验证难 |
| **P4** | **做市模拟**（小资金/长尾） | 库存模型、报价引擎 | 高门槛；先模拟 |
| P5 | CEX-DEX/MEV | 低延迟基础设施 | 不建议个人 |

## 7. 建议的落地路线（与现有项目衔接）

1. **数据层**：接多个交易所的 funding/perp/spot 行情与费率（已有 Hyperliquid 数据管线，可扩展 Binance Vision 历史）；
2. **成本模型**：统一手续费/滑点/资金费/提币成本（项目中已有 `quantlab/costs.py`）；
3. **扫描器**：每日/每小时计算"资金费 - 成本"、"跨所价差 - 成本"排序，输出可执行清单；
4. **预注册**：先固定策略参数与通过标准（避免看到结果再调参）；
5. **paper 30 天**：模拟真实成交价与延迟；
6. 只有 paper 通过（扣成本后正收益、回撤可控、样本外稳定）才考虑小资金实盘。

## 8. 结论

- **套利不是"无风险捡钱"**，而是"用资本/速度/运营能力换风险补偿"；
- 成功的项目（做市商、Abraxas、HLP、基差交易台）靠的是**基础设施与规模**，不是单个策略公式；
- 对个人/小资金，**资金费/基差类（P1）**最现实，但收益有限（年化个位数到十几个点，容量小）；
- **不要相信"稳定高收益套利"**——2025 年主流基差收益收窄就是市场给出的答案；
- 下一步建议：先做 **P1 跨所资金费/基差扫描器 + 成本模型**，paper 验证后再谈实盘。

## 参考来源

- [扒一扒币圈「套利」的真相（Foresight News）](https://foresightnews.pro/article/detail/83209)
- [Uncovering the Truth of "Arbitrage" in the Cryptocurrency Circle（ChainCatcher）](https://www.chaincatcher.com/en/article/2178787)
- [拆解 Abraxas：巨鲸如何在 Hyperliquid 上开展中性策略](https://foresightnews.pro/article/detail/101102)
- [Hyperliquid's Market Making Vault Grows by $250M（CoinDesk）](https://www.coindesk.com/business/2025/06/05/hyperliquid-s-market-making-vault-grows-by-usd250m-in-2-months-despite-jelly-fiasco)
- [The End of the Arbitrage Era: Wall Street Withdraws from Bitcoin Basis Trading（HTX Insights）](https://www.htx.com.gl/news/the-end-of-the-arbitrage-era-wall-street-withdraws-from-bitc-2dOYi4Cd/)
- [Bitcoin Arbitrage Yields Shrink as Institutions Pull Back（Bitcoin.com）](https://api.news.bitcoin.com/bitcoin-arbitrage-yields-shrink-as-institutions-pull-back/)
- [CEX-DEX 套利万字长文（Bitpush）](https://new.bitpush.news/articles/7547687)
- [Second Thoughts: 1-second subslots and CEX-DEX arbitrage（arXiv）](https://browse-export.arxiv.org/abs/2601.00738)
- [Wish or reality? On the exploitability of triangular arbitrage（University of Bamberg）](https://fis.uni-bamberg.de/entities/publication/0c9ed181-871f-4860-bc5f-b882cc81743e)
- [Market making: the strategy exchanges literally pay you to run（CCXT）](https://docs.ccxt.com/blog/market-making-with-ccxt)
- [Perpetual Futures and the Opportunities for Hedge Fund Managers（CV5 Capital）](https://www.cv5capital.io/insights/perpetual-futures-and-the-opportunities-for-hedge-fund-managers)
