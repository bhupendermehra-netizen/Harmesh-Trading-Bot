"""
Backtest-compatible strategy wrapper.
Adapts AdvancedStrategyEngine to the BacktestEngine interface.
Pre-computes indicators once on the full DataFrame for performance.
"""
import pandas as pd
import numpy as np

from engine.strategy_advanced import AdvancedStrategyEngine
from engine.regime import RegimeDetector


class BacktestStrategy:
    """
    Wraps AdvancedStrategyEngine for use with BacktestEngine.
    Pre-computes indicators once and reuses slices for speed.
    """

    def __init__(self, config: dict):
        self.config = config
        self.advanced = AdvancedStrategyEngine(config)
        self.regime = RegimeDetector(config.get("regime", {}))
        self.name = "HarmeshAdvanced"
        self._precomputed = None

    def set_full_data(self, df: pd.DataFrame):
        """Pre-compute all indicators on the full DataFrame once.
        Sets skip flag AFTER pre-computation so strategies use
        pre-computed indicators without recomputing per candle.
        """
        self._precomputed = self.advanced.compute_all_indicators(df.copy())
        self.advanced._skip_indicator_computation = True

    def generate_signal(self, df: pd.DataFrame) -> dict:
        """Generate trading signal from current candle slice."""
        if len(df) < 50:
            return {"signal": "hold", "confidence": 0.0, "reason": "not_enough_data"}

        # Use precomputed data if available (much faster)
        if self._precomputed is not None and len(self._precomputed) >= len(df):
            enriched = self._precomputed.iloc[:len(df)].copy()
        else:
            # Fallback: compute on the fly (slow for backtests)
            enriched = self.advanced.compute_all_indicators(df.copy())

        # Detect regime
        regime_info = self.regime.detect_regime(enriched)

        # Generate signal from advanced engine
        raw = self.advanced.generate_signal(
            df=enriched,
            regime_info=regime_info,
        )

        # Pass raw signal direction through — backtest engine expects "long"/"short"
        signal = raw.get("signal", "hold")
        confidence = raw.get("confidence", 0.0)

        return {
            "signal": signal,
            "confidence": confidence,
            "reason": f"regime={regime_info.get('regime', 'unknown')} fusion={confidence:.2f}",
            "details": raw.get("details", {}),
        }
