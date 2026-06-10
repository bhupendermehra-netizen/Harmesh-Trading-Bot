#!/usr/bin/env python3
"""Quick test: verify all modules import and basic logic works."""
import sys
sys.path.insert(0, '/root/harmesh')

print("Testing imports...")
from engine.exchange import ExchangeConnector
print("  exchange.py  OK")
from engine.risk import RiskManager
print("  risk.py      OK")
from engine.strategy import MACDRSIStrategy, EMACrossoverStrategy, get_strategy
print("  strategy.py  OK")
from engine.paper import PaperTradingEngine, PaperTrade
print("  paper.py     OK")
from engine.live import LiveTradeEngine
print("  live.py      OK")

import json
with open('/root/harmesh/config.json') as f:
    config = json.load(f)

print("\nTesting strategy signal generation...")
import pandas as pd
import numpy as np

np.random.seed(42)
dates = pd.date_range('2026-01-01', periods=200, freq='1h')
close = 50000 + np.cumsum(np.random.randn(200) * 10)
mock_df = pd.DataFrame({
    'timestamp': dates,
    'open': close + np.random.randn(200) * 5,
    'high': close + np.abs(np.random.randn(200)) * 30,
    'low': close - np.abs(np.random.randn(200)) * 30,
    'close': close,
    'volume': np.random.rand(200) * 1000,
})
mock_df.set_index('timestamp', inplace=True)

strat = get_strategy('macd_rsi', config)
signal = strat.generate_signal(mock_df)
print(f"  MACD+RSI signal: {signal}")

strat2 = get_strategy('ema_crossover', config)
signal2 = strat2.generate_signal(mock_df)
print(f"  EMA crossover:   {signal2}")

print("\nTesting PaperTrade...")
t = PaperTrade("BTC/USDT", "long", 50000.0, 0.02, 49000.0, 52000.0, "2026-01-01T00:00:00", 1000.0)
t.close_trade(51000.0, "take_profit")
d = t.to_dict()
print(f"  Trade PnL: ${d['pnl']:.2f} ({d['pnl_pct']:.2f}%)")
assert d['pnl'] == 20.0, f"Expected 20.0, got {d['pnl']}"

print("\nTesting RiskManager...")
risk = RiskManager(config)
atr = risk.compute_atr(mock_df)
print(f"  ATR: {atr:.2f}")
sl = risk.compute_stop_loss(50000.0, "long", atr, 2.0)
tp = risk.compute_take_profit(50000.0, "long", atr, 4.0)
print(f"  SL: {sl:.2f} | TP: {tp:.2f}")
size = risk.compute_position_size(1000.0, 50000.0, sl)
print(f"  Position size: {size:.6f} BTC")
allowed, reason = risk.can_open_trade(0, 1000.0)
print(f"  Can open trade: {allowed} ({reason})")

print("\nAll tests PASS!")
