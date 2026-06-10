"""
Harmesh Exchange Module — CCXT wrapper
Provides unified market data + order execution for paper/live modes.
"""
import json
import os
import time
import logging
from datetime import datetime
from typing import Optional

import ccxt
import pandas as pd

logger = logging.getLogger("harmesh.exchange")


class ExchangeConnector:
    """Unified exchange interface using CCXT."""

    def __init__(self, config: dict):
        self.cfg = config["exchange"]
        self.sandbox = self.cfg.get("sandbox", True)
        self.exchange_name = self.cfg["name"].lower()
        self.api_key = self.cfg.get("api_key", "")
        self.api_secret = self.cfg.get("api_secret", "")
        self._ccxt: Optional[ccxt.Exchange] = None
        self._connect()

    def _connect(self):
        """Initialize CCXT exchange instance."""
        exchange_class = getattr(ccxt, self.exchange_name)
        exchange_config = {
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
            "options": self.cfg.get("options", {}),
        }
        if self.sandbox:
            exchange_config["options"]["sandboxMode"] = True

        self._ccxt = exchange_class(exchange_config)

        if self.sandbox and hasattr(self._ccxt, "set_sandbox_mode"):
            self._ccxt.set_sandbox_mode(True)

        # Test connection
        try:
            self._ccxt.load_markets()
            logger.info(f"Connected to {self.exchange_name} ({'sandbox' if self.sandbox else 'live'})")
        except Exception as e:
            logger.warning(f"Exchange connection issue: {e} (offline mode)")

    @property
    def exchange(self) -> ccxt.Exchange:
        return self._ccxt

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> pd.DataFrame:
        """Fetch recent OHLCV candles as a DataFrame."""
        try:
            raw = self._ccxt.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            return df
        except Exception as e:
            logger.error(f"Failed to fetch OHLCV for {symbol}: {e}")
            return pd.DataFrame()

    def fetch_ticker(self, symbol: str) -> dict:
        """Fetch current ticker."""
        try:
            return self._ccxt.fetch_ticker(symbol)
        except Exception as e:
            logger.error(f"Failed to fetch ticker for {symbol}: {e}")
            return {}

    def fetch_balance(self) -> dict:
        """Fetch wallet balance (free + used + total)."""
        try:
            return self._ccxt.fetch_balance()
        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            return {"free": {}, "used": {}, "total": {}}

    def create_order(self, symbol: str, order_type: str, side: str,
                     amount: float, price: Optional[float] = None,
                     params: Optional[dict] = None) -> dict:
        """Place a real order on the exchange."""
        try:
            order = self._ccxt.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=amount,
                price=price,
                params=params or {}
            )
            logger.info(f"Order placed: {side} {amount} {symbol} @ {price or 'market'}")
            return order
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return {"status": "error", "error": str(e)}

    def fetch_order(self, id: str, symbol: str) -> dict:
        """Check order status."""
        try:
            return self._ccxt.fetch_order(id, symbol)
        except Exception as e:
            logger.error(f"Failed to fetch order {id}: {e}")
            return {}

    def cancel_order(self, id: str, symbol: str) -> dict:
        """Cancel an open order."""
        try:
            return self._ccxt.cancel_order(id, symbol)
        except Exception as e:
            logger.error(f"Failed to cancel order {id}: {e}")
            return {}

    @staticmethod
    def list_exchanges() -> list:
        return ccxt.exchanges

    def get_precision(self, symbol: str) -> dict:
        """Get trading precision for a symbol."""
        market = self._ccxt.market(symbol)
        return {
            "amount": market["precision"]["amount"],
            "price": market["precision"]["price"],
        }

    def get_min_amount(self, symbol: str) -> float:
        """Get minimum trade amount for a symbol."""
        market = self._ccxt.market(symbol)
        return market["limits"]["amount"]["min"] or 0.0

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get latest close price from last candle."""
        df = self.fetch_ohlcv(symbol, limit=2)
        if not df.empty:
            return float(df["close"].iloc[-1])
        return None
