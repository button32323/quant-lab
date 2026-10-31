# GitHub 借鉴清单：加密量化/套利开源项目

> 扫描时间：2026-10-31 ｜ 方法：GitHub API 按 star 搜索 + 读取 README/目录结构。所有结论来自公开仓库页面/README，代码仅作参考，**没有复制任何代码进本项目**。

## 1. 扫描到的项目（按相关性）

| 项目 | 星 | 语言/许可 | 一句话 |
|---|---:|---|---|
| [ccxt/ccxt](https://github.com/ccxt/ccxt) | 44.6k | Python / MIT | 100+ 交易所统一 API，事实标准 |
| [hummingbot/hummingbot](https://github.com/hummingbot/hummingbot) | 20.9k | Python / Apache-2.0 | 做市/套利机器人框架，连接器生态 |
| [hyperliquid-dex/hyperliquid-python-sdk](https://github.com/hyperliquid-dex/hyperliquid-python-sdk) | 1.9k | Python / MIT | Hyperliquid 官方 SDK（签名/下单） |
| [nkaz001/hftbacktest](https://github.com/nkaz001/hftbacktest) | 5.0k | Rust+Python / MIT | 高频回测：延迟、队列位置、L2 重建 |
| [aoki-h-jp/funding-rate-arbitrage](https://github.com/aoki-h-jp/funding-rate-arbitrage) | 310 | Python / MIT | 跨 CEX 资金费差检测库（不自动执行） |
| [50shadesofgwei/funding-rate-arbitrage](https://github.com/50shadesofgwei/funding-rate-arbitrage) | 184 | Python / MIT | DEX-DEX 中性套利模板（GMX/Synthetix） |
| [enarjord/passivbot](https://github.com/enarjord/passivbot) | 2.2k | Python+Rust / Unlicense | 网格/DCA 机器人，支持 Hyperliquid |
| [wangzhe3224/awesome-systematic-trading](https://github.com/wangzhe3224/awesome-systematic-trading) | 5.4k | HTML / MIT | 系统化交易资源大全 |

## 2. 最值得借鉴的 6 个点

### ① 成本优先：先扣佣金，再看资金费（来自 aoki-h-jp README 示例）

该项目 README 的真实输出：

```
Funding Rate: 0.1480 %
Commission:  0.32 %
Revenue: -0.21 / 100USDT   ← 看起来 0.148% 的"机会"，扣费后是负的
```

**启示**：资金费扫描器必须把手续费、滑点、提币/桥成本全部计入，再排序；我们项目已经是"成本优先"（0.415%/边、L2 滑点实测），这条正好互证。

### ② 交易所适配层（来自 50shades 仓库结构 + ccxt）

50shades 的目录：`APICaller/{Binance,ByBit,GMX,OKX,Synthetix}/...`、`Backtesting/`、`MatchingEngine/`、`PositionMonitor/`、`GlobalUtils/`。

**启示**：
- 每个交易所一个 caller，统一接口 → 可以照这个思路做**跨所资金费扫描器**；
- 不要自己手写 100 个交易所的签名/限频——直接用 **ccxt**（MIT，Python 原生，统一 `fetchFundingRate`、`fetchOHLCV`、`fetchTicker`）；
- 我们的 `quantlab/binance_vision.py`、`hyperliquid.py` 是"单所适配器"雏形，可扩展成 `adapters/` 层。

### ③ 官方 SDK 做下单/签名（hyperliquid-python-sdk）

- 官方 SDK 提供 `Info`（只读）与 `Exchange`（签名下单）、API Wallet 机制（主钱包 + API 私钥分离）；
- 官方推荐"**API wallet**"：主钱包地址作为 account_address，API 私钥单独生成、可撤销；
- **借鉴做法**：真到实盘阶段，用官方 SDK 构建订单（dry-run 先打印），不自己实现签名；API 私钥只存本地环境变量/配置文件，绝不入库；
- 我们当前的实盘计划（逐笔授权、仅交易权限）与官方 API wallet 模型一致。

### ④ 回测真实性（hftbacktest）

- 它强调 **feed latency + order latency + queue position**，并说："如果 2025 年 1 月的实盘策略，回测同期结果对不上，就别谈优化"；
- **启示**：我们目前是日线 carry 回测，不需要 L2/队列；但若以后做 **做市/L2 套利**，不要用"日线收盘价成交"这种乐观假设，要么用 hftbacktest，要么自建延迟+盘口撮合模型；
- 我们已有的"次日开盘成交、L2 滑点实测、手续费/资金费对账"是同一思路的简化版。

### ⑤ 交易框架的分层（hummingbot）

- Hummingbot 把 **connectors / strategies / risk / scripting / data feed** 分层，支持 CEX+DEX，Apache-2.0（可商用但需保留声明）；
- **启示**：不必引入它的重框架，但可以借鉴其分层：`connector`（交易所）→ `strategy`（信号）→ `risk`（风控）→ `executor`（下单/对账）→ `reporting`；
- 我们的 `paper.py` 已经是"strategy+executor+reconcile+report"的雏形，可以按这个分法重构。

### ⑥ 实盘前的"测试网/纸面"纪律（50shades + passivbot）

- 50shades 明确写"先 testnet，再实盘"，并声明"未经过大规模生产验证，风险自负"；
- passivbot 有明确的 live/testnet 模式、配置迁移工具、版本说明；
- **启示**：我们坚持 paper 30 天、逐笔授权、不做自动实盘，方向与这些项目一致；将来若实盘，先用 testnet + dry-run + 小额。

## 3. 不要借鉴的地方

| 类型 | 例子 | 原因 |
|---|---|---|
| 高星"AI 交易终端/网格/DCA" | OctoBot、各种 AI agent | 无公开可复现 edge，营销属性强；网格/DCA 在单边行情会爆仓 |
| 直接复制 GPL/AGPL 代码 | OctoBot（GPL-3.0）、部分 arb 项目 | 传染性许可，不能随意并入我们仓库；只借鉴思路/自研 |
| 高频/做市"抄来就跑" | hftbacktest 生态的做市策略 | 需要低延迟基础设施与库存风控；个人小资金先不碰 |
| 多交易所"自动搬砖"脚本 | 各种三角套利 bot | 主流币价差已被毫秒级吃掉；提币限制/风控/对手方风险大 |

> 我们仓库**没有引入上述任何依赖或代码**；如果以后要用 ccxt（MIT）/hyperliquid-python-sdk（MIT）/hftbacktest（MIT），可以安全引入，但需要在 requirements 里写明并测试。

## 4. 对照我们项目的差距

| 能力 | 我们现状 | 可借鉴/下一步 |
|---|---|---|
| 交易所适配 | 已有 Binance Vision（只读历史）+ Hyperliquid（只读+paper） | 加 **ccxt** 做跨所只读数据（funding/perp/spot 扫描） |
| 下单/签名 | 无（只有 paper 虚拟账） | 实盘时用 **hyperliquid-python-sdk**（API wallet + dry-run） |
| 回测真实性 | 日线 + L2 滑点实测 + 成本模型 | 做市/高频再引入 **hftbacktest** 思路 |
| 数据/机会扫描 | 无跨所扫描器 | 做 **P1 跨所资金费/价差扫描器**（只读、净收益排序） |
| 风控/对账 | 已有 paper 对账、预登记、gate、告警 | 保持；可加 testnet 模式 |
| 工程规范 | 37 单测、自检、链接/密钥扫描、CI 未上 | 若推 GitHub 可参考旧仓库的 GitHub Actions 跑单测 |

## 5. 建议的下一步（按优先级）

1. **P1（推荐）**：基于 ccxt 写"跨所资金费/价差扫描器"（只读）：
   - 输入：BTC/ETH/SOL/PURR/HYPE 等；
   - 输出：扣手续费/滑点后的净年化、容量估计、风险标记；
   - 只写报告，不自动下单；
2. **P2**：用 hyperliquid-python-sdk 写一个**只读 + dry-run 订单构建器**（不接私钥、不提交订单），为将来实盘做准备；
3. **P3**：如果决定做 L2/做市，再评估 hftbacktest（需要 tick 数据与撮合模型）；
4. 维持现有 carry + paper 路线，不因 GitHub 项目多就切换策略。

## 6. 结论

- 开源世界**值得借鉴的是工程结构与基础设施**（ccxt 适配层、官方 SDK、hftbacktest 的真实性、hummingbot 分层），而不是"现成策略"；
- 最值钱的一条经验来自 aoki-h-jp 的示例输出：**"资金费 0.148% vs 佣金 0.32% = 负收益"**——和我们"成本优先"的结论完全一致；
- 我们的方案（carry + 严格成本 + paper + 对账）在开源项目里属于"研究/验证型"路线，和"高星交易机器人"是两类东西。

## 参考链接

- [ccxt](https://github.com/ccxt/ccxt) ｜ [hummingbot](https://github.com/hummingbot/hummingbot) ｜ [hyperliquid-python-sdk](https://github.com/hyperliquid-dex/hyperliquid-python-sdk)
- [hftbacktest](https://github.com/nkaz001/hftbacktest) ｜ [aoki-h-jp/funding-rate-arbitrage](https://github.com/aoki-h-jp/funding-rate-arbitrage) ｜ [50shadesofgwei/funding-rate-arbitrage](https://github.com/50shadesofgwei/funding-rate-arbitrage)
- [passivbot](https://github.com/enarjord/passivbot) ｜ [awesome-systematic-trading](https://github.com/wangzhe3224/awesome-systematic-trading)
