"""Quick single-trial optimizer test."""
import sys, os, json, pandas as pd, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.backtest import BacktestEngine
from engine.backtest_strategy import BacktestStrategy

# Load data
df = pd.read_csv("data/historical_btc_1h.csv", index_col=0, parse_dates=True)
df = df.reset_index()
if "index" in df.columns:
    df.rename(columns={"index": "timestamp"}, inplace=True)
df = df.sort_values("timestamp").reset_index(drop=True)
print(f"Data: {len(df)} rows")

# Random params
params = {"ema_fast": 12, "ema_slow": 26, "macd_fast": 8, "macd_slow": 30, "macd_signal": 10, "adx_threshold": 28, "_strategies": ["trend_following"]}

config = {
    "trading": {"symbols": ["BTC/USDT"], "timeframe": "1h", "initial_capital": 10000, "slippage": 0.001, "fee_rate": 0.001, "max_open_trades": 3, "stop_loss_pct": 0.02},
    "risk": {"max_risk_per_trade": 0.02, "atr_period": 14, "stop_loss_atr_mult": 1.5, "take_profit_atr_mult": 3.0, "max_open_positions": 3},
    "advanced_strategy": {
        "active_strategies": params.get("_strategies", ["trend_following"]),
        "fusion_method": "weighted", "mtf_enabled": False, "ml_enabled": False,
        "trend_params": {k: v for k, v in params.items() if k in ["ema_fast","ema_slow","macd_fast","macd_slow","macd_signal","adx_threshold"]},
        "mean_reversion_params": {},
        "volatility_params": {},
    },
}

engine = BacktestEngine(config)
strategy = BacktestStrategy(config)
result = engine.run(df, strategy, print_progress=False)

score = result.win_rate * 10 + result.profit_factor * 5 - result.max_drawdown_pct / 20 + min(result.sharpe_ratio / 5, 2)
print(f"WR={result.win_rate:.1%} PF={result.profit_factor:.2f} Score={score:.2f}")
print("OK")
