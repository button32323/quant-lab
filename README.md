# 量化项目（新）

> 一个从零开始的量化研究项目。原则：**数据可复现、成本口径统一、先 paper 后实盘、实盘逐笔授权**。

## 快速开始

```bash
# 1) 安装依赖（建议先建虚拟环境）
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 2) 跑单元测试
python -m unittest discover -s tests -v

# 3) 拉取 Hyperliquid 公开数据（示例）
python scripts/demo/hl_fetch.py --coin HYPE --interval 1d
```

## 目录结构

```
src/quantlab/      核心库（数据 / 指标 / 成本模型）
tests/             单元测试（纯函数，离线可跑）
scripts/demo/      示例脚本（拉数据、简单统计）
docs/              设计文档与决策记录
config/            配置模板（不含任何密钥）
data/              本地数据目录（git 忽略，不入库）
```

## 已有基础模块

| 模块 | 内容 |
|---|---|
| `quantlab/hyperliquid.py` | Hyperliquid 公开 API（资金费、K 线、市场上下文），无需密钥 |
| `quantlab/metrics.py` | 收益/波动/Sharpe/最大回撤等指标 |
| `quantlab/costs.py` | 统一成本模型（taker/maker/滑点/资金费） |

## 研究文档

- [docs/DESIGN.md](docs/DESIGN.md) — 研究流程与原则
- [docs/ARBITRAGE_RESEARCH.md](docs/ARBITRAGE_RESEARCH.md) — 套利类型、成功案例与可行路线
- [reports/PLAN_100_1000.md](reports/PLAN_100_1000.md) — **$100–$1,000 本金方案对比与推荐**
- [reports/CARRY_VALIDATION.md](reports/CARRY_VALIDATION.md) — carry 稳健性/压力/Bootstrap
- [reports/CAPACITY_TIERS.md](reports/CAPACITY_TIERS.md) — 容量与本金额度（$27–$20k）
- [reports/SLIPPAGE_DEPTH.md](reports/SLIPPAGE_DEPTH.md) — 盘口滑点实测（L2）
- [reports/FUNDING_REGIME.md](reports/FUNDING_REGIME.md) — 资金费环境与盈亏平衡
- [docs/PAPER_PLAN.md](docs/PAPER_PLAN.md) — 30 天 paper 验证计划

## 红线（写死）

- 不借钱、不加杠杆（除非策略明确验证并通过风控）；
- 密钥/私钥 **不入库**（`.gitignore` 已排除 `data/`、`.env`）；
- 实盘必须逐笔授权，脚本默认只有 dry-run 能力；
- 任何策略先 paper 验证，再考虑实盘。

## 备注

- 旧项目归档：`C:\量化备份\`（**含钱包私钥，务必离线保管，不要上传**）；
- 新项目不继承旧项目的任何密钥/钱包文件。






