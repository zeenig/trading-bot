import os


def _to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# Minimal bootstrap config (keep only what is needed to connect and start service).
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://bltkentshsqvgltjcyvj.supabase.co")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJsdGtlbnRzaHNxdmdsdGpjeXZqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3Mjg3MTY0MywiZXhwIjoyMDg4NDQ3NjQzfQ.Y9SW4TDKqPwP1APxsTZcEnIEap-8WMt8PUs_o2_k6mU")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
SETTINGS_CACHE_TTL_SECONDS = _to_int(os.getenv("SETTINGS_CACHE_TTL_SECONDS"), 20)
