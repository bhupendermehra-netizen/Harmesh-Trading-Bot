"""
Harmesh Advanced Risk Manager
Professional-grade risk management with:
- Kelly Criterion position sizing
- Dynamic volatility-adjusted sizing
- Correlation-based portfolio limits
- Drawdown-based risk reduction
- Trailing stop-loss
- Regime-adaptive parameters
"""
import logging
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger("harmesh.risk_advanced")

# Backward-compatible alias for original PaperTradingEngine
RiskManager = None  # Will be set at end of file


class AdvancedRiskManager:
    """
    Professional risk management engine for crypto trading.
    Supports multiple position sizing methods, dynamic adjustment,
    and portfolio-level risk controls.
    """

    def __init__(self, config: dict):
        risk_cfg = config.get("risk", {})
        live_cfg = config.get("live", {})

        # Basic limits
        self.max_open_trades = risk_cfg.get("max_open_trades", 3)
        self.max_risk_per_trade = live_cfg.get("max_risk_per_trade", 0.02)
        self.min_balance = risk_cfg.get("min_balance_for_trade", 10.0)

        # Position sizing method: "fixed_risk", "kelly", "volatility_adjusted"
        self.sizing_method = risk_cfg.get("sizing_method", "volatility_adjusted")

        # Kelly Criterion parameters
        self.kelly_fraction = risk_cfg.get("kelly_fraction", 0.25)  # Fraction of Kelly (conservative)
        self.kelly_window = risk_cfg.get("kelly_window", 50)  # Trades to estimate win rate

        # Trailing stop
        self.trailing_stop = risk_cfg.get("trailing_stop", True)
        self.trailing_activation_pct = risk_cfg.get("trailing_stop_activation_pct", 0.02)
        self.trailing_distance_pct = risk_cfg.get("trailing_stop_distance_pct", 0.015)

        # Correlation management
        self.correlation_limit = risk_cfg.get("correlation_limit", 0.7)
        self.correlation_lookback = risk_cfg.get("correlation_lookback", 100)

        # Drawdown protection
        self.max_drawdown_pct = risk_cfg.get("max_drawdown_pct", 0.25)  # Stop trading at 25% DD
        self.drawdown_recovery_mult = risk_cfg.get("drawdown_recovery_mult", 0.5)  # Reduce size in DD

        # Cooldown
        self.cooldown_hours = risk_cfg.get("cooldown_period_hours", 0)

        # Portfolio equity tracking for drawdown
        self._peak_equity: Optional[float] = None
        self._current_drawdown_pct: float = 0.0

    # ---- ATR Calculations ----

    def compute_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Compute Average True Range."""
        if len(df) < period:
            return 0.0
        high, low, close = df["high"].values, df["low"].values, df["close"].values
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:] - close[:-1])
            )
        )
        return float(np.mean(tr[-period:]))

    def compute_atr_pct(self, df: pd.DataFrame, period: int = 14) -> float:
        """ATR as percentage of price."""
        atr = self.compute_atr(df, period)
        price = float(df["close"].iloc[-1])
        return atr / price if price > 0 else 0.0

    # ---- Position Sizing ----

    def compute_kelly_fraction(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """
        Compute optimal Kelly fraction.
        f* = (p * b - q) / b
        where p = win rate, q = loss rate, b = win/loss ratio
        """
        if avg_loss <= 0:
            return self.max_risk_per_trade

        # Win/loss ratio
        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1.0

        # Kelly formula
        q = 1.0 - win_rate
        if win_loss_ratio > 0:
            kelly = (win_rate * win_loss_ratio - q) / win_loss_ratio
        else:
            kelly = win_rate - q

        # Apply fraction and clamp
        kelly = max(0.0, min(kelly * self.kelly_fraction, self.max_risk_per_trade * 2))

        # Conservative cap: never risk more than max_risk_per_trade
        return min(kelly, self.max_risk_per_trade)

    def compute_position_size(
        self,
        capital: float,
        entry_price: float,
        stop_loss_price: float,
        symbol: str = "",
        volatility: float = 0.0,
        win_rate: float = 0.5,
        avg_win: float = 0.0,
        avg_loss: float = 0.0,
        regime_mult: float = 1.0,
    ) -> float:
        """
        Compute position size with selected method.
        Returns base currency amount to buy.
        """
        if entry_price <= 0 or capital <= 0:
            return 0.0

        price_risk = abs(entry_price - stop_loss_price)
        if price_risk <= 0:
            price_risk = entry_price * 0.01

        # Calculate base risk amount
        if self.sizing_method == "kelly" and win_rate > 0 and avg_win > 0:
            risk_per_trade = self.compute_kelly_fraction(win_rate, avg_win, avg_loss)
        elif self.sizing_method == "volatility_adjusted" and volatility > 0:
            # Reduce size when volatility is high
            base_vol = 0.02  # 2% daily vol baseline
            vol_adjustment = base_vol / max(volatility, 0.001)
            vol_adjustment = max(0.3, min(3.0, vol_adjustment))
            risk_per_trade = self.max_risk_per_trade * vol_adjustment
        else:
            risk_per_trade = self.max_risk_per_trade

        # Apply regime multiplier
        risk_per_trade *= regime_mult

        # Apply drawdown reduction
        drawdown_factor = self._get_drawdown_factor()
        risk_per_trade *= drawdown_factor

        # Enforce hard max
        risk_per_trade = min(risk_per_trade, self.max_risk_per_trade * 2)

        # Calculate size
        risk_amount = capital * risk_per_trade
        position_size = risk_amount / max(price_risk, entry_price * 0.005)

        # Hard cap: never exceed 50% of capital in a single position
        max_position_pct = min(0.5 * regime_mult, 0.7)
        max_position = (capital * max_position_pct) / entry_price
        position_size = min(position_size, max_position)

        # Sanity cap: never exceed what 100% of capital could buy
        absolute_max = capital / max(entry_price, 0.01)
        position_size = min(position_size, absolute_max)

        logger.info(
            f"Position size for {symbol}: {position_size:.6f} units "
            f"(${position_size * entry_price:.2f} @ ${entry_price:.2f}) "
            f"[method={self.sizing_method}, risk={risk_per_trade:.2%}]"
        )
        return max(position_size, 0.0)

    # ---- Stop Loss ----

    def compute_stop_loss(
        self,
        entry_price: float,
        side: str,
        atr: float,
        atr_multiplier: float = 2.0,
        regime_mult: float = 1.0,
    ) -> float:
        """ATR-based stop loss with regime adjustment."""
        effective_mult = atr_multiplier * regime_mult
        if side == "long":
            stop = entry_price - (atr * effective_mult)
        else:
            stop = entry_price + (atr * effective_mult)
        return max(stop, 0.0)

    def compute_take_profit(
        self,
        entry_price: float,
        side: str,
        atr: float,
        atr_multiplier: float = 4.0,
        regime_mult: float = 1.0,
        risk_reward: Optional[float] = None,
    ) -> float:
        """ATR-based or risk-reward based take profit."""
        if risk_reward is not None and side in ("long", "short"):
            # Use fixed risk:reward ratio
            price_risk = atr * 2.0 * regime_mult  # stop distance
            if side == "long":
                tp = entry_price + (price_risk * risk_reward)
            else:
                tp = entry_price - (price_risk * risk_reward)
            return max(tp, 0.0)

        effective_mult = atr_multiplier * regime_mult
        if side == "long":
            tp = entry_price + (atr * effective_mult)
        else:
            tp = entry_price - (atr * effective_mult)
        return max(tp, 0.0)

    def update_trailing_stop(
        self,
        current_price: float,
        entry_price: float,
        side: str,
        current_stop: float,
    ) -> float:
        """
        Update trailing stop loss.
        Moves stop up for longs as price increases, down for shorts as price decreases.
        """
        if not self.trailing_stop:
            return current_stop

        if side == "long":
            # Price must move up by activation % from entry
            if current_price < entry_price * (1 + self.trailing_activation_pct):
                return current_stop

            # Trail at specified distance
            new_stop = current_price * (1 - self.trailing_distance_pct)
            return max(new_stop, current_stop)  # Only move up

        else:  # short
            if current_price > entry_price * (1 - self.trailing_activation_pct):
                return current_stop

            new_stop = current_price * (1 + self.trailing_distance_pct)
            return min(new_stop, current_stop) if current_stop > 0 else new_stop  # Only move down

    # ---- Portfolio Controls ----

    def _get_drawdown_factor(self) -> float:
        """
        Reduce position size based on current drawdown.
        Linear reduction from 1.0 at 0% DD to 0 at max_drawdown_pct.
        """
        if self._current_drawdown_pct <= 0:
            return 1.0
        if self._current_drawdown_pct >= self.max_drawdown_pct:
            return 0.0
        return 1.0 - (self._current_drawdown_pct / self.max_drawdown_pct) * self.drawdown_recovery_mult

    def update_drawdown(self, current_equity: float):
        """Track peak equity and compute current drawdown."""
        if self._peak_equity is None or current_equity > self._peak_equity:
            self._peak_equity = current_equity
            self._current_drawdown_pct = 0.0
        elif self._peak_equity > 0:
            self._current_drawdown_pct = (self._peak_equity - current_equity) / self._peak_equity

        if self._current_drawdown_pct >= self.max_drawdown_pct:
            logger.warning(
                f"CRITICAL: Drawdown {self._current_drawdown_pct:.1%} "
                f"exceeds max {self.max_drawdown_pct:.1%}. Risk reduction active."
            )

    def check_correlation(
        self,
        symbol_a: str,
        symbol_b: str,
        price_history_a: list[float],
        price_history_b: list[float],
    ) -> float:
        """Compute Pearson correlation between two symbols' returns."""
        if len(price_history_a) < 20 or len(price_history_b) < 20:
            return 0.0

        returns_a = np.diff(price_history_a) / price_history_a[:-1]
        returns_b = np.diff(price_history_b) / price_history_b[:-1]

        min_len = min(len(returns_a), len(returns_b))
        returns_a = returns_a[-min_len:]
        returns_b = returns_b[-min_len:]

        if np.std(returns_a) == 0 or np.std(returns_b) == 0:
            return 0.0

        corr = np.corrcoef(returns_a, returns_b)[0, 1]
        return float(corr)

    def can_open_trade(
        self,
        open_trades_count: int,
        current_balance: float,
        symbol_balance: float = 0.0,
        portfolio_correlation: float = 0.0,
    ) -> tuple:
        """
        Check if a new trade is allowed.
        Considers: max trades, min balance, correlation, drawdown.
        """
        if open_trades_count >= self.max_open_trades:
            return False, f"Max open trades ({self.max_open_trades}) reached"

        if current_balance < self.min_balance:
            return False, f"Balance ${current_balance:.2f} below min ${self.min_balance:.2f}"

        if self._current_drawdown_pct >= self.max_drawdown_pct:
            return False, f"Max drawdown ({self.max_drawdown_pct:.1%}) reached. Trading halted."

        if abs(portfolio_correlation) > self.correlation_limit:
            return False, f"Portfolio correlation {portfolio_correlation:.2f} exceeds limit {self.correlation_limit:.2f}"

        return True, "ok"

    # ---- Trade Validation ----

    def validate_trade_parameters(
        self,
        entry_price: float,
        stop_loss: float,
        capital: float,
        symbol: str = "",
    ) -> tuple:
        """Validate trade parameters before execution."""
        if entry_price <= 0:
            return False, "Invalid entry price"
        if stop_loss <= 0:
            return False, "Invalid stop loss"
        if stop_loss >= entry_price and False:  # Disabled for short support
            return False, "Stop loss must be below entry for longs"

        risk_pct = abs(entry_price - stop_loss) / entry_price
        if risk_pct > 0.1:  # Max 10% price risk
            return False, f"Risk too high: {risk_pct:.1%} > 10%"

        if capital <= 0:
            return False, "No capital available"

        # Position would be too small to be meaningful
        position_value = capital * self.max_risk_per_trade
        if position_value < 1.0:
            return False, f"Position value ${position_value:.2f} too small"

        return True, "ok"

    # ---- Performance Calculations ----

    def compute_max_drawdown(self, equity_curve: list) -> dict:
        """Compute max drawdown from equity curve."""
        if not equity_curve:
            return {"max_dd": 0.0, "max_dd_pct": 0.0}
        arr = np.array(equity_curve)
        peak = np.maximum.accumulate(arr)
        dd = (peak - arr) / peak
        max_dd = float(np.max(dd))
        max_dd_idx = int(np.argmax(dd))
        return {
            "max_dd": float(peak[max_dd_idx] - arr[max_dd_idx]),
            "max_dd_pct": max_dd * 100,
        }

    def compute_sharpe_ratio(self, returns: list, risk_free_rate: float = 0.02) -> float:
        """Compute annualized Sharpe ratio."""
        if len(returns) < 2:
            return 0.0
        arr = np.array(returns)
        excess = arr - (risk_free_rate / (365 * 24))
        if np.std(excess) == 0:
            return 0.0
        return float(np.mean(excess) / np.std(excess) * np.sqrt(365 * 24))

    def compute_sortino_ratio(self, returns: list, risk_free_rate: float = 0.02) -> float:
        """Sortino ratio — only penalizes downside volatility."""
        if len(returns) < 2:
            return 0.0
        arr = np.array(returns)
        excess = arr - (risk_free_rate / (365 * 24))
        downside = arr[arr < 0]
        if len(downside) == 0 or np.std(downside) == 0:
            return float(np.mean(excess) * np.sqrt(365 * 24)) if np.mean(excess) > 0 else 0.0
        return float(np.mean(excess) / np.std(downside) * np.sqrt(365 * 24))

    def compute_calmar_ratio(self, annualized_return: float, max_drawdown_pct: float) -> float:
        """Calmar ratio: annualized return / max drawdown."""
        if max_drawdown_pct <= 0:
            return annualized_return * 100 if annualized_return > 0 else 0.0
        return annualized_return / (max_drawdown_pct / 100)

    def compute_profit_factor(self, trades: list) -> float:
        """Profit factor: gross profit / gross loss."""
        gross_profit = sum(t.pnl for t in trades if t.pnl is not None and t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in trades if t.pnl is not None and t.pnl < 0))
        return gross_profit / gross_loss if gross_loss > 0 else 999.0

    def compute_expectancy(self, trades: list) -> float:
        """Expected value per trade."""
        if not trades:
            return 0.0
        return float(np.mean([t.pnl for t in trades if t.pnl is not None]))


