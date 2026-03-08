from dataclasses import asdict, dataclass


@dataclass
class RiskPlan:
    side: str
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_amount: float
    position_size: float
    risk_reward: float

    def to_dict(self):
        return asdict(self)


def _round_size(size: float, decimals: int = 6) -> float:
    return round(max(size, 0.0), decimals)


def build_risk_plan(
    side: str,
    entry_price: float,
    atr: float,
    balance: float,
    risk_pct: float = 1.0,
    stop_loss_atr_multiplier: float = 1.5,
    take_profit_rr: float = 2.0,
    min_order_size: float = 0.001,
    risk_amount_override: float = 0.0,
) -> RiskPlan:
    if entry_price <= 0:
        raise ValueError("entry_price must be greater than 0")
    if balance <= 0:
        raise ValueError("balance must be greater than 0")

    # Fallback if ATR is not available yet from indicator warmup period.
    effective_atr = atr if atr and atr > 0 else entry_price * 0.003
    stop_distance = effective_atr * stop_loss_atr_multiplier
    risk_amount = risk_amount_override if risk_amount_override > 0 else balance * (risk_pct / 100.0)

    raw_position_size = risk_amount / stop_distance if stop_distance > 0 else 0.0
    position_size = max(_round_size(raw_position_size), min_order_size)

    if side == "BUY":
        stop_loss = entry_price - stop_distance
        take_profit = entry_price + (stop_distance * take_profit_rr)
    else:
        stop_loss = entry_price + stop_distance
        take_profit = entry_price - (stop_distance * take_profit_rr)

    return RiskPlan(
        side=side,
        entry_price=entry_price,
        stop_loss=round(stop_loss, 6),
        take_profit=round(take_profit, 6),
        risk_amount=round(risk_amount, 6),
        position_size=position_size,
        risk_reward=take_profit_rr,
    )
