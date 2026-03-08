import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests


class OKXClient:
    def __init__(self, api_key="", secret_key="", passphrase="", mode="testnet", timeout=15):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.mode = mode
        self.timeout = timeout
        self.base_url = "https://www.okx.com"

    def _can_auth(self):
        return bool(self.api_key and self.secret_key and self.passphrase)

    def _timestamp(self):
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def _sign(self, timestamp, method, request_path, body=""):
        message = f"{timestamp}{method.upper()}{request_path}{body}"
        mac = hmac.new(self.secret_key.encode("utf-8"), message.encode("utf-8"), digestmod=hashlib.sha256)
        return base64.b64encode(mac.digest()).decode()

    def _request(self, method, path, params=None, body=None, auth=False):
        query_string = f"?{urlencode(params)}" if params else ""
        request_path = f"{path}{query_string}"
        body_str = json.dumps(body) if body else ""

        headers = {"Content-Type": "application/json"}
        if self.mode == "testnet":
            headers["x-simulated-trading"] = "1"

        if auth:
            if not self._can_auth():
                raise ValueError("OKX credentials are required for authenticated endpoints")
            ts = self._timestamp()
            headers.update(
                {
                    "OK-ACCESS-KEY": self.api_key,
                    "OK-ACCESS-SIGN": self._sign(ts, method, request_path, body_str),
                    "OK-ACCESS-TIMESTAMP": ts,
                    "OK-ACCESS-PASSPHRASE": self.passphrase,
                }
            )

        response = requests.request(
            method=method.upper(),
            url=f"{self.base_url}{request_path}",
            headers=headers,
            data=body_str if body else None,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("code") not in (None, "0"):
            raise RuntimeError(f"OKX API error: {payload.get('msg', 'unknown error')}")
        return payload

    # Public
    def get_candles(self, inst_id, bar="1m", limit=100):
        return self._request(
            "GET",
            "/api/v5/market/candles",
            params={"instId": inst_id, "bar": bar, "limit": limit},
            auth=False,
        )

    def get_ticker(self, inst_id):
        return self._request("GET", "/api/v5/market/ticker", params={"instId": inst_id}, auth=False)

    # Private
    def get_balance(self, ccy="USDT"):
        return self._request("GET", "/api/v5/account/balance", params={"ccy": ccy}, auth=True)

    def get_positions(self, inst_type="SWAP"):
        return self._request("GET", "/api/v5/account/positions", params={"instType": inst_type}, auth=True)

    def place_spot_order(self, inst_id, side, size, order_type="market"):
        return self._request(
            "POST",
            "/api/v5/trade/order",
            body={
                "instId": inst_id,
                "tdMode": "cash",
                "side": side.lower(),
                "ordType": order_type,
                "sz": str(size),
            },
            auth=True,
        )

    def place_swap_order(self, inst_id, side, size, order_type="market", td_mode="cross"):
        return self._request(
            "POST",
            "/api/v5/trade/order",
            body={
                "instId": inst_id,
                "tdMode": td_mode,
                "side": side.lower(),
                "ordType": order_type,
                "sz": str(size),
            },
            auth=True,
        )

    def close_position(self, inst_id, mgn_mode="cross"):
        return self._request(
            "POST",
            "/api/v5/trade/close-position",
            body={"instId": inst_id, "mgnMode": mgn_mode},
            auth=True,
        )
