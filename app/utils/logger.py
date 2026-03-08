import logging

from app import config


_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO), format=_LOG_FORMAT)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log(msg: str) -> None:
    get_logger("bot").info(msg)
