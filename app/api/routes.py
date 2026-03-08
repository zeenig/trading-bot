from fastapi import APIRouter

from app.core.runtime_settings import get_runtime_settings
from app.execution.engine import get_engine
from app.storage import db

router = APIRouter()


@router.get("/status")
def status():
    engine = get_engine()
    settings = get_runtime_settings()
    active_symbols = db.fetch_active_symbols()
    return {
        "bot": "running" if engine.running else "idle",
        "mode": settings.get("OKX_MODE"),
        "dry_run": settings.get("DRY_RUN"),
        "active_symbols": active_symbols,
        "last_cycle": engine.last_cycle,
    }


@router.get("/config")
def bot_config():
    settings = get_runtime_settings()
    return {
        "riskConfig": settings.get("RISK_CONFIG", {}),
        "strategyConfig": settings.get("STRATEGY_CONFIG", {}),
        "mode": settings.get("OKX_MODE"),
        "dry_run": settings.get("DRY_RUN"),
    }


@router.post("/cycle/run")
def run_cycle():
    engine = get_engine()
    return engine.run_cycle()


@router.get("/positions")
def positions(limit: int = 50):
    return {"items": db.fetch_positions(limit)}


@router.get("/signals")
def signals(limit: int = 50):
    return {"items": db.fetch_signals(limit)}


@router.get("/trades")
def trades(limit: int = 50):
    return {"items": db.fetch_trades(limit)}


@router.get("/pnl")
def pnl(limit: int = 100):
    trades_data = db.fetch_trades(limit)
    realized = sum(float(item.get("realized_pnl", 0) or 0) for item in trades_data)
    return {"realized_pnl": realized, "trades_count": len(trades_data), "items": db.fetch_pnl(limit)}
