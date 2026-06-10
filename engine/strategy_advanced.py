"""
Harmesh Advanced Strategy Engine
Multi-strategy, multi-timeframe, ML-enhanced signal generation.
Supports: trend following, mean reversion, volatility breakout, ML-based.
"""
import logging
from typing import Optional, Callable
from enum import Enum

import pandas as pd
import numpy as np
import ta

logger = logging.getLogger("harmesh.strategy_advanced")


class StrategyType(Enum):
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    VOLATILITY_BREAKOUT = "volatility_breakout"
    ML_ENHANCED = "ml_enhanced"
    MULTI_TIMEFRAME = "multi_timeframe"


class SignalStrength(Enum):
    STRONG = 3
    MODERATE = 2
    WEAK = 1
    NONE = 0


class AdvancedStrategyEngine:
    """
    Advanced strategy engine with multiple strategy types, regime adaptation,
    multi-timeframe analysis, and ML-based signal enhancement.
    """

    def __init__(self, config: dict):
        self.config = config
        trading_cfg = config.get("trading", {})
        strategy_cfg = config.get("advanced_strategy", {})

        self.symbols = trading_cfg.get("symbols", ["BTC/USDT"])
        self.timeframe = trading_cfg.get("timeframe", "1h")
        self.slippage = trading_cfg.get("slippage", 0.001)
        self.fee_rate = trading_cfg.get("fee_rate", 0.001)

        # Strategy types to use (from config)
        self.active_strategies = strategy_cfg.get("active_strategies", [
            "trend_following", "mean_reversion"
        ])

        # Signal fusion method: "majority", "weighted", "any"
        self.fusion_method = strategy_cfg.get("fusion_method", "weighted")

        # Multi-timeframe config
        self.mtf_enabled = strategy_cfg.get("mtf_enabled", True)
        self.mtf_timeframes = strategy_cfg.get("mtf_timeframes", ["15m", "1h", "4h"])

        # ML enhancement
        self.ml_enabled = strategy_cfg.get("ml_enabled", False)

        # Strategy-specific parameters
        self.trend_params = strategy_cfg.get("trend_params", {
            "ema_fast": 9,
            "ema_slow": 21,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "adx_threshold": 25,
        })

        self.mean_reversion_params = strategy_cfg.get("mean_reversion_params", {
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "bb_period": 20,
            "bb_std": 2.0,
            "mean_reversion_threshold": 0.02,  # 2% from mean
        })

        self.volatility_params = strategy_cfg.get("volatility_params", {
            "bb_breakout_threshold": 2.5,
            "kc_period": 20,
            "kc_multiplier": 2.0,
            "volume_surge_mult": 1.5,
        })

        # ML model (lazy init)
        self._ml_model = None
        self._ml_features = []

        # Optimization: skip indicator recomputation when data is pre-enriched
        self._skip_indicator_computation = False

    def compute_trend_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute trend-following indicators: EMAs, MACD, ADX."""
        out = df.copy()

        # EMAs
        out["ema_9"] = ta.trend.EMAIndicator(
            close=out["close"], window=self.trend_params["ema_fast"]
        ).ema_indicator()
        out["ema_21"] = ta.trend.EMAIndicator(
            close=out["close"], window=self.trend_params["ema_slow"]
        ).ema_indicator()
        out["ema_50"] = ta.trend.EMAIndicator(
            close=out["close"], window=50
        ).ema_indicator()
        out["ema_200"] = ta.trend.EMAIndicator(
            close=out["close"], window=200
        ).ema_indicator()

        # MACD
        macd = ta.trend.MACD(
            close=out["close"],
            window_slow=self.trend_params["macd_slow"],
            window_fast=self.trend_params["macd_fast"],
            window_sign=self.trend_params["macd_signal"],
        )
        out["macd"] = macd.macd()
        out["macd_signal"] = macd.macd_signal()
        out["macd_diff"] = macd.macd_diff()

        # ATR
        out["atr_14"] = ta.volatility.AverageTrueRange(
            high=out["high"], low=out["low"], close=out["close"], window=14
        ).average_true_range()

        return out

    def compute_mean_reversion_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute mean reversion indicators: RSI, Bollinger Bands, Stochastic."""
        out = df.copy()
        params = self.mean_reversion_params

        # RSI
        out["rsi_14"] = ta.momentum.RSIIndicator(
            close=out["close"], window=params["rsi_period"]
        ).rsi()

        # Bollinger Bands
        bb = ta.volatility.BollingerBands(
            close=out["close"],
            window=params["bb_period"],
            window_dev=params["bb_std"],
        )
        out["bb_upper"] = bb.bollinger_hband()
        out["bb_lower"] = bb.bollinger_lband()
        out["bb_middle"] = bb.bollinger_mavg()
        out["bb_width"] = (out["bb_upper"] - out["bb_lower"]) / out["bb_middle"]
        out["bb_position"] = (out["close"] - out["bb_lower"]) / (out["bb_upper"] - out["bb_lower"] + 1e-10)

        # Stochastic Oscillator
        low_14 = out["low"].rolling(14).min()
        high_14 = out["high"].rolling(14).max()
        out["stoch_k"] = 100 * (out["close"] - low_14) / (high_14 - low_14 + 1e-10)
        out["stoch_d"] = out["stoch_k"].rolling(3).mean()

        # Distance from SMA
        out["sma_20"] = out["close"].rolling(20).mean()
        out["price_to_sma_20"] = (out["close"] - out["sma_20"]) / out["sma_20"]

        return out

    def compute_volatility_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute volatility breakout indicators."""
        out = df.copy()
        params = self.volatility_params

        # ATR (independent — computed here so not dependent on compute_trend_indicators)
        out["atr_14"] = ta.volatility.AverageTrueRange(
            high=out["high"], low=out["low"], close=out["close"], window=14
        ).average_true_range()

        # Keltner Channels
        out["kc_middle"] = out["close"].rolling(params["kc_period"]).mean()
        atr_kc = ta.volatility.AverageTrueRange(
            high=out["high"], low=out["low"], close=out["close"],
            window=params["kc_period"]
        ).average_true_range()
        out["kc_upper"] = out["kc_middle"] + atr_kc * params["kc_multiplier"]
        out["kc_lower"] = out["kc_middle"] - atr_kc * params["kc_multiplier"]
        out["kc_width"] = (out["kc_upper"] - out["kc_lower"]) / out["kc_middle"]

        # Volume indicators
        out["volume_sma_20"] = out["volume"].rolling(20).mean()
        out["volume_ratio"] = out["volume"] / (out["volume_sma_20"] + 1e-10)

        # True Range
        out["tr"] = np.maximum(
            out["high"] - out["low"],
            np.maximum(
                np.abs(out["high"] - out["close"].shift(1)),
                np.abs(out["low"] - out["close"].shift(1)),
            ),
        )
        out["atr_pct"] = out["atr_14"] / out["close"]

        return out

    def compute_mtf_signal(self, dfs: dict[str, pd.DataFrame]) -> dict:
        """
        Multi-timeframe signal aggregation.
        Takes a dict of {timeframe: df} and returns consensus signal.
        Higher timeframes have more weight.
        """
        if not dfs:
            return {"signal": "hold", "strength": SignalStrength.NONE, "confidence": 0.0}

        timeframe_weights = {
            "5m": 0.1, "15m": 0.15, "30m": 0.2,
            "1h": 0.25, "2h": 0.3, "4h": 0.35,
            "6h": 0.4, "8h": 0.45, "12h": 0.5,
            "1d": 0.6, "1w": 0.7,
        }

        signals = []
        total_weight = 0.0

        for tf, df in dfs.items():
            if df.empty or len(df) < 50:
                continue

            weight = timeframe_weights.get(tf, 0.2)
            trend_signal = self._generate_trend_signal(df)
            if trend_signal["signal"] != "hold":
                signals.append({
                    "timeframe": tf,
                    "signal": trend_signal["signal"],
                    "weight": weight,
                    "confidence": trend_signal.get("confidence", 0.5),
                })
                total_weight += weight

        if not signals or total_weight == 0:
            return {"signal": "hold", "strength": SignalStrength.NONE, "confidence": 0.0}

        # Weighted vote
        long_weight = sum(s["weight"] * s["confidence"] for s in signals if s["signal"] == "long")
        short_weight = sum(s["weight"] * s["confidence"] for s in signals if s["signal"] == "short")

        net_signal = long_weight - short_weight
        max_possible = total_weight

        if net_signal > max_possible * 0.3:
            signal = "long"
            confidence = abs(net_signal) / max_possible
        elif net_signal < -max_possible * 0.3:
            signal = "short"
            confidence = abs(net_signal) / max_possible
        else:
            signal = "hold"
            confidence = 0.0

        strengths = {
            "long_signal_count": sum(1 for s in signals if s["signal"] == "long"),
            "short_signal_count": sum(1 for s in signals if s["signal"] == "short"),
            "timeframes": [s["timeframe"] for s in signals],
        }

        return {
            "signal": signal,
            "strength": self._confidence_to_strength(confidence),
            "confidence": min(1.0, confidence),
            "details": strengths,
        }

    def _generate_trend_signal(self, df: pd.DataFrame) -> dict:
        """Generate signal from trend-following indicators."""
        if df.empty or len(df) < 50:
            return {"signal": "hold", "confidence": 0.0}

        if not self._skip_indicator_computation:
            df = self.compute_trend_indicators(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]

        if pd.isna(last.get("macd_diff")) or pd.isna(last.get("ema_9")):
            return {"signal": "hold", "confidence": 0.0}

        # EMA alignment (trend direction)
        ema_bullish = last["ema_9"] > last["ema_21"] > last["ema_50"]
        ema_bearish = last["ema_9"] < last["ema_21"] < last["ema_50"]

        # EMA crossover
        ema_cross_up = prev["ema_9"] <= prev["ema_21"] and last["ema_9"] > last["ema_21"]
        ema_cross_down = prev["ema_9"] >= prev["ema_21"] and last["ema_9"] < last["ema_21"]

        # MACD
        macd_bullish = last["macd"] > last["macd_signal"]
        macd_bearish = last["macd"] < last["macd_signal"]
        macd_cross_up = prev["macd_diff"] < 0 and last["macd_diff"] > 0
        macd_cross_down = prev["macd_diff"] > 0 and last["macd_diff"] < 0

        # Price relative to EMA
        above_ema_50 = last["close"] > last["ema_50"]
        below_ema_50 = last["close"] < last["ema_50"]

        # Long signal scoring
        long_score = 0
        if ema_cross_up: long_score += 3
        if ema_bullish: long_score += 2
        if macd_cross_up: long_score += 3
        if macd_bullish: long_score += 1
        if above_ema_50: long_score += 1

        # Short signal scoring
        short_score = 0
        if ema_cross_down: short_score += 3
        if ema_bearish: short_score += 2
        if macd_cross_down: short_score += 3
        if macd_bearish: short_score += 1
        if below_ema_50: short_score += 1

        if long_score >= 4 and long_score > short_score:
            return {"signal": "long", "confidence": min(1.0, long_score / 10)}
        elif short_score >= 4 and short_score > long_score:
            return {"signal": "short", "confidence": min(1.0, short_score / 10)}

        return {"signal": "hold", "confidence": 0.0}

    def _generate_mean_reversion_signal(self, df: pd.DataFrame) -> dict:
        """Generate signal from mean reversion indicators."""
        if df.empty or len(df) < 30:
            return {"signal": "hold", "confidence": 0.0}

        if not self._skip_indicator_computation:
            df = self.compute_mean_reversion_indicators(df)
        last = df.iloc[-1]
        params = self.mean_reversion_params

        if pd.isna(last.get("rsi_14")) or pd.isna(last.get("bb_position")):
            return {"signal": "hold", "confidence": 0.0}

        # Oversold / Overbought
        oversold = last["rsi_14"] < params["rsi_oversold"]
        overbought = last["rsi_14"] > params["rsi_overbought"]

        # Bollinger Band touch
        bb_lower_touch = last["close"] <= last["bb_lower"]
        bb_upper_touch = last["close"] >= last["bb_upper"]

        # Price far from SMA (mean reversion opportunity)
        far_below_sma = last["price_to_sma_20"] < -params["mean_reversion_threshold"]
        far_above_sma = last["price_to_sma_20"] > params["mean_reversion_threshold"]

        # Stochastic extremes
        stoch_oversold = last["stoch_k"] < 20 and last["stoch_d"] < 20
        stoch_overbought = last["stoch_k"] > 80 and last["stoch_d"] > 80

        # Long (price bounced too low)
        long_score = 0
        if oversold and bb_lower_touch: long_score += 4
        elif oversold: long_score += 2
        if bb_lower_touch: long_score += 2
        if far_below_sma: long_score += 2
        if stoch_oversold: long_score += 2

        # Short (price stretched too high)
        short_score = 0
        if overbought and bb_upper_touch: short_score += 4
        elif overbought: short_score += 2
        if bb_upper_touch: short_score += 2
        if far_above_sma: short_score += 2
        if stoch_overbought: short_score += 2

        if long_score >= 4 and long_score > short_score:
            return {"signal": "long", "confidence": min(1.0, long_score / 10)}
        elif short_score >= 4 and short_score > long_score:
            return {"signal": "short", "confidence": min(1.0, short_score / 10)}

        return {"signal": "hold", "confidence": 0.0}

    def _generate_volatility_breakout_signal(self, df: pd.DataFrame) -> dict:
        """Generate signal from volatility breakout indicators."""
        if df.empty or len(df) < 30:
            return {"signal": "hold", "confidence": 0.0}

        if not self._skip_indicator_computation:
            df = self.compute_volatility_indicators(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]

        if pd.isna(last.get("kc_upper")):
            return {"signal": "hold", "confidence": 0.0}

        # Bollinger Band squeeze (low vol -> breakout expected)
        bb_width_mean = df["bb_width"].rolling(50).mean().iloc[-1] if len(df) >= 50 else 0
        bb_squeeze = last["bb_width"] < bb_width_mean * 0.8 if pd.notna(bb_width_mean) and bb_width_mean > 0 else False

        # Breakout above Keltner upper (volatility expansion)
        kc_breakout_up = last["close"] > last["kc_upper"] and prev["close"] <= prev["kc_upper"]
        kc_breakout_down = last["close"] < last["kc_lower"] and prev["close"] >= prev["kc_lower"]

        # Volume surge confirmation
        volume_surge = last["volume_ratio"] > self.volatility_params["volume_surge_mult"]

        # ATR expansion
        atr_sma = last["atr_pct"]
        atr_increasing = atr_sma > df["atr_pct"].rolling(20).mean().iloc[-1] * 1.2 if len(df) >= 20 else False

        long_score = 0
        if kc_breakout_up and volume_surge: long_score += 5
        elif kc_breakout_up: long_score += 3
        if bb_squeeze: long_score += 1
        if atr_increasing: long_score += 1

        short_score = 0
        if kc_breakout_down and volume_surge: short_score += 5
        elif kc_breakout_down: short_score += 3
        if bb_squeeze: short_score += 1
        if atr_increasing: short_score += 1

        if long_score >= 4 and long_score > short_score:
            return {"signal": "long", "confidence": min(1.0, long_score / 8)}
        elif short_score >= 4 and short_score > long_score:
            return {"signal": "short", "confidence": min(1.0, short_score / 8)}

        return {"signal": "hold", "confidence": 0.0}

    def _generate_ml_signal(self, df: pd.DataFrame) -> dict:
        """
        ML-enhanced signal generation.
        Trains on historical patterns if enough data, returns signal probability.
        Falls back to trend signal if ML is not available.
        """
        if not self.ml_enabled:
            return {"signal": "hold", "confidence": 0.0}

        try:
            from sklearn.ensemble import GradientBoostingClassifier
            HAS_SKLEARN = True
        except ImportError:
            logger.warning("scikit-learn not installed. ML signal disabled.")
            return {"signal": "hold", "confidence": 0.0}

        if df.empty or len(df) < 200:
            return {"signal": "hold", "confidence": 0.0}

        # Compute all features
        if not self._skip_indicator_computation:
            df = self.compute_trend_indicators(df)
        if not self._skip_indicator_computation:
            df = self.compute_mean_reversion_indicators(df)
        if not self._skip_indicator_computation:
            df = self.compute_volatility_indicators(df)

        # Feature engineering
        feature_cols = [
            "ema_9", "ema_21", "ema_50", "macd", "macd_signal", "macd_diff",
            "rsi_14", "bb_position", "bb_width", "stoch_k", "stoch_d",
            "kc_width", "volume_ratio", "atr_pct", "price_to_sma_20",
        ]

        valid_features = [c for c in feature_cols if c in df.columns]
        feature_data = df[valid_features].dropna()

        if len(feature_data) < 100:
            return {"signal": "hold", "confidence": 0.0}

        # Create labels: future return > threshold = 1 (long), < -threshold = -1 (short)
        future_returns = df["close"].pct_change(6).shift(-6)  # 6-period forward return
        labels = np.where(future_returns > 0.005, 1, np.where(future_returns < -0.005, -1, 0))
        labels = pd.Series(labels, index=df.index)

        # Align features and labels
        aligned = pd.concat([feature_data, labels.rename("label")], axis=1).dropna()
        if len(aligned) < 100:
            return {"signal": "hold", "confidence": 0.0}

        X = aligned[valid_features].values
        y = aligned["label"].values

        # Train/test split
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        if len(np.unique(y_train)) < 2:
            return {"signal": "hold", "confidence": 0.0}

        # Train model
        model = GradientBoostingClassifier(
            n_estimators=100, max_depth=3, learning_rate=0.1,
            random_state=42
        )
        model.fit(X_train, y_train)

        # Latest prediction
        latest_features = feature_data.iloc[-1:][valid_features].values
        if len(latest_features) == 0:
            return {"signal": "hold", "confidence": 0.0}

        probs = model.predict_proba(latest_features)[0]
        classes = model.classes_

        # Map classes to signals
        prob_dict = dict(zip(classes, probs))
        long_prob = prob_dict.get(1, 0.0)
        short_prob = prob_dict.get(-1, 0.0)
        hold_prob = prob_dict.get(0, 0.0)

        if long_prob > 0.5 and long_prob > short_prob:
            return {"signal": "long", "confidence": long_prob}
        elif short_prob > 0.5 and short_prob > long_prob:
            return {"signal": "short", "confidence": short_prob}

        return {"signal": "hold", "confidence": hold_prob}

    def _confidence_to_strength(self, confidence: float) -> SignalStrength:
        if confidence >= 0.7:
            return SignalStrength.STRONG
        elif confidence >= 0.4:
            return SignalStrength.MODERATE
        elif confidence >= 0.1:
            return SignalStrength.WEAK
        return SignalStrength.NONE

    def compute_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pre-compute all indicators for a DataFrame once."""
        if not self._skip_indicator_computation:
            df = self.compute_trend_indicators(df)
        if not self._skip_indicator_computation:
            df = self.compute_mean_reversion_indicators(df)
        if not self._skip_indicator_computation:
            df = self.compute_volatility_indicators(df)
        return df

    def generate_signal(self, df: pd.DataFrame, regime_info: Optional[dict] = None,
                       mtf_dfs: Optional[dict[str, pd.DataFrame]] = None) -> dict:
        """
        Master signal generator. Combines all active strategies.
        Returns unified signal with confidence.
        """
        if df.empty or len(df) < 30:
            return {"signal": "hold", "strength": SignalStrength.NONE, "confidence": 0.0, "details": {}}

        # Pre-compute all indicators once (each sub-strategy uses the enriched DataFrame)
        if not self._skip_indicator_computation:
            df = self.compute_all_indicators(df)

        # Get regime info
        regime = None
        regime_bias = None
        if regime_info:
            from engine.regime import Regime
            regime = regime_info.get("regime")
            if regime:
                from engine.regime import RegimeDetector
                rd = RegimeDetector(self.config)
                regime_bias = rd.get_trade_direction_bias(regime)

        # Multi-timeframe signal (if enabled and data provided)
        if self.mtf_enabled and mtf_dfs and len(mtf_dfs) > 0:
            mtf_result = self.compute_mtf_signal(mtf_dfs)
            if mtf_result["signal"] != "hold" and mtf_result["confidence"] > 0.5:
                # MTF overrides short-term signals when confident
                return mtf_result

        # Generate signals from each active strategy
        strategy_signals = {}
        for strategy_name in self.active_strategies:
            if strategy_name == "trend_following":
                sig = self._generate_trend_signal(df)
            elif strategy_name == "mean_reversion":
                sig = self._generate_mean_reversion_signal(df)
            elif strategy_name == "volatility_breakout":
                sig = self._generate_volatility_breakout_signal(df)
            elif strategy_name == "ml_enhanced":
                sig = self._generate_ml_signal(df)
            else:
                continue

            strategy_signals[strategy_name] = sig
            logger.debug(f"  {strategy_name} signal: {sig['signal']} (conf={sig['confidence']:.2f})")

        # Apply regime bias
        if regime_bias:
            for name in strategy_signals:
                sig = strategy_signals[name]
                if sig["signal"] == "hold" and regime_bias != "neutral":
                    # Boost the bias direction
                    sig["signal"] = regime_bias
                    sig["confidence"] = 0.3  # Low confidence bias
                elif sig["signal"] != regime_bias and regime_bias != "neutral":
                    # Opposing regime bias reduces confidence
                    sig["confidence"] *= 0.5

        # Fuse signals
        return self._fuse_signals(strategy_signals, regime_info)

    def _fuse_signals(self, strategy_signals: dict, regime_info: Optional[dict] = None) -> dict:
        """Combine multiple strategy signals into one."""
        if not strategy_signals:
            return {"signal": "hold", "strength": SignalStrength.NONE, "confidence": 0.0, "details": {}}

        if self.fusion_method == "any":
            # Any signal triggers (aggressive)
            for name, sig in strategy_signals.items():
                if sig["signal"] != "hold" and sig["confidence"] > 0.3:
                    return sig

        elif self.fusion_method == "majority":
            # Majority vote
            longs = sum(1 for s in strategy_signals.values() if s["signal"] == "long")
            shorts = sum(1 for s in strategy_signals.values() if s["signal"] == "short")
            total_active = sum(1 for s in strategy_signals.values() if s["signal"] != "hold")

            if total_active == 0:
                return {"signal": "hold", "strength": SignalStrength.NONE, "confidence": 0.0, "details": strategy_signals}

            if longs > shorts and longs > total_active / 2:
                avg_conf = np.mean([s["confidence"] for s in strategy_signals.values() if s["signal"] == "long"])
                return {"signal": "long", "strength": self._confidence_to_strength(avg_conf),
                        "confidence": avg_conf, "details": strategy_signals}
            elif shorts > longs and shorts > total_active / 2:
                avg_conf = np.mean([s["confidence"] for s in strategy_signals.values() if s["signal"] == "short"])
                return {"signal": "short", "strength": self._confidence_to_strength(avg_conf),
                        "confidence": avg_conf, "details": strategy_signals}

        elif self.fusion_method == "weighted":
            # Weighted by strategy priority and confidence
            strategy_weights = {
                "trend_following": 1.0,
                "mean_reversion": 0.7,
                "volatility_breakout": 0.8,
                "ml_enhanced": 1.2,
            }

            long_score = 0.0
            short_score = 0.0
            total_weight = 0.0

            for name, sig in strategy_signals.items():
                weight = strategy_weights.get(name, 0.5) * sig["confidence"]
                if sig["signal"] == "long":
                    long_score += weight
                elif sig["signal"] == "short":
                    short_score += weight
                total_weight += weight

            if total_weight == 0:
                return {"signal": "hold", "strength": SignalStrength.NONE, "confidence": 0.0, "details": strategy_signals}

            net = long_score - short_score
            max_possible = total_weight

            if net > max_possible * 0.2:
                confidence = min(1.0, abs(net) / max_possible)
                return {"signal": "long", "strength": self._confidence_to_strength(confidence),
                        "confidence": confidence, "details": strategy_signals}
            elif net < -max_possible * 0.2:
                confidence = min(1.0, abs(net) / max_possible)
                return {"signal": "short", "strength": self._confidence_to_strength(confidence),
                        "confidence": confidence, "details": strategy_signals}

        return {"signal": "hold", "strength": SignalStrength.NONE, "confidence": 0.0, "details": strategy_signals}


def get_advanced_strategy(name: str, config: dict) -> AdvancedStrategyEngine:
    """Factory function for strategy engine."""
    return AdvancedStrategyEngine(config)
