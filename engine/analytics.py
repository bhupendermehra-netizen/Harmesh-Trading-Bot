"""
Harmesh Performance Analytics
Advanced performance analysis and reporting.
Metrics: Sharpe, Sortino, Calmar, Omega, MAR, Profit Factor, Win Rate, Expectancy
Visualization-friendly data exports.
"""
import json
import logging
import os
from datetime import datetime
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger("harmesh.analytics")


class PerformanceAnalyzer:
    """
    Comprehensive performance analysis for trading systems.
    Computes all key metrics and generates reports.
    """

    def __init__(self, config: dict):
        self.config = config

    def _get_attr(self, trade, key, default=None):
        """Extract attribute from either dict or object."""
        if isinstance(trade, dict):
            return trade.get(key, default)
        return getattr(trade, key, default)

    def analyze_trades(self, trades: list) -> dict:
        """
        Full analysis of a list of trade objects.
        trades: list of objects or dicts with pnl, pnl_pct, etc.
        """
        if not trades:
            return self._empty_metrics()

        pnls = np.array([self._get_attr(t, "pnl") for t in trades if self._get_attr(t, "pnl") is not None])
        pnl_pcts = np.array([self._get_attr(t, "pnl_pct") for t in trades if self._get_attr(t, "pnl_pct") is not None])
        durations = self._compute_durations(trades)

        wins = pnls[pnls > 0]
        losses = pnls[pnls <= 0]

        total = len(pnls)
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = win_count / total if total > 0 else 0.0

        gross_profit = float(np.sum(wins)) if len(wins) > 0 else 0.0
        gross_loss = float(abs(np.sum(losses))) if len(losses) > 0 else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.0

        avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
        avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0.0
        avg_trade = float(np.mean(pnls)) if total > 0 else 0.0
        expectancy = avg_trade  # Same as avg trade when risk is considered

        # Win/loss ratio
        win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0

        # Profitability
        net_pnl = float(np.sum(pnls))
        total_return_pct = float(np.sum(pnl_pcts)) if len(pnl_pcts) > 0 else 0.0

        # Consecutive wins/losses
        consecutive_wins = self._max_consecutive(pnls > 0)
        consecutive_losses = self._max_consecutive(pnls <= 0)

        # Trade duration stats
        avg_duration = float(np.mean(durations)) if len(durations) > 0 else 0.0
        median_duration = float(np.median(durations)) if len(durations) > 0 else 0.0

        # Monthly breakdown
        monthly_stats = self._monthly_breakdown(trades)

        # By symbol
        symbol_stats = self._by_symbol(trades)

        # By side
        long_trades = [t for t in trades if self._get_attr(t, "side") == "long"]
        short_trades = [t for t in trades if self._get_attr(t, "side") == "short"]
        long_stats = self._side_stats(long_trades)
        short_stats = self._side_stats(short_trades)

        return {
            "summary": {
                "total_trades": total,
                "winning_trades": win_count,
                "losing_trades": loss_count,
                "win_rate": round(win_rate, 4),
                "win_loss_ratio": round(win_loss_ratio, 4),
                "profit_factor": round(profit_factor, 4),
                "net_pnl": round(net_pnl, 2),
                "total_return_pct": round(total_return_pct, 2),
                "avg_trade": round(avg_trade, 2),
                "expectancy": round(expectancy, 2),
                "avg_win": round(avg_win, 2),
                "avg_loss": round(avg_loss, 2),
                "max_consecutive_wins": consecutive_wins,
                "max_consecutive_losses": consecutive_losses,
                "avg_duration_hours": round(avg_duration, 2),
                "median_duration_hours": round(median_duration, 2),
            },
            "by_side": {
                "long": long_stats,
                "short": short_stats,
            },
            "by_symbol": symbol_stats,
            "monthly": monthly_stats,
        }

    def analyze_equity(self, equity_curve: list, returns: list, risk_free_rate: float = 0.02) -> dict:
        """
        Risk-adjusted performance metrics from equity curve.
        """
        if not equity_curve or len(equity_curve) < 5:
            return self._empty_risk_metrics()

        equity = np.array(equity_curve)
        returns_arr = np.array(returns) if returns else np.diff(equity) / equity[:-1]

        # Compute returns from equity if not provided
        if len(returns_arr) < 2 and len(equity) > 2:
            returns_arr = np.diff(equity) / equity[:-1]

        # Max drawdown
        peak = np.maximum.accumulate(equity)
        dd = (peak - equity) / peak
        max_dd = float(np.max(dd))
        max_dd_pct = max_dd * 100

        # Sharpe ratio (annualized hourly)
        if len(returns_arr) > 1:
            excess = returns_arr - (risk_free_rate / (365 * 24))
            if np.std(excess) > 0:
                sharpe = float(np.mean(excess) / np.std(excess) * np.sqrt(365 * 24))
            else:
                sharpe = 0.0
        else:
            sharpe = 0.0

        # Sortino ratio
        if len(returns_arr) > 1:
            excess = returns_arr - (risk_free_rate / (365 * 24))
            downside = returns_arr[returns_arr < 0]
            if len(downside) > 0 and np.std(downside) > 0:
                sortino = float(np.mean(excess) / np.std(downside) * np.sqrt(365 * 24))
            else:
                sortino = float(np.mean(excess) * np.sqrt(365 * 24)) if np.mean(excess) > 0 else 0.0
        else:
            sortino = 0.0

        # Calmar ratio
        total_return = (equity[-1] - equity[0]) / equity[0]
        days = len(equity)  # Approximate (in hourly terms)
        annualized_return = total_return * (365 * 24 / max(days, 1))
        calmar = annualized_return / (max_dd + 1e-10) if max_dd > 0 else annualized_return * 100

        # Omega ratio (probability-weighted gain/loss)
        if len(returns_arr) > 1:
            threshold = 0
            gains = returns_arr[returns_arr > threshold]
            losses = abs(returns_arr[returns_arr < threshold])
            omega = np.sum(gains) / (np.sum(losses) + 1e-10) if np.sum(losses) > 0 else 999.0
        else:
            omega = 0.0

        # MAR ratio (Compound Annual Growth Rate / Max Drawdown)
        cagr = total_return / (max(len(equity) / (365 * 24), 1/365))
        mar = cagr / (max_dd + 1e-10) if max_dd > 0 else cagr * 100

        # Volatility (annualized)
        volatility = float(np.std(returns_arr) * np.sqrt(365 * 24)) if len(returns_arr) > 1 else 0.0

        # Value at Risk (95%)
        var_95 = float(np.percentile(returns_arr, 5)) if len(returns_arr) > 20 else 0.0

        # Conditional VaR (Expected Shortfall)
        cvar_95 = float(np.mean(returns_arr[returns_arr <= var_95])) if len(returns_arr[returns_arr <= var_95]) > 0 else 0.0

        # Profit factor from equity curve
        positive_returns = returns_arr[returns_arr > 0]
        negative_returns = abs(returns_arr[returns_arr < 0])
        profit_factor_curve = np.sum(positive_returns) / (np.sum(negative_returns) + 1e-10)

        return {
            "total_return_pct": round(total_return * 100, 2),
            "annualized_return_pct": round(annualized_return * 100, 2),
            "max_drawdown_pct": round(max_dd_pct, 2),
            "sharpe_ratio": round(sharpe, 3),
            "sortino_ratio": round(sortino, 3),
            "calmar_ratio": round(calmar, 3),
            "omega_ratio": round(omega, 3),
            "mar_ratio": round(mar, 3),
            "volatility_pct": round(volatility * 100, 2),
            "var_95_pct": round(var_95 * 100, 2),
            "cvar_95_pct": round(cvar_95 * 100, 2),
            "profit_factor": round(profit_factor_curve, 3),
            "peak_equity": round(float(np.max(equity)), 2),
            "current_equity": round(float(equity[-1]), 2),
        }

    def generate_report(self, trades: list, equity_curve: list, returns: list) -> str:
        """Generate a comprehensive formatted report."""
        trade_analysis = self.analyze_trades(trades)
        risk_metrics = self.analyze_equity(equity_curve, returns)

        lines = []
        lines.append("=" * 70)
        lines.append("HARMESH ADVANCED PERFORMANCE REPORT")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 70)

        s = trade_analysis["summary"]
        lines.append(f"\nTRADING SUMMARY:")
        lines.append(f"  Total Trades:     {s['total_trades']}")
        lines.append(f"  Win Rate:         {s['win_rate']:.1%} ({s['winning_trades']}W / {s['losing_trades']}L)")
        lines.append(f"  Profit Factor:    {s['profit_factor']:.3f}")
        lines.append(f"  Net P&L:          ${s['net_pnl']:+,.2f}")
        lines.append(f"  Avg Trade:        ${s['avg_trade']:+,.2f}")
        lines.append(f"  Avg Win:          ${s['avg_win']:+,.2f}")
        lines.append(f"  Avg Loss:         ${s['avg_loss']:+,.2f}")
        lines.append(f"  Win/Loss Ratio:   {s['win_loss_ratio']:.3f}")
        lines.append(f"  Expectancy:       ${s['expectancy']:+,.2f}")
        lines.append(f"  Max Consec Wins:  {s['max_consecutive_wins']}")
        lines.append(f"  Max Consec Losses: {s['max_consecutive_losses']}")
        lines.append(f"  Avg Duration:     {s['avg_duration_hours']:.1f}h")

        r = risk_metrics
        lines.append(f"\nRISK-ADJUSTED METRICS:")
        lines.append(f"  Total Return:     {r['total_return_pct']:+.2f}%")
        lines.append(f"  Annualized Return: {r['annualized_return_pct']:+.2f}%")
        lines.append(f"  Max Drawdown:     {r['max_drawdown_pct']:.2f}%")
        lines.append(f"  Sharpe Ratio:     {r['sharpe_ratio']:.3f}")
        lines.append(f"  Sortino Ratio:    {r['sortino_ratio']:.3f}")
        lines.append(f"  Calmar Ratio:     {r['calmar_ratio']:.3f}")
        lines.append(f"  Omega Ratio:      {r['omega_ratio']:.3f}")
        lines.append(f"  MAR Ratio:        {r['mar_ratio']:.3f}")
        lines.append(f"  Volatility:       {r['volatility_pct']:.2f}%")
        lines.append(f"  VaR (95%):        {r['var_95_pct']:.2f}%")
        lines.append(f"  CVaR (95%):       {r['cvar_95_pct']:.2f}%")

        lines.append(f"\nBY SIDE:")
        for side, stats in trade_analysis["by_side"].items():
            if stats["trades"] > 0:
                lines.append(f"  {side.upper():5s}: {stats['trades']} trades, "
                           f"WR={stats['win_rate']:.1%}, PF={stats['profit_factor']:.2f}, "
                           f"Net=${stats['net_pnl']:+,.2f}")

        if trade_analysis.get("by_symbol"):
            lines.append(f"\nBY SYMBOL:")
            for sym, stats in trade_analysis["by_symbol"].items():
                lines.append(f"  {sym:10s}: {stats['trades']} trades, "
                           f"WR={stats['win_rate']:.1%}, Net=${stats['net_pnl']:+,.2f}")

        if trade_analysis.get("monthly"):
            lines.append(f"\nMONTHLY BREAKDOWN:")
            for month, stats in list(trade_analysis["monthly"].items())[-12:]:
                lines.append(f"  {month}: {stats['trades']} trades, "
                           f"Net=${stats['net_pnl']:+,.2f}, WR={stats['win_rate']:.1%}")

        lines.append("\n" + "=" * 70)
        return "\n".join(lines)

    def _max_consecutive(self, arr: np.ndarray) -> int:
        """Find maximum consecutive True values."""
        if len(arr) == 0:
            return 0
        max_count = 0
        current = 0
        for val in arr:
            if val:
                current += 1
                max_count = max(max_count, current)
            else:
                current = 0
        return max_count

    def _compute_durations(self, trades: list) -> list[float]:
        """Compute trade durations in hours."""
        durations = []
        for t in trades:
            entry_time = self._get_attr(t, "entry_time")
            exit_time = self._get_attr(t, "exit_time")
            if entry_time and exit_time:
                try:
                    entry = datetime.fromisoformat(entry_time) if isinstance(entry_time, str) else entry_time
                    exit = datetime.fromisoformat(exit_time) if isinstance(exit_time, str) else exit_time
                    duration_hours = (exit - entry).total_seconds() / 3600
                    durations.append(duration_hours)
                except (ValueError, TypeError):
                    durations.append(0.0)
        return durations

    def _monthly_breakdown(self, trades: list) -> dict:
        """Group trades by month and compute stats."""
        monthly = {}
        for t in trades:
            exit_time = self._get_attr(t, "exit_time")
            pnl = self._get_attr(t, "pnl")
            if exit_time:
                try:
                    dt = exit_time if isinstance(exit_time, datetime) else datetime.fromisoformat(exit_time)
                    key = dt.strftime("%Y-%m")
                except (ValueError, TypeError):
                    key = "unknown"
            else:
                key = "unknown"

            if key not in monthly:
                monthly[key] = {"trades": 0, "net_pnl": 0.0, "wins": 0}
            monthly[key]["trades"] += 1
            if pnl is not None:
                monthly[key]["net_pnl"] += pnl
                if pnl > 0:
                    monthly[key]["wins"] += 1

        result = {}
        for key, data in monthly.items():
            result[key] = {
                "trades": data["trades"],
                "net_pnl": round(data["net_pnl"], 2),
                "win_rate": round(data["wins"] / data["trades"], 4) if data["trades"] > 0 else 0.0,
            }
        return result

    def _by_symbol(self, trades: list) -> dict:
        """Group trade stats by symbol."""
        symbols = {}
        for t in trades:
            sym = self._get_attr(t, "symbol", "unknown")
            pnl = self._get_attr(t, "pnl")
            if sym not in symbols:
                symbols[sym] = {"trades": 0, "net_pnl": 0.0, "wins": 0, "pnls": []}
            symbols[sym]["trades"] += 1
            if pnl is not None:
                symbols[sym]["net_pnl"] += pnl
                symbols[sym]["pnls"].append(pnl)
                if pnl > 0:
                    symbols[sym]["wins"] += 1

        result = {}
        for sym, data in symbols.items():
            pnls = np.array(data["pnls"])
            gross_profit = np.sum(pnls[pnls > 0])
            gross_loss = abs(np.sum(pnls[pnls < 0]))
            result[sym] = {
                "trades": data["trades"],
                "net_pnl": round(data["net_pnl"], 2),
                "win_rate": round(data["wins"] / data["trades"], 4) if data["trades"] > 0 else 0.0,
                "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss > 0 else 999.0,
                "avg_trade": round(float(np.mean(pnls)), 2),
            }
        return result

    def _side_stats(self, trades: list) -> dict:
        """Compute stats for a set of trades (long or short)."""
        if not trades:
            return {"trades": 0, "net_pnl": 0.0, "win_rate": 0.0, "profit_factor": 0.0, "avg_trade": 0.0}

        pnls = np.array([self._get_attr(t, "pnl") for t in trades if self._get_attr(t, "pnl") is not None])
        if len(pnls) == 0:
            return {"trades": len(trades), "net_pnl": 0.0, "win_rate": 0.0, "profit_factor": 0.0, "avg_trade": 0.0}

        wins = pnls[pnls > 0]
        losses = pnls[pnls < 0]
        gross_profit = np.sum(wins) if len(wins) > 0 else 0.0
        gross_loss = abs(np.sum(losses)) if len(losses) > 0 else 0.0

        return {
            "trades": len(pnls),
            "net_pnl": round(float(np.sum(pnls)), 2),
            "win_rate": round(len(wins) / len(pnls), 4) if len(pnls) > 0 else 0.0,
            "profit_factor": round(float(gross_profit / gross_loss), 3) if gross_loss > 0 else 999.0,
            "avg_trade": round(float(np.mean(pnls)), 2),
        }

    def _empty_metrics(self) -> dict:
        return {
            "summary": {
                "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
                "win_rate": 0.0, "win_loss_ratio": 0.0, "profit_factor": 0.0,
                "net_pnl": 0.0, "total_return_pct": 0.0, "avg_trade": 0.0,
                "expectancy": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
                "max_consecutive_wins": 0, "max_consecutive_losses": 0,
                "avg_duration_hours": 0.0, "median_duration_hours": 0.0,
            },
            "by_side": {"long": self._side_stats([]), "short": self._side_stats([])},
            "by_symbol": {},
            "monthly": {},
        }

    def _empty_risk_metrics(self) -> dict:
        return {
            "total_return_pct": 0.0, "annualized_return_pct": 0.0,
            "max_drawdown_pct": 0.0, "sharpe_ratio": 0.0, "sortino_ratio": 0.0,
            "calmar_ratio": 0.0, "omega_ratio": 0.0, "mar_ratio": 0.0,
            "volatility_pct": 0.0, "var_95_pct": 0.0, "cvar_95_pct": 0.0,
            "profit_factor": 0.0, "peak_equity": 0.0, "current_equity": 0.0,
        }
