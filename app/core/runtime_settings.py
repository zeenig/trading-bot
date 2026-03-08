import json
import time
from threading import Lock

from app import config
from app.storage.db import fetch_runtime_settings


_cache = None
_cache_ts = 0.0
_lock = Lock()

_RISK_DEFAULTS = {
    "autoTrading": True,
    "maxCapitalAllocation": 10_000.0,
    "riskPerTradeType": "PERCENT",
    "maxRiskPerTrade": 1.0,
    "maxDrawdown": 20.0,
    "maxDailyLoss": 500.0,
    "maxOpenPositions": 5,
    "maxExposurePerPair": 25.0,
    "maxLeverage": 5,
    "marginType": "CROSS",
    "trailingStop": False,
    "riskLevelProfile": "MODERATE",
}

_STRATEGY_DEFAULTS = {
    "activeStrategy": "TREND",
    "aiEnabled": False,
    "minConfidence": 70.0,
    "timeframe": "1m",
    "orderType": "MARKET",
    "allowedSpotAssets": [],
    "allowedSwapAssets": [],
    "blockedAssets": [],
    "minVolume": 0.0,
    "globalTakeProfit": 0.0,
    "globalStopLoss": 0.0,
    "indicators": {"rsi": True, "macd": True, "ema": True, "volume": True},
    "telegram": {"enabled": False, "botToken": "", "chatId": ""},
}

_DEFAULTS = {
    "OKX_TESTNET_API_KEY": "",
    "OKX_TESTNET_SECRET": "",
    "OKX_TESTNET_PASSPHRASE": "",
    "OKX_LIVE_API_KEY": "",
    "OKX_LIVE_SECRET": "",
    "OKX_LIVE_PASSPHRASE": "",
    "OKX_MODE": "testnet",
    "SPOT_SYMBOLS": "",
    "SWAP_SYMBOLS": "",
    "TRADING_CANDLE_LIMIT": 200,
    "LOOP_INTERVAL_SECONDS": 60,
    "DRY_RUN": True,
    "GEMINI_API_KEY": "",
    "GEMINI_MODEL": "gemini-1.5-flash",
    "AUTO_START_CYCLE": False,
}


def _to_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raw = str(value).strip()
    if not raw:
        return []
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    parts = [item.strip().strip("'\"") for item in raw.split(",")]
    return [item for item in parts if item]


def _to_obj(value):
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def _normalize_risk(merged):
    raw = _RISK_DEFAULTS.copy()
    raw.update(_to_obj(merged.get("RISK_CONFIG")))
    return {
        "autoTrading": _to_bool(raw.get("autoTrading"), True),
        "maxCapitalAllocation": _to_float(raw.get("maxCapitalAllocation"), 10_000.0),
        "riskPerTradeType": str(raw.get("riskPerTradeType", "PERCENT")).upper(),
        "maxRiskPerTrade": _to_float(raw.get("maxRiskPerTrade"), 1.0),
        "maxDrawdown": _to_float(raw.get("maxDrawdown"), 20.0),
        "maxDailyLoss": _to_float(raw.get("maxDailyLoss"), 500.0),
        "maxOpenPositions": _to_int(raw.get("maxOpenPositions"), 5),
        "maxExposurePerPair": _to_float(raw.get("maxExposurePerPair"), 25.0),
        "maxLeverage": max(1, min(_to_int(raw.get("maxLeverage"), 5), 100)),
        "marginType": str(raw.get("marginType", "CROSS")).upper(),
        "trailingStop": _to_bool(raw.get("trailingStop"), False),
        "riskLevelProfile": str(raw.get("riskLevelProfile", "MODERATE")).upper(),
    }


