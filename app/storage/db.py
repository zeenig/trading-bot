from collections import deque
from datetime import datetime, timezone

import requests

from app import config
from app.utils.logger import get_logger


logger = get_logger("storage.db")

_memory = {
    "signals": deque(maxlen=500),
    "trades": deque(maxlen=500),
    "positions": deque(maxlen=500),
    "pnl": deque(maxlen=500),
    "cycles": deque(maxlen=500),
}


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


class SupabaseDB:
    def __init__(self, url="", service_role_key=""):
        self.url = (url or "").rstrip("/")
        self.key = service_role_key or ""

    @property
    def enabled(self):
        return bool(self.url and self.key)

    def _headers(self):
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def insert(self, table, data):
        if not self.enabled:
            return None
        try:
            response = requests.post(
                f"{self.url}/rest/v1/{table}",
                headers=self._headers(),
                json=data,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.warning("Supabase insert failed for table=%s: %s", table, exc)
            return None

    def select(self, table, limit=50, order_by="created_at.desc", suppress_errors=False):
        if not self.enabled:
            return []
        try:
            params = {"select": "*", "limit": limit}
            if order_by:
                params["order"] = order_by
            response = requests.get(
                f"{self.url}/rest/v1/{table}",
                headers=self._headers(),
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            if not suppress_errors:
                logger.warning("Supabase select failed for table=%s: %s", table, exc)
            return []


db = SupabaseDB(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)


def _save(table, payload):
    record = {"created_at": _utc_now(), **payload}
    if table in _memory:
        _memory[table].appendleft(record)
    db.insert(table, record)
    return record


def save_signal(data):
    return _save("signals", data)


def save_trade(data):
    return _save("trades", data)


def save_position(data):
    return _save("positions", data)


def save_pnl(data):
    return _save("pnl", data)


def save_cycle(data):
    return _save("cycles", data)


def fetch_signals(limit=50):
    records = db.select("signals", limit=limit)
    if records:
        return records
    return list(_memory["signals"])[:limit]


def fetch_trades(limit=50):
    records = db.select("trades", limit=limit)
    if records:
        return records
    return list(_memory["trades"])[:limit]


def fetch_positions(limit=50):
    records = db.select("positions", limit=limit)
    if records:
        return records
    return list(_memory["positions"])[:limit]


def fetch_pnl(limit=50):
    records = db.select("pnl", limit=limit)
    if records:
        return records
    return list(_memory["pnl"])[:limit]


def fetch_runtime_settings():
    rows = db.select("bot_settings", limit=500, order_by=None, suppress_errors=True)
    if not rows:
        rows = db.select("settings", limit=500, order_by=None, suppress_errors=True)

    output = {}
    for row in rows:
        key = row.get("key") or row.get("name")
        if not key:
            continue
        output[str(key)] = row.get("value")
    return output


def _as_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "active"}


def _parse_symbols(raw):
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    text = str(raw).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    parts = [item.strip().strip("'\"") for item in text.split(",")]
    return [item for item in parts if item]


def fetch_active_symbols():
    rows = db.select("bot_symbols", limit=500, order_by=None, suppress_errors=True)
    active_symbols = []

    for row in rows:
        symbol = (row.get("symbol") or "").strip()
        market_type = str(row.get("market_type") or "").strip().lower()
        is_active = row.get("is_active")
        if not symbol or market_type not in {"spot", "swap"}:
            continue
        if _as_bool(is_active, True):
            active_symbols.append({"symbol": symbol, "market_type": market_type})

    if active_symbols:
        return active_symbols

    # Backward-compatible fallback to bot_settings keys.
    settings_map = fetch_runtime_settings()
    spot_symbols = _parse_symbols(settings_map.get("SPOT_SYMBOLS"))
    swap_symbols = _parse_symbols(settings_map.get("SWAP_SYMBOLS"))
    return [{"symbol": s, "market_type": "spot"} for s in spot_symbols] + [
        {"symbol": s, "market_type": "swap"} for s in swap_symbols
    ]
