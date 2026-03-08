from app.core.indicators import Indicators

class Strategy:

    def __init__(self):
        self.name = "ema_rsi_macd_vwap"

    def analyze(self, candles, indicators=None):
        indicators = indicators or {"rsi": True, "macd": True, "ema": True, "volume": True}
        df = Indicators.to_dataframe(candles)
        if len(df) < 60:
            return {
                "signal": "HOLD",
                "trend": "UNKNOWN",
                "price": float(df.iloc[-1]["close"]) if len(df) else 0.0,
                "rsi": 0.0,
                "atr": 0.0,
                "reasons": ["Not enough candles for stable indicators"],
            }

        # indicators
        df["ema20"] = Indicators.ema(df, 20)
        df["ema50"] = Indicators.ema(df, 50)

        df["rsi"] = Indicators.rsi(df)

        macd, signal, hist = Indicators.macd(df)

        df["macd"] = macd
        df["macd_signal"] = signal

        upper, lower = Indicators.bollinger(df)

        df["bb_upper"] = upper
        df["bb_lower"] = lower

        df["vwap"] = Indicators.vwap(df)

        df["atr"] = Indicators.atr(df)

        last = df.iloc[-1]
        prev = df.iloc[-2]

        return self.generate_signal(last, prev, indicators)

    # ==================================
    # SIGNAL ENGINE
    # ==================================

    def generate_signal(self, last, prev, indicators):

        signal = "HOLD"

        reasons = []

        # ========================
        # TREND CHECK
        # ========================

        if indicators.get("ema", True) and last["ema20"] > last["ema50"]:
            trend = "UP"
        elif indicators.get("ema", True):
            trend = "DOWN"
        else:
            trend = "NEUTRAL"

        # ========================
        # BUY CONDITIONS
        # ========================

        if (
            trend == "UP"
            and (not indicators.get("rsi", True) or last["rsi"] < 70)
            and (not indicators.get("macd", True) or last["macd"] > last["macd_signal"])
            and last["close"] > last["vwap"]
        ):

            signal = "BUY"

            reasons.append("Uptrend EMA20>EMA50")
            reasons.append("MACD bullish crossover")
            reasons.append("Price above VWAP")

        # ========================
        # SELL CONDITIONS
        # ========================

        if (
            trend == "DOWN"
            and (not indicators.get("rsi", True) or last["rsi"] > 30)
            and (not indicators.get("macd", True) or last["macd"] < last["macd_signal"])
            and last["close"] < last["vwap"]
        ):

            signal = "SELL"

            reasons.append("Downtrend EMA20<EMA50")
            reasons.append("MACD bearish crossover")
            reasons.append("Price below VWAP")

        return {
            "signal": signal,
            "trend": trend,
            "price": float(last["close"]),
            "rsi": float(last["rsi"]),
            "atr": float(last["atr"]) if str(last["atr"]) != "nan" else 0.0,
            "reasons": reasons
        }