def _normalize_strategy(merged):
    raw = _STRATEGY_DEFAULTS.copy()
    raw.update(_to_obj(merged.get("STRATEGY_CONFIG")))

    indicators = _STRATEGY_DEFAULTS["indicators"].copy()
    indicators.update(_to_obj(raw.get("indicators")))

    telegram = _STRATEGY_DEFAULTS["telegram"].copy()
    telegram.update(_to_obj(raw.get("telegram")))

    return {
        "activeStrategy": str(raw.get("activeStrategy", "TREND")).upper(),
        "aiEnabled": _to_bool(raw.get("aiEnabled"), False),
        "minConfidence": _to_float(raw.get("minConfidence"), 70.0),
        "timeframe": str(raw.get("timeframe", "1m")),
        "orderType": str(raw.get("orderType", "MARKET")).upper(),
        "allowedSpotAssets": [x.upper() for x in _to_list(raw.get("allowedSpotAssets"))],
        "allowedSwapAssets": [x.upper() for x in _to_list(raw.get("allowedSwapAssets"))],
        "blockedAssets": [x.upper() for x in _to_list(raw.get("blockedAssets"))],
        "minVolume": _to_float(raw.get("minVolume"), 0.0),
        "globalTakeProfit": _to_float(raw.get("globalTakeProfit"), 0.0),
        "globalStopLoss": _to_float(raw.get("globalStopLoss"), 0.0),
        "indicators": {
            "rsi": _to_bool(indicators.get("rsi"), True),
            "macd": _to_bool(indicators.get("macd"), True),
            "ema": _to_bool(indicators.get("ema"), True),
            "volume": _to_bool(indicators.get("volume"), True),
        },
        "telegram": {
            "enabled": _to_bool(telegram.get("enabled"), False),
            "botToken": str(telegram.get("botToken") or ""),
            "chatId": str(telegram.get("chatId") or ""),
        },
    }


def _normalize(values):
    merged = _DEFAULTS.copy()
    merged.update(values or {})
    mode = str(merged.get("OKX_MODE") or "testnet").strip().lower()

    risk_config = _normalize_risk(merged)
    strategy_config = _normalize_strategy(merged)

    return {
        "OKX_MODE": mode,
        "OKX_TESTNET_API_KEY": str(merged.get("OKX_TESTNET_API_KEY") or ""),
        "OKX_TESTNET_SECRET": str(merged.get("OKX_TESTNET_SECRET") or ""),
        "OKX_TESTNET_PASSPHRASE": str(merged.get("OKX_TESTNET_PASSPHRASE") or ""),
        "OKX_LIVE_API_KEY": str(merged.get("OKX_LIVE_API_KEY") or ""),
        "OKX_LIVE_SECRET": str(merged.get("OKX_LIVE_SECRET") or ""),
        "OKX_LIVE_PASSPHRASE": str(merged.get("OKX_LIVE_PASSPHRASE") or ""),
        "SPOT_SYMBOLS": _to_list(merged.get("SPOT_SYMBOLS")),
        "SWAP_SYMBOLS": _to_list(merged.get("SWAP_SYMBOLS")),
        "TRADING_BAR": strategy_config["timeframe"],
        "TRADING_CANDLE_LIMIT": _to_int(merged["TRADING_CANDLE_LIMIT"], 200),
        "LOOP_INTERVAL_SECONDS": _to_int(merged["LOOP_INTERVAL_SECONDS"], 60),
        "DRY_RUN": _to_bool(merged["DRY_RUN"], True),
        "GEMINI_API_KEY": str(merged["GEMINI_API_KEY"] or ""),
        "GEMINI_MODEL": str(merged["GEMINI_MODEL"] or "gemini-1.5-flash"),
        "AUTO_START_CYCLE": _to_bool(merged["AUTO_START_CYCLE"], False),
        "ENABLE_AI_CONFIRMATION": strategy_config["aiEnabled"],
        "AI_MIN_CONFIDENCE": strategy_config["minConfidence"] / 100.0,
        "RISK_CONFIG": risk_config,
        "STRATEGY_CONFIG": strategy_config,
    }


def get_runtime_settings(force_refresh=False):
    global _cache, _cache_ts
    now = time.time()
    with _lock:
        if not force_refresh and _cache and (now - _cache_ts) <= config.SETTINGS_CACHE_TTL_SECONDS:
            return _cache

        _cache = _normalize(fetch_runtime_settings())
        _cache_ts = now
        return _cache
