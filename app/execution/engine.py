import time
from datetime import datetime, timezone
from threading import Lock

from app.core.risk import build_risk_plan
from app.core.runtime_settings import get_runtime_settings
from app.core.strategy import Strategy
from app.exchange.okx import OKXClient
from app.execution.trader import Trader
from app.services.ai_engine import AIEngine
from app.services.telegram import send_message
from app.storage import db
from app.utils.logger import get_logger


logger = get_logger("execution.engine")


class TradingEngine:
    def __init__(self):
        self.okx = OKXClient()
        self.strategy = Strategy()
        self.ai = AIEngine()
        self.trader = Trader(self.okx, dry_run=True)

        self._lock = Lock()
        self.running = False
        self.last_cycle = None

    def _utc_now(self):
        return datetime.now(timezone.utc).isoformat()

    def _extract_candles(self, response):
        if isinstance(response, dict):
            return response.get("data", [])
        if isinstance(response, list):
            return response
        return []

    def _extract_balance(self, response):
        if not isinstance(response, dict):
            return 1000.0
        try:
            details = response.get("data", [{}])[0].get("details", [])
            if not details:
                return 1000.0
            usdt_line = next((item for item in details if item.get("ccy") == "USDT"), details[0])
            return float(usdt_line.get("availBal") or usdt_line.get("cashBal") or 1000.0)
        except Exception:
            return 1000.0

    def _asset_from_symbol(self, symbol):
        return str(symbol).split("-")[0].upper()

    def _daily_realized_loss(self):
        today = datetime.now(timezone.utc).date()
        total_loss = 0.0
        for trade in db.fetch_trades(500):
            pnl = float(trade.get("realized_pnl", 0) or 0)
            created_at = trade.get("created_at")
            if not created_at:
                continue
            try:
                day = datetime.fromisoformat(str(created_at).replace("Z", "+00:00")).date()
            except Exception:
                continue
            if day == today and pnl < 0:
                total_loss += abs(pnl)
        return total_loss

    def _realized_drawdown(self, baseline_capital):
        total_pnl = 0.0
        for trade in db.fetch_trades(1000):
            total_pnl += float(trade.get("realized_pnl", 0) or 0)
        loss = abs(total_pnl) if total_pnl < 0 else 0.0
        if baseline_capital <= 0:
            return 0.0
        return (loss / baseline_capital) * 100.0

    def _risk_gate(self, settings, symbol):
        risk = settings["RISK_CONFIG"]
        if not risk["autoTrading"]:
            return False, "Auto trading disabled"

        open_positions = [p for p in db.fetch_positions(500) if str(p.get("status", "")).upper() == "OPEN"]
        if len(open_positions) >= risk["maxOpenPositions"]:
            return False, "Max open positions reached"

        if self._daily_realized_loss() >= risk["maxDailyLoss"]:
            return False, "Max daily loss reached"
        if self._realized_drawdown(risk["maxCapitalAllocation"]) >= risk["maxDrawdown"]:
            return False, "Max drawdown reached"

        asset = self._asset_from_symbol(symbol)
        existing = [p for p in open_positions if self._asset_from_symbol(p.get("symbol", "")) == asset]
        if existing:
            return False, f"Exposure already open for {asset}"

        return True, ""

    def _is_symbol_allowed(self, settings, symbol, market_type):
        strategy = settings["STRATEGY_CONFIG"]
        asset = self._asset_from_symbol(symbol)
        if asset in strategy["blockedAssets"]:
            return False, "Blocked asset"
        if market_type == "spot" and strategy["allowedSpotAssets"] and asset not in strategy["allowedSpotAssets"]:
            return False, "Not in allowedSpotAssets"
        if market_type == "swap" and strategy["allowedSwapAssets"] and asset not in strategy["allowedSwapAssets"]:
            return False, "Not in allowedSwapAssets"
        return True, ""

    def _passes_volume_filter(self, settings, symbol):
        min_volume = settings["STRATEGY_CONFIG"]["minVolume"]
        if min_volume <= 0:
            return True
        try:
            ticker_resp = self.okx.get_ticker(symbol)
            data = ticker_resp.get("data", [{}])[0] if isinstance(ticker_resp, dict) else {}
            volume_24h = float(data.get("volCcy24h") or data.get("vol24h") or 0.0)
            return volume_24h >= min_volume
        except Exception:
            return False

    def _risk_amount(self, risk_cfg, balance):
        if risk_cfg["riskPerTradeType"] == "FIXED":
            return min(risk_cfg["maxRiskPerTrade"], risk_cfg["maxCapitalAllocation"])
        return balance * (risk_cfg["maxRiskPerTrade"] / 100.0)

    def _apply_global_tp_sl(self, strategy_cfg, side, entry_price, risk_plan):
        sl_pct = strategy_cfg["globalStopLoss"]
        tp_pct = strategy_cfg["globalTakeProfit"]
        if sl_pct > 0:
            risk_plan.stop_loss = entry_price * (1 - sl_pct / 100.0) if side == "BUY" else entry_price * (1 + sl_pct / 100.0)
        if tp_pct > 0:
            risk_plan.take_profit = entry_price * (1 + tp_pct / 100.0) if side == "BUY" else entry_price * (1 - tp_pct / 100.0)

    def _apply_runtime(self, settings):
        mode = settings["OKX_MODE"]
        if mode == "live":
            self.okx.api_key = settings["OKX_LIVE_API_KEY"]
            self.okx.secret_key = settings["OKX_LIVE_SECRET"]
            self.okx.passphrase = settings["OKX_LIVE_PASSPHRASE"]
        else:
            self.okx.api_key = settings["OKX_TESTNET_API_KEY"]
            self.okx.secret_key = settings["OKX_TESTNET_SECRET"]
            self.okx.passphrase = settings["OKX_TESTNET_PASSPHRASE"]
        self.okx.mode = mode
        self.trader.dry_run = settings["DRY_RUN"]

    def _resolve_symbol_targets(self, settings):
        targets = db.fetch_active_symbols()
        if targets:
            return targets

        # Backward-compatible fallback to bot_settings list keys if bot_symbols table is empty.
        return [{"symbol": s, "market_type": "spot"} for s in settings.get("SPOT_SYMBOLS", [])] + [
            {"symbol": s, "market_type": "swap"} for s in settings.get("SWAP_SYMBOLS", [])
        ]

    def monitor_positions(self, settings):
        try:
            if settings["DRY_RUN"]:
                return []
            response = self.okx.get_positions(inst_type="SWAP")
            positions = response.get("data", []) if isinstance(response, dict) else []
            snapshots = []
            for pos in positions:
                snapshot = {
                    "symbol": pos.get("instId"),
                    "side": "LONG" if pos.get("posSide", "").lower() == "long" else "SHORT",
                    "size": float(pos.get("pos", 0) or 0),
                    "entry_price": float(pos.get("avgPx", 0) or 0),
                    "unrealized_pnl": float(pos.get("upl", 0) or 0),
                    "status": "OPEN",
                    "source": "okx",
                }
                db.save_position(snapshot)
                snapshots.append(snapshot)
            return snapshots
        except Exception as exc:
            logger.warning("Position monitor failed: %s", exc)
            return []

    def _run_symbol_cycle(self, settings, symbol, market_type):
        allowed, deny_reason = self._is_symbol_allowed(settings, symbol, market_type)
        if not allowed:
            return {
                "symbol": symbol,
                "market_type": market_type,
                "strategy_signal": "HOLD",
                "final_signal": "HOLD",
                "trade_status": "skipped",
                "trade_reason": deny_reason,
                "risk_plan": None,
                "signal": {"symbol": symbol, "market_type": market_type, "signal": "HOLD", "final_signal": "HOLD"},
                "trade": {"status": "skipped", "reason": deny_reason, "symbol": symbol, "market_type": market_type},
            }

        if not self._passes_volume_filter(settings, symbol):
            return {
                "symbol": symbol,
                "market_type": market_type,
                "strategy_signal": "HOLD",
                "final_signal": "HOLD",
                "trade_status": "skipped",
                "trade_reason": "Volume below threshold",
                "risk_plan": None,
                "signal": {"symbol": symbol, "market_type": market_type, "signal": "HOLD", "final_signal": "HOLD"},
                "trade": {"status": "skipped", "reason": "Volume below threshold", "symbol": symbol, "market_type": market_type},
            }

        market_response = self.okx.get_candles(symbol, settings["TRADING_BAR"], settings["TRADING_CANDLE_LIMIT"])
        candles = self._extract_candles(market_response)
        if not candles:
            raise RuntimeError(f"No candle data received from OKX for {symbol}")

        strategy_result = self.strategy.analyze(candles, settings["STRATEGY_CONFIG"]["indicators"])
        ai_result = self.ai.evaluate(strategy_result, settings)
        final_signal = ai_result["decision"]

        signal_record = {
            "symbol": symbol,
            "market_type": market_type,
            "signal": strategy_result.get("signal"),
            "final_signal": final_signal,
            "trend": strategy_result.get("trend"),
            "price": strategy_result.get("price"),
            "rsi": strategy_result.get("rsi"),
            "atr": strategy_result.get("atr", 0.0),
            "strategy_reasons": strategy_result.get("reasons", []),
            "ai_confidence": ai_result.get("confidence"),
            "ai_reason": ai_result.get("rationale"),
        }
        db.save_signal(signal_record)

        trade_result = {"status": "skipped", "reason": "HOLD signal", "symbol": symbol, "market_type": market_type}
        risk_plan_dict = None

        if final_signal in {"BUY", "SELL"}:
            allowed_trade, risk_reason = self._risk_gate(settings, symbol)
            if not allowed_trade:
                trade_result = {"status": "skipped", "reason": risk_reason, "symbol": symbol, "market_type": market_type}
                return {
                    "symbol": symbol,
                    "market_type": market_type,
                    "strategy_signal": strategy_result.get("signal"),
                    "final_signal": final_signal,
                    "trade_status": trade_result.get("status"),
                    "trade_reason": trade_result.get("reason"),
                    "risk_plan": risk_plan_dict,
                    "signal": signal_record,
                    "trade": trade_result,
                }

            try:
                balance_response = self.okx.get_balance("USDT") if not settings["DRY_RUN"] else {}
                balance = self._extract_balance(balance_response) if balance_response else 1000.0
            except Exception as exc:
                logger.warning("Balance fetch failed, using fallback balance: %s", exc)
                balance = 1000.0

            risk_cfg = settings["RISK_CONFIG"]
            strategy_cfg = settings["STRATEGY_CONFIG"]
            risk_amount = self._risk_amount(risk_cfg, balance)
            risk_plan = build_risk_plan(
                side=final_signal,
                entry_price=float(strategy_result.get("price", 0)),
                atr=float(strategy_result.get("atr", 0) or 0),
                balance=balance,
                risk_pct=1.0,
                stop_loss_atr_multiplier=1.5,
                take_profit_rr=2.0,
                min_order_size=0.001,
                risk_amount_override=risk_amount,
            )
            self._apply_global_tp_sl(strategy_cfg, final_signal, risk_plan.entry_price, risk_plan)

            max_pair_value = balance * (risk_cfg["maxExposurePerPair"] / 100.0)
            if risk_plan.entry_price > 0:
                capped_size = max_pair_value / risk_plan.entry_price
                risk_plan.position_size = max(min(risk_plan.position_size, capped_size), 0.0)
            risk_plan_dict = risk_plan.to_dict()
            if risk_plan.position_size <= 0:
                trade_result = {"status": "skipped", "reason": "Position size is zero after risk limits", "symbol": symbol, "market_type": market_type}
                return {
                    "symbol": symbol,
                    "market_type": market_type,
                    "strategy_signal": strategy_result.get("signal"),
                    "final_signal": final_signal,
                    "trade_status": trade_result.get("status"),
                    "trade_reason": trade_result.get("reason"),
                    "risk_plan": risk_plan_dict,
                    "signal": signal_record,
                    "trade": trade_result,
                }
            trade_result = self.trader.place_order(
                symbol,
                final_signal,
                risk_plan.position_size,
                market_type=market_type,
                order_type=settings["STRATEGY_CONFIG"]["orderType"].lower(),
                margin_type=risk_cfg["marginType"].lower(),
                leverage=risk_cfg["maxLeverage"],
            )

            trade_record = {
                "symbol": symbol,
                "market_type": market_type,
                "side": final_signal,
                "entry_price": risk_plan.entry_price,
                "size": risk_plan.position_size,
                "stop_loss": risk_plan.stop_loss,
                "take_profit": risk_plan.take_profit,
                "risk_amount": risk_plan.risk_amount,
                "order_id": trade_result.get("order_id"),
                "status": trade_result.get("status"),
            }
            db.save_trade(trade_record)
            db.save_position({**trade_record, "status": "OPEN", "source": trade_result.get("status")})
            send_message(
                settings,
                f"Trade {trade_result.get('status')}: {final_signal} {symbol} ({market_type}) size={risk_plan.position_size}",
            )

        return {
            "symbol": symbol,
            "market_type": market_type,
            "strategy_signal": strategy_result.get("signal"),
            "final_signal": final_signal,
            "trade_status": trade_result.get("status"),
            "trade_reason": trade_result.get("reason"),
            "risk_plan": risk_plan_dict,
            "signal": signal_record,
            "trade": trade_result,
        }

    def run_cycle(self):
        with self._lock:
            settings = get_runtime_settings()
            self._apply_runtime(settings)
            started = self._utc_now()
            targets = self._resolve_symbol_targets(settings)
            if not targets:
                raise RuntimeError("No symbols configured. Set SPOT_SYMBOLS and/or SWAP_SYMBOLS in bot_settings.")

            results = []
            for target in targets:
                symbol = target["symbol"]
                market_type = target["market_type"]
                try:
                    result = self._run_symbol_cycle(settings, symbol, market_type)
                    cycle_summary = {
                        "timestamp": started,
                        "symbol": symbol,
                        "market_type": market_type,
                        "strategy_signal": result["strategy_signal"],
                        "final_signal": result["final_signal"],
                        "trade_status": result["trade_status"],
                        "trade_reason": result["trade_reason"],
                        "risk_plan": result["risk_plan"],
                    }
                    db.save_cycle(cycle_summary)
                    results.append({**result, "cycle": cycle_summary})
                except Exception as exc:
                    logger.exception("Symbol cycle failed for %s (%s): %s", symbol, market_type, exc)
                    send_message(settings, f"Cycle failed for {symbol} ({market_type}): {exc}")
                    results.append(
                        {
                            "symbol": symbol,
                            "market_type": market_type,
                            "error": str(exc),
                            "trade_status": "failed",
                        }
                    )

            summary = {
                "timestamp": started,
                "symbols_processed": len(results),
                "successful": len([item for item in results if item.get("error") is None]),
                "failed": len([item for item in results if item.get("error")]),
                "results": results,
            }
            self.last_cycle = summary
            return summary

    def run_continuous(self):
        self.running = True
        logger.info("Trading loop started")
        settings = get_runtime_settings()
        while self.running:
            try:
                settings = get_runtime_settings()
                self.run_cycle()
                self.monitor_positions(settings)
            except Exception as exc:
                logger.exception("Cycle failed: %s", exc)
            time.sleep(max(1, int(settings["LOOP_INTERVAL_SECONDS"])))

    def stop(self):
        self.running = False
        logger.info("Trading loop stopped")


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = TradingEngine()
    return _engine
