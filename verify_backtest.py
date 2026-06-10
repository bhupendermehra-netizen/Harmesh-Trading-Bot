"""
Quick sanity check that backtest runs with performance fix.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
import json

from engine.backtest import BacktestEngine
from engine.backtest_strategy import BacktestStrategy

# Load config
with open("config.json") as f:
    config = json.load(f)

# Load data
df = pd.read_csv("data/historical_btc_1h.csv", index_col=0, parse_dates=True)
if df.index.name == "timestamp" or "timestamp" in dir(df.index):
    pass
df = df.reset_index()
if "index" in df.columns:
    df.rename(columns={"index": "timestamp"}, inplace=True)

print(f"Data: {len(df)} rows, cols: {list(df.columns)}")

# Quick test
engine = BacktestEngine(config)
strategy = BacktestStrategy(config)

t0 = time.time()
result = engine.run(df, strategy, print_progress=False)
t1 = time.time()

print(f"Time: {t1-t0:.1f}s")
print(f"Trades: {result.total_trades}")
print(f"Win rate: {result.win_rate*100:.1f}%")
print(f"Profit factor: {result.profit_factor:.3f}")
print(f"Equity curve points: {len(result.equity_curve)}")
print(f"Final equity: ${result.final_equity:,.2f}")
