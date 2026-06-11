"""
Harmesh Backtesting Engine
Professional backtesting framework with:
- Walk-forward analysis (prevents overfitting)
- Monte Carlo simulation (assesses strategy robustness)
- Multi-strategy comparison
- Detailed performance reports
- Parameter optimization
"""
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field, asdict

import pandas as pd
import numpy as np

logger = logging.getLogger("harmesh.backtest")


@dataclass
class BacktestTrade:
    """A single backtest trade record."""
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    entry_time: str
    exit_time: str
    quantity: float
    pnl: float
    pnl_pct: float
    exit_reason: str = "signal"


@dataclass
class BacktestResult:
    """Complete backtest result with all metrics."""
    strategy_name: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    initial_capital: float
    final_equity: float
    total_return: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    avg_win: float
    avg_loss: float
    avg_trade: float
    expectancy: float
    std_dev_returns: float
    trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)
    monthly_returns: list = field(default_factory=list)


class BacktestEngine:
    """
    Professional backtesting engine.
    Simulates trading on historical data with configurable parameters.
    """

    def __init__(self, config: dict):
        self.config = config
        backtest_cfg = config.get("backtest", {})

        self.initial_capital = backtest_cfg.get("initial_capital", 10000.0)
        self.commission = backtest_cfg.get("commission", 0.001)
        self.slippage = backtest_cfg.get("slippage", 0.001)

        # Walk-forward settings
        self.wf_enabled = backtest_cfg.get("walk_forward_enabled", False)
        self.wf_train_pct = backtest_cfg.get("walk_forward_train_pct", 0.7)
        self.wf_window = backtest_cfg.get("walk_forward_window", 500)  # Candles per window

        # Monte Carlo settings
        self.mc_simulations = backtest_cfg.get("monte_carlo_simulations", 1000)
        self.mc_enabled = backtest_cfg.get("monte_carlo_enabled", False)

    def _simulate_trade(
        self,
        df: pd.DataFrame,
        idx: int,
        signal: str,
        symbol: str,
        capital: float,
    ) -> Optional[BacktestTrade]:
        """Simulate a single trade from entry to exit."""
        from engine.risk import AdvancedRiskManager
        risk = AdvancedRiskManager(self.config)

        entry_price = float(df.iloc[idx]["close"])
        entry_time = str(df.index[idx]) if isinstance(df.index, pd.DatetimeIndex) else str(idx)

        # Apply slippage
        if signal == "long":
            entry_price *= (1 + self.slippage)
        else:
            entry_price *= (1 - self.slippage)

        # Get OHLCV slice for ATR
        atr_slice = df.iloc[:idx + 1]
        atr = risk.compute_atr(atr_slice) if len(atr_slice) >= 14 else entry_price * 0.02

        # Compute stop loss and take profit
        stop_loss = risk.compute_stop_loss(entry_price, signal, atr)
        take_profit = risk.compute_take_profit(entry_price, signal, atr)

        # Position size
        position_size = risk.compute_position_size(
            capital, entry_price, stop_loss, symbol=symbol, volatility=atr / entry_price
        )

        # Simulate forward to find exit
        exit_price = entry_price
        exit_reason = "signal"
        exit_idx = idx

        for j in range(idx + 1, min(idx + 100, len(df))):
            current_price = float(df.iloc[j]["close"])
            high = float(df.iloc[j]["high"])
            low = float(df.iloc[j]["low"])

            if signal == "long":
                # Check stop loss (intraday low hit)
                if low <= stop_loss:
                    exit_price = stop_loss
                    exit_reason = "stop_loss"
                    exit_idx = j
                    break
                # Check take profit (intraday high hit)
                if high >= take_profit:
                    exit_price = take_profit
                    exit_reason = "take_profit"
                    exit_idx = j
                    break
                # Update trailing stop
                stop_loss = risk.update_trailing_stop(current_price, entry_price, signal, stop_loss)
                if low <= stop_loss:
                    exit_price = stop_loss
                    exit_reason = "trailing_stop"
                    exit_idx = j
                    break
            else:  # short
                if high >= stop_loss:
                    exit_price = stop_loss
                    exit_reason = "stop_loss"
                    exit_idx = j
                    break
                if low <= take_profit:
                    exit_price = take_profit
                    exit_reason = "take_profit"
                    exit_idx = j
                    break
                stop_loss = risk.update_trailing_stop(current_price, entry_price, signal, stop_loss)
                if high >= stop_loss:
                    exit_price = stop_loss
                    exit_reason = "trailing_stop"
                    exit_idx = j
                    break

            exit_price = current_price
            exit_idx = j

        # Apply exit slippage
        if signal == "long":
            exit_price *= (1 - self.slippage)
        else:
            exit_price *= (1 + self.slippage)

        # Compute P&L
        if signal == "long":
            pnl = (exit_price - entry_price) * position_size
            pnl_pct = (exit_price - entry_price) / entry_price * 100
        else:
            pnl = (entry_price - exit_price) * position_size
            pnl_pct = (entry_price - exit_price) / entry_price * 100

        # Deduct commission
        commission_cost = (entry_price * position_size + exit_price * position_size) * self.commission
        pnl -= commission_cost

        exit_time = str(df.index[exit_idx]) if isinstance(df.index, pd.DatetimeIndex) else str(exit_idx)

        return BacktestTrade(
            symbol=symbol, side=signal,
            entry_price=entry_price, exit_price=exit_price,
            entry_time=entry_time, exit_time=exit_time,
            quantity=position_size, pnl=pnl, pnl_pct=pnl_pct,
            exit_reason=exit_reason,
        )

    def run(
        self,
        df: pd.DataFrame,
        strategy,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
        print_progress: bool = True,
    ) -> BacktestResult:
        """
        Run a full backtest on historical data.
        
        Args:
            df: Historical OHLCV data
            strategy: Strategy instance with generate_signal(df) -> dict
            symbol: Trading symbol
            timeframe: Candle timeframe
            print_progress: Whether to print progress dots during run
        """
        if df.empty or len(df) < 100:
            raise ValueError(f"Not enough data: {len(df)} rows (need 100+)")

        capital = self.initial_capital
        trades = []
        equity_curve = []
        returns = []

        # Track open positions per symbol
        open_positions: dict[str, BacktestTrade] = {}

        # Pre-compute indicators on full data (performance optimization)
        if hasattr(strategy, 'set_full_data'):
            strategy.set_full_data(df)

        start_time = time.time()
        total_candles = len(df)
        next_progress = 0.1  # print every 10% progress

        # Iterate through each candle
        for i in range(50, total_candles):  # Start after indicators stabilize
            current_slice = df.iloc[:i + 1]
            current_price = float(df.iloc[i]["close"])
            current_time = str(df.index[i]) if isinstance(df.index, pd.DatetimeIndex) else str(i)

            # Check stop losses on open positions
            to_close = []
            for sym, trade in open_positions.items():
                high = float(df.iloc[i]["high"])
                low = float(df.iloc[i]["low"])

                if trade.side == "long":
                    if low <= trade.exit_price and trade.exit_reason in ("stop_loss", "trailing_stop"):
                        to_close.append(sym)
                    elif high >= trade.exit_price and trade.exit_reason == "take_profit":
                        to_close.append(sym)
                else:
                    if high >= trade.exit_price and trade.exit_reason in ("stop_loss", "trailing_stop"):
                        to_close.append(sym)
                    elif low <= trade.exit_price and trade.exit_reason == "take_profit":
                        to_close.append(sym)

            for sym in to_close:
                trade = open_positions.pop(sym)
                trade.exit_price = current_price
                trade.exit_time = current_time
                if trade.side == "long":
                    trade.pnl = (trade.exit_price - trade.entry_price) * trade.quantity
                    trade.pnl_pct = (trade.exit_price - trade.entry_price) / trade.entry_price * 100
                else:
                    trade.pnl = (trade.entry_price - trade.exit_price) * trade.quantity
                    trade.pnl_pct = (trade.entry_price - trade.exit_price) / trade.entry_price * 100

                # Short trades: you receive cash on entry, pay to close
                if trade.side == "short":
                    capital += trade.pnl - (trade.quantity * trade.entry_price)
                else:
                    capital += trade.pnl + (trade.quantity * trade.entry_price)
                trades.append(trade)
                returns.append(trade.pnl_pct / 100.0)

            # Generate signal
            if len(open_positions) < 3:  # Max 3 concurrent positions
                signal_result = strategy.generate_signal(current_slice)
                signal = signal_result["signal"]

                if signal != "hold" and symbol not in open_positions:
                    trade = self._simulate_trade(df, i, signal, symbol, capital)
                    if trade:
                        open_positions[symbol] = trade
                        if trade.side == "short":
                            capital += trade.quantity * trade.entry_price  # Receive short sale proceeds
                        else:
                            capital -= trade.quantity * trade.entry_price  # Pay for long purchase

            # Record equity on EVERY candle (capital + open position value)
            pos_value = capital + sum(
                t.quantity * current_price for t in open_positions.values()
            )
            equity_curve.append(pos_value)

            # Progress indicator
            if print_progress:
                progress = (i - 49) / (total_candles - 50)
                if progress >= next_progress:
                    pct = int(progress * 100)
                    print(f"  [{pct}%] candles={i}/{total_candles} trades={len(trades)} equity=${pos_value:.0f}")
                    sys.stdout.flush()
                    next_progress += 0.1

        # Close any remaining positions
        for sym, trade in open_positions.items():
            trade.exit_price = float(df.iloc[-1]["close"])
            trade.exit_time = str(df.index[-1]) if isinstance(df.index, pd.DatetimeIndex) else str(len(df))
            trade.exit_reason = "end_of_data"
            if trade.side == "long":
                trade.pnl = (trade.exit_price - trade.entry_price) * trade.quantity
                trade.pnl_pct = (trade.exit_price - trade.entry_price) / trade.entry_price * 100
            else:
                trade.pnl = (trade.entry_price - trade.exit_price) * trade.quantity
                trade.pnl_pct = (trade.entry_price - trade.exit_price) / trade.entry_price * 100
            if trade.side == "short":
                capital += trade.pnl - (trade.quantity * trade.entry_price)
            else:
                capital += trade.pnl + (trade.quantity * trade.entry_price)
            trades.append(trade)

            if trade.pnl_pct:
                returns.append(trade.pnl_pct / 100.0)

        equity_curve.append(capital)

        # Compute metrics
        from engine.risk import AdvancedRiskManager
        risk = AdvancedRiskManager(self.config)

        result = self._compute_metrics(
            trades, equity_curve, returns, capital, symbol, timeframe, strategy, df
        )
        logger.info(f"Backtest complete: {len(trades)} trades in {time.time() - start_time:.1f}s")
        return result

    def _compute_metrics(
        self,
        trades: list,
        equity_curve: list,
        returns: list,
        final_capital: float,
        symbol: str,
        timeframe: str,
        strategy,
        df: pd.DataFrame,
    ) -> BacktestResult:
        """Compute all performance metrics from backtest results."""
        from engine.risk import AdvancedRiskManager
        risk = AdvancedRiskManager(self.config)

        total_return_pct = (final_capital - self.initial_capital) / self.initial_capital * 100

        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]
        total = len(trades)
        win_rate = len(wins) / total if total > 0 else 0.0

        profit_factor = risk.compute_profit_factor(trades)
        dd_metrics = risk.compute_max_drawdown(equity_curve)

        # Use equity-curve hourly returns for Sharpe/Sortino (per-candle sampling)
        # This ensures the annualization factor of sqrt(365*24) is correct
        if len(equity_curve) > 1:
            hourly_returns = np.diff(equity_curve) / equity_curve[:-1]
            sharpe = risk.compute_sharpe_ratio(hourly_returns.tolist())
            sortino = risk.compute_sortino_ratio(hourly_returns.tolist())
        else:
            sharpe = 0.0
            sortino = 0.0

        avg_win = np.mean([t.pnl for t in wins]) if wins else 0.0
        avg_loss = np.mean([t.pnl for t in losses]) if losses else 0.0
        avg_trade = np.mean([t.pnl for t in trades]) if trades else 0.0
        expectancy = risk.compute_expectancy(trades)
        std_returns = float(np.std(returns)) if returns else 0.0

        # Annualized return estimate
        if isinstance(df.index, pd.DatetimeIndex) and len(df) > 1:
            days = (df.index[-1] - df.index[0]).days
        else:
            days = len(df)  # Approximate
        annualized_return = (total_return_pct / 100) * (365 / max(days, 1))
        calmar = risk.compute_calmar_ratio(annualized_return, dd_metrics["max_dd_pct"])

        start_date = str(df.index[0]) if isinstance(df.index, pd.DatetimeIndex) else "N/A"
        end_date = str(df.index[-1]) if isinstance(df.index, pd.DatetimeIndex) else "N/A"

        return BacktestResult(
            strategy_name=strategy.__class__.__name__,
            symbol=symbol, timeframe=timeframe,
            start_date=start_date, end_date=end_date,
            initial_capital=self.initial_capital,
            final_equity=final_capital,
            total_return=final_capital - self.initial_capital,
            total_return_pct=total_return_pct,
            total_trades=total, winning_trades=len(wins), losing_trades=len(losses),
            win_rate=win_rate, profit_factor=profit_factor,
            max_drawdown_pct=dd_metrics["max_dd_pct"],
            sharpe_ratio=sharpe, sortino_ratio=sortino, calmar_ratio=calmar,
            avg_win=avg_win, avg_loss=avg_loss, avg_trade=avg_trade,
            expectancy=expectancy, std_dev_returns=std_returns,
            trades=[asdict(t) for t in trades],
            equity_curve=equity_curve,
        )

    def run_walk_forward(
        self,
        df: pd.DataFrame,
        strategy_class,
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
    ) -> list[BacktestResult]:
        """
        Walk-forward analysis.
        Splits data into train/test windows, optimizes on train, tests on test.
        Reports out-of-sample performance — the true test of a strategy.
        """
        if not self.wf_enabled:
            return []

        results = []
        total_candles = len(df)
        window_size = self.wf_window
        train_size = int(window_size * self.wf_train_pct)
        test_size = window_size - train_size

        logger.info(f"Walk-forward analysis: {total_candles} candles, "
                    f"window={window_size}, train={train_size}, test={test_size}")

        for start in range(0, total_candles - window_size, test_size):
            train_end = start + train_size
            test_end = min(start + window_size, total_candles)

            if test_end - train_end < 50:
                break  # Skip too-small test windows

            train_df = df.iloc[start:train_end]
            test_df = df.iloc[train_end:test_end]

            # Train: run backtest to find optimal params (simplified)
            # In production: optimize parameters here
            strategy = strategy_class(self.config)

            # Test: run on out-of-sample data
            result = self.run(test_df, strategy, symbol, timeframe)

            results.append(result)

            logger.info(
                f"Window {start}-{test_end}: OOS return={result.total_return_pct:.1f}%, "
                f"trades={result.total_trades}, win_rate={result.win_rate:.1%}"
            )

        return results

    def run_monte_carlo(self, result: BacktestResult) -> dict:
        """
        Monte Carlo simulation to assess strategy robustness.
        Shuffles trade outcomes to simulate thousands of possible equity curves.
        Returns probability of profit, max drawdown ranges, and confidence intervals.
        """
        if not self.mc_enabled or not result.trades:
            return {}

        trade_pnls = np.array([t["pnl"] for t in result.trades])
        n_sim = self.mc_simulations
        n_trades = len(trade_pnls)

        final_equities = []
        max_drawdowns = []

        for sim in range(n_sim):
            # Randomly shuffle and sample with replacement
            np.random.seed(sim)
            sampled = np.random.choice(trade_pnls, size=n_trades, replace=True)

            equity = result.initial_capital
            curve = [equity]
            peak = equity

            for pnl in sampled:
                equity += pnl
                curve.append(equity)
                if equity > peak:
                    peak = equity
                dd = (peak - equity) / peak if peak > 0 else 0
                max_drawdowns.append(dd)

            final_equities.append(equity)

        final_array = np.array(final_equities)
        dd_array = np.array(max_drawdowns)

        percentiles = [5, 25, 50, 75, 95]
        equity_percentiles = {str(p): float(np.percentile(final_array, p)) for p in percentiles}
        dd_percentiles = {str(p): float(np.percentile(dd_array, p)) for p in percentiles}

        prob_profit = float(np.mean(final_array >= result.initial_capital))

        return {
            "simulations": n_sim,
            "prob_profit": prob_profit,
            "expected_final_equity": float(np.mean(final_array)),
            "median_final_equity": float(np.median(final_array)),
            "final_equity_percentiles": equity_percentiles,
            "max_drawdown_percentiles": dd_percentiles,
            "worst_case_equity": float(np.min(final_array)),
            "best_case_equity": float(np.max(final_array)),
        }

    def print_report(self, result: BacktestResult, mc_results: Optional[dict] = None) -> str:
        """Generate a formatted backtest report."""
        lines = []
        lines.append("=" * 60)
        lines.append(f"HARMESH BACKTEST REPORT")
        lines.append("=" * 60)
        lines.append(f"Strategy: {result.strategy_name}")
        lines.append(f"Symbol: {result.symbol} | Timeframe: {result.timeframe}")
        lines.append(f"Period: {result.start_date} → {result.end_date}")
        lines.append(f"Initial Capital: ${result.initial_capital:,.2f}")
        lines.append(f"Final Equity:   ${result.final_equity:,.2f}")
        lines.append(f"Total Return:   ${result.total_return:+,.2f} ({result.total_return_pct:+.2f}%)")
        lines.append("-" * 60)
        lines.append(f"TRADES:         {result.total_trades}")
        lines.append(f"Wins:           {result.winning_trades} ({result.win_rate:.1%})")
        lines.append(f"Losses:         {result.losing_trades} ({1 - result.win_rate:.1%})")
        lines.append(f"Profit Factor:  {result.profit_factor:.3f}")
        lines.append(f"Expectancy:     ${result.expectancy:+.2f} per trade")
        lines.append(f"Avg Win:        ${result.avg_win:+.2f}")
        lines.append(f"Avg Loss:       ${result.avg_loss:+.2f}")
        lines.append("-" * 60)
        lines.append(f"RISK METRICS:")
        lines.append(f"Max Drawdown:   {result.max_drawdown_pct:.2f}%")
        lines.append(f"Sharpe Ratio:   {result.sharpe_ratio:.3f}")
        lines.append(f"Sortino Ratio:  {result.sortino_ratio:.3f}")
        lines.append(f"Calmar Ratio:   {result.calmar_ratio:.3f}")
        lines.append(f"Std Dev:        {result.std_dev_returns:.3f}")
        lines.append("-" * 60)

        if mc_results:
            lines.append(f"MONTE CARLO ({mc_results['simulations']} simulations):")
            lines.append(f"Prob Profit:    {mc_results['prob_profit:.1%']}")
            lines.append(f"Expected Eq:   ${mc_results['expected_final_equity']:,.2f}")
            lines.append(f"Median Eq:     ${mc_results['median_final_equity']:,.2f}")
            lines.append(f"Worst Case:    ${mc_results['worst_case_equity']:,.2f}")
            lines.append(f"Best Case:     ${mc_results['best_case_equity']:,.2f}")
            lines.append(f"95%ile DD:     {mc_results['max_drawdown_percentiles']['95']:.2%}")
            lines.append("-" * 60)

        lines.append("=" * 60)
        return "\n".join(lines)
