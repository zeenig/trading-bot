import os

import uvicorn
from fastapi import FastAPI

from app.api.routes import router
from app.core.runtime_settings import get_runtime_settings
from app.execution.engine import get_engine
from app.utils.logger import get_logger

app = FastAPI(title="AI Trading Bot")
app.include_router(router)
logger = get_logger("main")


@app.on_event("startup")
def startup_event():
    engine = get_engine()
    settings = get_runtime_settings()
    auto_start = bool(settings.get("AUTO_START_CYCLE", False))
    if auto_start and not engine.running:
        from threading import Thread

        worker = Thread(target=engine.run_continuous, daemon=True)
        worker.start()
        logger.info("Background trading loop started on app startup")


@app.on_event("shutdown")
def shutdown_event():
    engine = get_engine()
    if engine.running:
        engine.stop()


@app.get("/health")
def health():
    settings = get_runtime_settings()
    return {"status": "ok", "mode": settings.get("OKX_MODE"), "dry_run": settings.get("DRY_RUN")}


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
