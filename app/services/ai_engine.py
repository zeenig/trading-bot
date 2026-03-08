import json
import re

import requests

from app.utils.logger import get_logger


logger = get_logger("services.ai")


class AIEngine:
    def __init__(self):
        pass

    def _build_prompt(self, strategy_result):
        return (
            "You are a trading risk assistant. Respond in JSON only with keys: "
            "decision (BUY/SELL/HOLD), confidence (0 to 1), rationale.\n"
            f"Strategy signal: {strategy_result.get('signal')}\n"
            f"Trend: {strategy_result.get('trend')}\n"
            f"Price: {strategy_result.get('price')}\n"
            f"RSI: {strategy_result.get('rsi')}\n"
            f"ATR: {strategy_result.get('atr')}\n"
            f"Reasons: {strategy_result.get('reasons')}\n"
        )

    def _extract_json(self, text):
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    def _call_gemini(self, prompt, api_key, model):
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        return self._extract_json(text)

    def evaluate(self, strategy_result, settings):
        enabled = bool(settings.get("ENABLE_AI_CONFIRMATION")) and bool(settings.get("GEMINI_API_KEY"))
        if not enabled:
            return {
                "decision": strategy_result.get("signal", "HOLD"),
                "confidence": 1.0,
                "rationale": "AI confirmation disabled",
            }

        try:
            output = self._call_gemini(
                self._build_prompt(strategy_result),
                api_key=settings.get("GEMINI_API_KEY", ""),
                model=settings.get("GEMINI_MODEL", "gemini-1.5-flash"),
            ) or {}
            decision = str(output.get("decision", "HOLD")).upper()
            confidence = float(output.get("confidence", 0.0))
            rationale = output.get("rationale", "No rationale returned")
            min_conf = float(settings.get("AI_MIN_CONFIDENCE", 0.7))
            if confidence < min_conf:
                decision = "HOLD"
                rationale = f"Confidence below threshold ({confidence:.2f} < {min_conf:.2f})"
            return {"decision": decision, "confidence": confidence, "rationale": rationale}
        except Exception as exc:
            logger.warning("AI confirmation failed: %s", exc)
            return {"decision": "HOLD", "confidence": 0.0, "rationale": "AI failure fallback"}