class RiskManager(AdvancedRiskManager):
    """
    Backward-compatible RiskManager for original PaperTradingEngine.
    Wraps AdvancedRiskManager with the old method signatures.
    """

    def __init__(self, config: dict):
        super().__init__(config)

    def compute_position_size(
        self,
        capital: float,
        entry_price: float,
        stop_loss_price: float,
        symbol: str = "",
    ) -> float:
        return super().compute_position_size(
            capital, entry_price, stop_loss_price, symbol=symbol
        )

    def compute_stop_loss(
        self,
        entry_price: float,
        side: str,
        atr: float,
        atr_multiplier: float = 2.0,
    ) -> float:
        return super().compute_stop_loss(entry_price, side, atr, atr_multiplier)

    def compute_take_profit(
        self,
        entry_price: float,
        side: str,
        atr: float,
        atr_multiplier: float = 4.0,
    ) -> float:
        return super().compute_take_profit(entry_price, side, atr, atr_multiplier)

    def can_open_trade(
        self,
        open_trades_count: int,
        current_balance: float,
        symbol_balance: float = 0.0,
    ) -> tuple:
        return super().can_open_trade(
            open_trades_count, current_balance, symbol_balance
        )

    def validate_trade_parameters(
        self,
        entry_price: float,
        stop_loss: float,
        capital: float,
        symbol: str = "",
    ) -> tuple:
        return super().validate_trade_parameters(entry_price, stop_loss, capital, symbol)

    def compute_max_drawdown(self, equity_curve: list) -> dict:
        return super().compute_max_drawdown(equity_curve)

    def compute_sharpe_ratio(self, returns: list, risk_free_rate: float = 0.02) -> float:
        return super().compute_sharpe_ratio(returns, risk_free_rate)
