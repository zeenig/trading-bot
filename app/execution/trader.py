from datetime import datetime, timezone


class Trader:
    def __init__(self, okx_client, dry_run=True):
        self.okx = okx_client
        self.dry_run = dry_run

    def place_order(self, symbol, side, size, market_type="swap", order_type="market", margin_type="cross", leverage=5):
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")

        if self.dry_run:
            return {
                "status": "simulated",
                "order_id": f"SIM-{int(datetime.now(timezone.utc).timestamp())}",
                "symbol": symbol,
                "market_type": market_type,
                "side": side,
                "size": float(size),
                "order_type": order_type,
                "margin_type": margin_type,
                "leverage": leverage,
            }

        if market_type == "spot":
            response = self.okx.place_spot_order(
                inst_id=symbol,
                side=side.lower(),
                size=size,
                order_type=order_type,
            )
        else:
            response = self.okx.place_swap_order(
                inst_id=symbol,
                side=side.lower(),
                size=size,
                order_type=order_type,
                td_mode=margin_type,
            )
        order_data = response.get("data", [{}])[0] if isinstance(response, dict) else {}
        return {
            "status": "submitted",
            "order_id": order_data.get("ordId"),
            "symbol": symbol,
            "market_type": market_type,
            "side": side,
            "size": float(size),
            "order_type": order_type,
            "margin_type": margin_type,
            "leverage": leverage,
            "exchange_response": response,
        }
