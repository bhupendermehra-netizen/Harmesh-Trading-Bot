"""
Harmesh Market Regime Detector
Detects market regimes: trending, ranging, volatile, calm
Uses volatility clustering, ADX, and statistical tests.
Switches strategy behavior based on detected regime.
"""
import logging
from typing import Optional
from enum import Enum

import pandas as pd
import numpy as np

logger = logging.getLogger("harmesh.regime")


class Regime(Enum):
    STRONG_TREND_UP = "strong_trend_up"
    STRONG_TREND_DOWN = "strong_trend_down"
    WEAK_TREND_UP = "weak_trend_up"
    WEAK_TREND_DOWN = "weak_trend_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"


class RegimeDetector:
    """
    Multi-method market regime detector.
    Combines ADX trend strength, volatility percentile, and linear regression slope.
    """

    def __init__(self, config: Optional[dict] = None):
        cfg = config or {}
        regime_cfg = cfg.get("regime", {})

        # ADX thresholds
        self.adx_trend_threshold = regime_cfg.get("adx_trend_threshold", 25)
        self.adx_strong_trend = regime_cfg.get("adx_strong_trend", 35)

        # Volatility thresholds (percentile-based)
        self.vol_lookback = regime_cfg.get("vol_lookback", 100)
        self.vol_high_percentile = regime_cfg.get("vol_high_percentile", 80)
        self.vol_low_percentile = regime_cfg.get("vol_low_percentile", 20)

        # Trend strength via linear regression
        self.trend_lookback = regime_cfg.get("trend_lookback", 50)
        self.trend_slope_threshold = regime_cfg.get("trend_slope_threshold", 0.0001)

        # Price deviation from SMA for ranging detection
        self.ranging_deviation = regime_cfg.get("ranging_deviation", 0.03)  # 3%

        # Cache for volatility history
        self._volatility_history: list[float] = []

    def compute_adx(self, df: pd.DataFrame, period: int = 14) -> float:
        """Compute Average Directional Index (ADX)."""
        if len(df) < period + 1:
            return 0.0

        high = df["high"].values
        low = df["low"].values
        close = df["close"].values

        # True range
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:] - close[:-1])
            )
        )

        # Directional movements
        up_move = high[1:] - high[:-1]
        down_move = low[:-1] - low[1:]

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        # Smoothed averages
        def ema(arr: np.ndarray, window: int) -> np.ndarray:
            result = np.zeros_like(arr, dtype=float)
            result[0] = np.mean(arr[:window]) if len(arr) >= window else arr[0]
            alpha = 2.0 / (window + 1)
            for i in range(1, len(arr)):
                result[i] = (arr[i] * alpha) + (result[i - 1] * (1 - alpha))
            return result

        atr = ema(tr, period)
        plus_di = ema(plus_dm, period) / atr * 100
        minus_di = ema(minus_dm, period) / atr * 100

        dx = np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10) * 100
        adx = ema(dx, period)

        return float(adx[-1]) if len(adx) > 0 else 0.0

    def detect_regime(self, df: pd.DataFrame) -> dict:
        """
        Detect market regime from OHLCV data.
        Returns dict with regime info.
        """
        if df.empty or len(df) < 50:
            return {"regime": Regime.RANGING, "confidence": 0.0, "details": {}}

        close = df["close"].values
        high = df["high"].values
        low = df["low"].values

        # 1. ADX for trend strength
        adx = self.compute_adx(df)

        # 2. Trend direction via linear regression slope
        x = np.arange(min(len(close), self.trend_lookback))
        y = close[-len(x):]
        if len(x) > 1:
            slope = np.polyfit(x, y, 1)[0]
            normalized_slope = slope / (np.mean(y) + 1e-10)
        else:
            normalized_slope = 0.0

        # 3. Volatility (ATR / Price)
        atr = np.mean(
            np.maximum(
                high[-14:] - low[-14:],
                np.maximum(
                    np.abs(high[-14:] - close[-15:-1] if len(close) > 15 else high[-14:] - close[-14:]),
                    np.abs(low[-14:] - close[-15:-1] if len(close) > 15 else low[-14:] - close[-14:])
                )
            )
        )
        current_vol = atr / (np.mean(close[-14:]) + 1e-10)

        # Update volatility history
        self._volatility_history.append(current_vol)
        if len(self._volatility_history) > self.vol_lookback:
            self._volatility_history = self._volatility_history[-self.vol_lookback:]

        # Volatility percentile
        if len(self._volatility_history) >= 20:
            vol_percentile = sum(1 for v in self._volatility_history if v <= current_vol) / len(self._volatility_history) * 100
        else:
            vol_percentile = 50.0

        # 4. Price deviation from SMA for ranging detection
        sma_50 = np.mean(close[-50:]) if len(close) >= 50 else np.mean(close)
        deviation = abs(close[-1] - sma_50) / (sma_50 + 1e-10)

        # Determine regime
        is_high_vol = vol_percentile > self.vol_high_percentile
        is_low_vol = vol_percentile < self.vol_low_percentile
        is_trending = adx > self.adx_trend_threshold
        is_strong_trend = adx > self.adx_strong_trend
        is_up = normalized_slope > self.trend_slope_threshold
        is_down = normalized_slope < -self.trend_slope_threshold
        is_ranging = deviation < self.ranging_deviation and not is_trending

        if is_strong_trend and is_up:
            regime = Regime.STRONG_TREND_UP
        elif is_strong_trend and is_down:
            regime = Regime.STRONG_TREND_DOWN
        elif is_trending and is_up:
            regime = Regime.WEAK_TREND_UP
        elif is_trending and is_down:
            regime = Regime.WEAK_TREND_DOWN
        elif is_high_vol:
            regime = Regime.HIGH_VOLATILITY
        elif is_low_vol:
            regime = Regime.LOW_VOLATILITY
        else:
            regime = Regime.RANGING

        # Build confidence score
        confidence = min(1.0, (abs(normalized_slope) * 1000) + (adx / 50) * 0.5)
        confidence = min(1.0, max(0.0, confidence))

        return {
            "regime": regime,
            "confidence": confidence,
            "details": {
                "adx": round(adx, 2),
                "normalized_slope": round(normalized_slope, 6),
                "volatility": round(current_vol, 6),
                "vol_percentile": round(vol_percentile, 1),
                "deviation_from_sma": round(deviation, 4),
            },
        }

    def get_preferred_strategy(self, regime: Regime) -> str:
        """Map regime to best-suited strategy."""
        regime_strategy_map = {
            Regime.STRONG_TREND_UP: "trend_following",
            Regime.STRONG_TREND_DOWN: "trend_following",
            Regime.WEAK_TREND_UP: "trend_following",
            Regime.WEAK_TREND_DOWN: "trend_following",
            Regime.RANGING: "mean_reversion",
            Regime.HIGH_VOLATILITY: "volatility_breakout",
            Regime.LOW_VOLATILITY: "ranging",
        }
        return regime_strategy_map.get(regime, "trend_following")

    def get_regime_params(self, regime: Regime) -> dict:
        """
        Get risk/strategy parameter adjustments based on regime.
        Returns multipliers for position size, stop loss, take profit.
        """
        params = {
            Regime.STRONG_TREND_UP: {
                "position_size_mult": 1.5,
                "stop_loss_mult": 1.2,
                "take_profit_mult": 1.5,
                "max_trades_mult": 1.0,
                "bias": "long",
            },
            Regime.STRONG_TREND_DOWN: {
                "position_size_mult": 1.3,
                "stop_loss_mult": 1.2,
                "take_profit_mult": 1.5,
                "max_trades_mult": 1.0,
                "bias": "short",
            },
            Regime.WEAK_TREND_UP: {
                "position_size_mult": 1.0,
                "stop_loss_mult": 1.0,
                "take_profit_mult": 1.0,
                "max_trades_mult": 1.0,
                "bias": "long",
            },
            Regime.WEAK_TREND_DOWN: {
                "position_size_mult": 0.8,
                "stop_loss_mult": 1.0,
                "take_profit_mult": 1.0,
                "max_trades_mult": 0.8,
                "bias": "short",
            },
            Regime.RANGING: {
                "position_size_mult": 0.6,
                "stop_loss_mult": 0.8,
                "take_profit_mult": 0.6,
                "max_trades_mult": 0.7,
                "bias": "neutral",
            },
            Regime.HIGH_VOLATILITY: {
                "position_size_mult": 0.5,
                "stop_loss_mult": 1.5,
                "take_profit_mult": 1.2,
                "max_trades_mult": 0.5,
                "bias": "neutral",
            },
            Regime.LOW_VOLATILITY: {
                "position_size_mult": 0.7,
                "stop_loss_mult": 0.8,
                "take_profit_mult": 0.7,
                "max_trades_mult": 0.8,
                "bias": "neutral",
            },
        }
        return params.get(regime, {
            "position_size_mult": 1.0,
            "stop_loss_mult": 1.0,
            "take_profit_mult": 1.0,
            "max_trades_mult": 1.0,
            "bias": "neutral",
        })

    def get_trade_direction_bias(self, regime: Regime) -> Optional[str]:
        """Return preferred trade direction based on regime, or None if neutral."""
        params = self.get_regime_params(regime)
        bias = params.get("bias", "neutral")
        return None if bias == "neutral" else bias
