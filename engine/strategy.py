"""
Harmesh Strategy Module — Technical analysis strategies.
Default: MACD + RSI combo. Users can add more in strategies/ dir.
"""
import logging
from typing import Optional

import pandas as pd
import numpy as np
import ta

logger = logging.getLogger("harmesh.strategy")


class MACDRSIStrategy:
    """
    MACD + RSI combo strategy.
    Long: MACD crosses above signal line AND RSI > 30 (not overbought)
    Short: MACD crosses below signal line AND RSI < 70 (not oversold)
    """

    def __init__(self, config: dict):
        trading_cfg = config.get("trading", {})
        self.symbols = trading_cfg.get("symbols", ["BTC/USDT"])
        self.timeframe = trading_cfg.get("timeframe", "1h")
        self.slippage = trading_cfg.get("slippage", 0.001)
        self.fee_rate = trading_cfg.get("fee_rate", 0.001)

        # Strategy params
        self.rsi_period = 14
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add MACD, RSI, and ATR indicators to DataFrame."""
        if df.empty or len(df) < self.macd_slow + self.macd_signal:
            return df

        out = df.copy()

        # MACD
        macd = ta.trend.MACD(
            close=out["close"],
            window_slow=self.macd_slow,
            window_fast=self.macd_fast,
            window_sign=self.macd_signal,
        )
        out["macd"] = macd.macd()
        out["macd_signal"] = macd.macd_signal()
        out["macd_diff"] = macd.macd_diff()

        # RSI
        out["rsi"] = ta.momentum.RSIIndicator(
            close=out["close"],
            window=self.rsi_period,
        ).rsi()

        # ATR
        out["atr"] = ta.volatility.AverageTrueRange(
            high=out["high"],
            low=out["low"],
            close=out["close"],
            window=14,
        ).average_true_range()

        return out

    def generate_signal(self, df: pd.DataFrame) -> str:
        """
        Generate trading signal.
        Returns: "long", "short", or "hold"
        """
        df = self.compute_indicators(df)
        if df.empty or len(df) < 2:
            return "hold"

        last = df.iloc[-1]
        prev = df.iloc[-2]

        # Check for NaN indicators
        if pd.isna(last.get("macd_diff")) or pd.isna(last.get("rsi")):
            return "hold"

        macd_bullish = last["macd"] > last["macd_signal"]
        macd_bearish = last["macd"] < last["macd_signal"]
        macd_cross_up = prev["macd_diff"] < 0 and last["macd_diff"] > 0
        macd_cross_down = prev["macd_diff"] > 0 and last["macd_diff"] < 0

        # Long: MACD crossing up + RSI not overbought
        if macd_cross_up and last["rsi"] < self.rsi_overbought:
            logger.info(
                f"LONG signal — MACD cross up, RSI={last['rsi']:.1f}, "
                f"close={last['close']:.2f}"
            )
            return "long"

        # Short: MACD crossing down + RSI not oversold
        if macd_cross_down and last["rsi"] > self.rsi_oversold:
            logger.info(
                f"SHORT signal — MACD cross down, RSI={last['rsi']:.1f}, "
                f"close={last['close']:.2f}"
            )
            return "short"

        return "hold"


class EMACrossoverStrategy:
    """Simple EMA crossover strategy (Golden Cross / Death Cross)."""

    def __init__(self, config: dict):
        trading_cfg = config.get("trading", {})
        self.symbols = trading_cfg.get("symbols", ["BTC/USDT"])
        self.timeframe = trading_cfg.get("timeframe", "1h")
        self.fast_ema = 9
        self.slow_ema = 21

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        out = df.copy()
        out["ema_fast"] = ta.trend.EMAIndicator(
            close=out["close"], window=self.fast_ema
        ).ema_indicator()
        out["ema_slow"] = ta.trend.EMAIndicator(
            close=out["close"], window=self.slow_ema
        ).ema_indicator()
        out["atr"] = ta.volatility.AverageTrueRange(
            high=out["high"], low=out["low"], close=out["close"], window=14
        ).average_true_range()
        return out

    def generate_signal(self, df: pd.DataFrame) -> str:
        df = self.compute_indicators(df)
        if df.empty or len(df) < 2:
            return "hold"
        last = df.iloc[-1]
        prev = df.iloc[-2]
        if pd.isna(last.get("ema_fast")) or pd.isna(last.get("ema_slow")):
            return "hold"
        cross_up = prev["ema_fast"] <= prev["ema_slow"] and last["ema_fast"] > last["ema_slow"]
        cross_down = prev["ema_fast"] >= prev["ema_slow"] and last["ema_fast"] < last["ema_slow"]
        if cross_up:
            return "long"
        if cross_down:
            return "short"
        return "hold"


def get_strategy(name: str, config: dict):
    """Factory: returns strategy instance by name."""
    strategies = {
        "macd_rsi": MACDRSIStrategy,
        "ema_crossover": EMACrossoverStrategy,
    }
    cls = strategies.get(name)
    if cls is None:
        logger.warning(f"Strategy '{name}' not found, falling back to MACD_RSI")
        cls = MACDRSIStrategy
    return cls(config)
