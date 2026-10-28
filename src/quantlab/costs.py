"""统一成本模型：手续费 + 滑点 + 资金费（可扩展）。

所有比例均为小数（0.00045 = 4.5 bps）。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    taker_bps: float = 4.5        # taker 手续费，单位 bps
    maker_bps: float = 1.5        # maker 手续费，单位 bps
    slippage_bps: float = 5.0     # 每边滑点估计，单位 bps

    def fee_rate(self, maker: bool = False) -> float:
        return (self.maker_bps if maker else self.taker_bps) / 10_000.0

    def slippage_rate(self) -> float:
        return self.slippage_bps / 10_000.0

    def per_leg_cost_rate(self, maker: bool = False) -> float:
        """单边成本率（手续费 + 滑点）。"""
        return self.fee_rate(maker) + self.slippage_rate()

    def trade_cost(self, notional: float, legs: int = 2, maker: bool = False) -> float:
        """一笔交易（默认双边）的成本金额。"""
        return abs(notional) * self.per_leg_cost_rate(maker) * legs

    def funding_payment(self, notional: float, funding_rate: float) -> float:
        """资金费现金流：正资金费、空头收钱（返回正数）；多头付钱时为负。"""
        return -abs(notional) * float(funding_rate)
