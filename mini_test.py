"""Minimal optimizer test."""
import sys, os, json, pandas as pd
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.backtest import BacktestEngine
from engine.backtest_strategy import BacktestStrategy

print("loading data...")
df = pd.read_csv("data/historical_btc_1h.csv", index_col=0, parse_dates=True)
df = df.reset_index()
if "index" in df.columns:
    df.rename(columns={"index": "timestamp"}, inplace=True)
print(f"Data: {len(df)} rows")

config = {
    "trading": {
        "symbols": ["BTC/USDT"], "timeframe": "1h",
        "initial_capital": 10000, "slippage": 0.001, "fee_rate": 0.001,
        "max_open_trades": 3, "stop_loss_pct": 0.02,
    },
    "risk": {
        "max_risk_per_trade": 0.02, "atr_period": 14,
        "stop_loss_atr_mult": 1.5, "take_profit_atr_mult": 3.0,
        "max_open_positions": 3,
    },
    "advanced_strategy": {
        "active_strategies": ["trend_following"],
        "fusion_method": "weighted", "mtf_enabled": False, "ml_enabled": False,
        "trend_params": {"ema_fast": 9, "ema_slow": 21, "macd_fast": 12, "macd_slow": 26, "macd_signal": 9, "adx_threshold": 25},
        "mean_reversion_params": {},
        "volatility_params": {},
    },
}

print("running backtest...")
sys.stdout.flush()
engine = BacktestEngine(config)
strategy = BacktestStrategy(config)
result = engine.run(df, strategy, print_progress=False)
print(f"Trades: {result.total_trades}, WR: {result.win_rate:.1%}, PF: {result.profit_factor:.3f}")
print("DONE")
