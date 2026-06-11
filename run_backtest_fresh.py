"""
Phase 3: Fresh backtest on real BTC data after all bug fixes.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import pandas as pd
import numpy as np

print("=" * 70)
print("PHASE 3: FRESH BACKTEST ON REAL BTC DATA")
print("=" * 70)

# Load real data
df = pd.read_csv("data/historical_btc_1h.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"])
df.set_index("timestamp", inplace=True)
print(f"Loaded {len(df)} candles: {df.index[0]} to {df.index[-1]}")
print(f"Price range: ${df['low'].min():.2f} - ${df['high'].max():.2f}")

config = {
    "backtest": {"initial_capital": 10000.0, "commission": 0.001, "slippage": 0.001},
    "risk": {"max_open_trades": 3, "min_balance_for_trade": 10.0},
    "trading": {"symbols": ["BTC/USDT"], "timeframe": "1h", "strategy": "macd_rsi"},
    "advanced_strategy": {
        "active_strategies": ["trend_following", "mean_reversion"],
        "fusion_method": "weighted",
        "ml_enabled": False,
        "trend_params": {"ema_fast": 9, "ema_slow": 21, "macd_fast": 12, "macd_slow": 26, "macd_signal": 9, "adx_threshold": 25},
        "mean_reversion_params": {"rsi_period": 14, "rsi_oversold": 30, "rsi_overbought": 70, "bb_period": 20, "bb_std": 2.0, "mean_reversion_threshold": 0.02},
    },
    "live": {"stop_loss_atr_multiplier": 2.0, "take_profit_atr_multiplier": 4.0, "max_risk_per_trade": 0.02},
    "paper": {"initial_capital": 10000.0, "state_file": "/dev/null", "trade_log": "/dev/null"},
    "exchange": {"name": "binance", "sandbox": True, "api_key": "", "api_secret": ""},
    "regime": {},
}

from engine.backtest import BacktestEngine
from engine.backtest_strategy import BacktestStrategy

print("\n--- Running backtest ---")
start = time.time()

engine = BacktestEngine(config)
strategy = BacktestStrategy(config)
result = engine.run(df, strategy, symbol="BTC/USDT", timeframe="1h", print_progress=True)

elapsed = time.time() - start

print(f"\nBacktest completed in {elapsed:.1f}s")
print("=" * 70)
print("PERFORMANCE REPORT")
print("=" * 70)
print(f"  Strategy:       {result.strategy_name}")
print(f"  Symbol:         {result.symbol} ({result.timeframe})")
print(f"  Period:         {result.start_date} to {result.end_date}")
print(f"  Initial capital: ${result.initial_capital:,.2f}")
print(f"  Final equity:   ${result.final_equity:,.2f}")
print(f"  Total return:   {result.total_return_pct:+.2f}%")
print(f"  Total trades:   {result.total_trades}")
print(f"  Winning trades: {result.winning_trades}")
print(f"  Losing trades:  {result.losing_trades}")
print(f"  Win rate:       {result.win_rate*100:.1f}%")
print(f"  Profit factor:  {result.profit_factor:.2f}")
print(f"  Max drawdown:   {result.max_drawdown_pct:.2f}%")
print(f"  Sharpe ratio:   {result.sharpe_ratio:.2f}")
print(f"  Sortino ratio:  {result.sortino_ratio:.2f}")
print(f"  Calmar ratio:   {result.calmar_ratio:.2f}")
print(f"  Avg win:        ${result.avg_win:+.2f}")
print(f"  Avg loss:       ${result.avg_loss:+.2f}")
print(f"  Avg trade:      ${result.avg_trade:+.2f}")
print(f"  Expectancy:     ${result.expectancy:+.2f}")
print(f"  Std dev ret:    {result.std_dev_returns:.4f}")

# Trade side breakdown
trades = result.trades
if trades:
    side_stats = {}
    for t in trades:
        s = t["side"]
        if s not in side_stats:
            side_stats[s] = {"count": 0, "won": 0, "total_pnl": 0.0}
        side_stats[s]["count"] += 1
        side_stats[s]["total_pnl"] += t["pnl"]
        if t["pnl"] > 0:
            side_stats[s]["won"] += 1

    print(f"\n  Trade breakdown:")
    for side, stats in side_stats.items():
        wr = stats["won"] / stats["count"] * 100 if stats["count"] > 0 else 0
        print(f"    {side}: {stats['count']} trades, {stats['won']} wins ({wr:.0f}%), "
              f"PnL=${stats['total_pnl']:+.2f}")

# Exit reason breakdown
exit_reasons = {}
for t in trades:
    r = t.get("exit_reason", "signal")
    exit_reasons[r] = exit_reasons.get(r, 0) + 1
print(f"\n  Exit reasons:")
for r, c in sorted(exit_reasons.items(), key=lambda x: -x[1]):
    print(f"    {r}: {c}")

# Trim large data for JSON (keep summary, omit full equity curve and trade details)
result_dict = {
    "strategy_name": result.strategy_name,
    "symbol": result.symbol,
    "timeframe": result.timeframe,
    "start_date": result.start_date,
    "end_date": result.end_date,
    "initial_capital": result.initial_capital,
    "final_equity": result.final_equity,
    "total_return": result.total_return,
    "total_return_pct": result.total_return_pct,
    "total_trades": result.total_trades,
    "winning_trades": result.winning_trades,
    "losing_trades": result.losing_trades,
    "win_rate": result.win_rate,
    "profit_factor": result.profit_factor,
    "max_drawdown_pct": result.max_drawdown_pct,
    "sharpe_ratio": result.sharpe_ratio,
    "sortino_ratio": result.sortino_ratio,
    "calmar_ratio": result.calmar_ratio,
    "avg_win": result.avg_win,
    "avg_loss": result.avg_loss,
    "avg_trade": result.avg_trade,
    "expectancy": result.expectancy,
    "std_dev_returns": result.std_dev_returns,
    "trades": result.trades[:200] if len(result.trades) > 200 else result.trades,
    "equity_curve": result.equity_curve[:500] if len(result.equity_curve) > 500 else result.equity_curve,
}

# Save results
out_path = "data/backtest_results.json"
with open(out_path, "w") as f:
    json.dump(result_dict, f, indent=2, default=str)
print(f"\nResults saved to {out_path}")

# Also generate trade-level CSV
trades_df = pd.DataFrame(result.trades)
if len(trades_df) > 0:
    # Reorder columns
    cols = ["symbol", "side", "entry_time", "exit_time", "entry_price", "exit_price",
            "quantity", "pnl", "pnl_pct", "exit_reason"]
    cols = [c for c in cols if c in trades_df.columns]
    trades_df[cols].to_csv("data/backtest_trades.csv", index=False)
    print(f"Trade log saved to data/backtest_trades.csv ({len(trades_df)} trades)")

# Save equity curve separately
pd.DataFrame({"equity": result.equity_curve}).to_csv("data/backtest_equity.csv", index=False)
print(f"Equity curve saved to data/backtest_equity.csv ({len(result.equity_curve)} points)")

print("\n" + "=" * 70)
print("PHASE 3 COMPLETE")
print("=" * 70)
