import requests

from app.utils.logger import get_logger


logger = get_logger("services.telegram")


def send_message(settings, text):
    strategy = settings.get("STRATEGY_CONFIG", {})
    telegram = strategy.get("telegram", {})
    enabled = bool(telegram.get("enabled"))
    token = telegram.get("botToken", "")
    chat_id = telegram.get("chatId", "")
    if not enabled or not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
        response.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("Telegram send failed: %s", exc)
        return False
