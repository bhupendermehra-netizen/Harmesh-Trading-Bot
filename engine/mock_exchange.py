"""
Harmesh Mock Exchange — Generates realistic simulated market data for demo/testing.
Provides trending OHLCV data with realistic volatility so the paper trader works.
"""
import logging
import math
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger("harmesh.mock")


class MockExchange:
    """Simulated exchange that generates realistic OHLCV data using random walk."""

    def __init__(self, config: dict):
        trading_cfg = config.get("trading", {})
        self.symbols = trading_cfg.get("symbols", ["BTC/USDT", "ETH/USDT"])
        self._prices = {}
        self._seeds = {}
        self._tick = 0

        # Initialize price seeds for each symbol (realistic base prices)
        base_prices = {
            "BTC/USDT": 65000.0,
            "ETH/USDT": 3500.0,
            "SOL/USDT": 145.0,
            "BNB/USDT": 580.0,
            "XRP/USDT": 0.55,
            "ADA/USDT": 0.45,
            "DOGE/USDT": 0.12,
            "DOT/USDT": 7.50,
            "AVAX/USDT": 35.0,
            "LINK/USDT": 14.0,
        }
        for sym in self.symbols:
            self._prices[sym] = base_prices.get(sym, 100.0)
            self._seeds[sym] = {
                "trend": random.uniform(-0.0002, 0.0002),  # slight trend per tick
                "volatility": random.uniform(0.002, 0.008),  # tick volatility
                "phase": random.uniform(0, 2 * math.pi),
            }

        logger.info(f"MockExchange ready for {len(self.symbols)} symbols")

    def _generate_ohlcv(self, symbol: str, limit: int = 100) -> pd.DataFrame:
        """Generate realistic OHLCV data with trend, noise, and intra-candle volatility."""
        seed = self._seeds[symbol]
        price = self._prices[symbol]
        now = datetime.now()

        closes = []
        for i in range(limit):
            t = now - timedelta(hours=limit - i)
            # Random walk with trend + cyclical component
            cycle = math.sin(seed["phase"] + i * 0.1) * price * 0.02
            noise = np.random.randn() * price * seed["volatility"]
            trend = price * seed["trend"]
            price += trend + noise * 0.3
            price += cycle * 0.01

            # Mean reversion (don't drift too far)
            reversion = (self._prices[symbol] - price) * 0.001
            price += reversion

            # Ensure positive
            price = max(price, price * 0.1)
            closes.append(price)

        closes = np.array(closes)

        # Generate OHLC from close
        df = pd.DataFrame({
            "timestamp": pd.date_range(end=now, periods=limit, freq="1h"),
            "open": closes * (1 + np.random.randn(limit) * 0.002),
            "high": closes * (1 + np.abs(np.random.randn(limit)) * 0.008),
            "low": closes * (1 - np.abs(np.random.randn(limit)) * 0.008),
            "close": closes,
            "volume": np.random.uniform(100, 10000, limit),
        })
        df.set_index("timestamp", inplace=True)

        # Ensure high >= open >= low etc
        for idx in df.index:
            row = df.loc[idx]
            vals = sorted([row["open"], row["close"]])
            df.at[idx, "low"] = min(vals[0], row["low"])
            df.at[idx, "high"] = max(vals[1], row["high"])

        # Update stored price to latest close
        self._prices[symbol] = float(closes[-1])

        return df

    def get_current_price(self, symbol: str) -> float:
        """Return latest simulated price."""
        return self._prices.get(symbol, 100.0)

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> pd.DataFrame:
        """Generate and return simulated OHLCV data."""
        # Update tick counter
        self._tick += 1

        # Every 10 ticks, shift trend slightly for regime changes
        if self._tick % 10 == 0:
            for sym in self.symbols:
                self._seeds[sym]["trend"] += random.uniform(-0.0003, 0.0003)
                self._seeds[sym]["trend"] = max(-0.001, min(0.001, self._seeds[sym]["trend"]))

        return self._generate_ohlcv(symbol, limit)

    def get_precision(self, symbol: str) -> dict:
        """Return mock precision values."""
        return {"amount": 6, "price": 2}

    def get_min_amount(self, symbol: str) -> float:
        return 0.0001

    def fetch_balance(self) -> dict:
        return {"free": {"USDT": 1000.0}, "used": {}, "total": {"USDT": 1000.0}}

    def fetch_ticker(self, symbol: str) -> dict:
        return {"last": self._prices.get(symbol, 100.0), "symbol": symbol}

    def create_order(self, symbol: str, order_type: str, side: str,
                     amount: float, price=None, params=None) -> dict:
        logger.info(f"Mock order: {side} {amount} {symbol} ({order_type})")
        return {"id": "mock_" + str(random.randint(1000, 9999)),
                "status": "closed",
                "symbol": symbol,
                "type": order_type,
                "side": side,
                "amount": amount,
                "price": price or self._prices.get(symbol, 100.0),
                "filled": amount,
                "cost": amount * (price or self._prices.get(symbol, 100.0))}

    def fetch_order(self, id: str, symbol: str) -> dict:
        return {"id": id, "status": "closed", "symbol": symbol}

    def cancel_order(self, id: str, symbol: str) -> dict:
        return {"id": id, "status": "canceled"}
