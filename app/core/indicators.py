import pandas as pd
import numpy as np

class Indicators:

    @staticmethod
    def to_dataframe(candles):
        """
        Convert OKX candles to pandas dataframe
        """
        df = pd.DataFrame(
            candles,
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "volCcy",
                "volCcyQuote",
                "confirm",
            ],
        )

        df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms")

        numeric_cols = ["open", "high", "low", "close", "volume"]
        df[numeric_cols] = df[numeric_cols].astype(float)

        df = df.sort_values("timestamp")

        return df

    # ===============================
    # EMA
    # ===============================

    @staticmethod
    def ema(df, period=20):
        return df["close"].ewm(span=period, adjust=False).mean()

    # ===============================
    # RSI
    # ===============================

    @staticmethod
    def rsi(df, period=14):

        delta = df["close"].diff()

        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss

        rsi = 100 - (100 / (1 + rs))

        return rsi

    # ===============================
    # MACD
    # ===============================

    @staticmethod
    def macd(df):

        ema12 = df["close"].ewm(span=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, adjust=False).mean()

        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - signal

        return macd, signal, histogram

    # ===============================
    # Bollinger Bands
    # ===============================

    @staticmethod
    def bollinger(df, period=20):

        sma = df["close"].rolling(window=period).mean()
        std = df["close"].rolling(window=period).std()

        upper = sma + (std * 2)
        lower = sma - (std * 2)

        return upper, lower

    # ===============================
    # VWAP
    # ===============================

    @staticmethod
    def vwap(df):

        typical_price = (df["high"] + df["low"] + df["close"]) / 3

        vwap = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()

        return vwap

    # ===============================
    # ATR (Volatility)
    # ===============================

    @staticmethod
    def atr(df, period=14):

        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())

        ranges = pd.concat([high_low, high_close, low_close], axis=1)

        true_range = ranges.max(axis=1)

        atr = true_range.rolling(period).mean()

        return atr
