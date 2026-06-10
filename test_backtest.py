"""
Quick test: reproduce the 'empty' attribute error
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from engine.backtest import BacktestEngine


def load_csv():
    csv_path = "data/historical_btc_1h.csv"
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    return df.reset_index().rename(columns={"index": "timestamp"})


def make_config():
    return {
        "trading": {"symbols": ["BTC/USDT"], "timeframe": "1h", "initial_capital": 10000,
                    "slippage": 0.001, "fee_rate": 0.001, "max_open_trades": 3},
        "risk": {"max_risk_per_trade": 0.02, "atr_period": 14,
                 "stop_loss_atr_mult": 1.5, "take_profit_atr_mult": 3.0, "max_open_positions": 3},
        "backtest": {"initial_capital": 10000, "commission": 0.001, "slippage": 0.001},
        "advanced_strategy": {"active_strategies": ["trend_following"], "fusion_method": "weighted",
            "mtf_enabled": False, "ml_enabled": False,
            "trend_params": {"ema_fast": 9, "ema_slow": 21, "macd_fast": 12, "macd_slow": 26,
                             "macd_signal": 9, "adx_threshold": 25},
            "mean_reversion_params": {"rsi_period": 14, "rsi_oversold": 30, "rsi_overbought": 70,
                                      "bb_period": 20, "bb_std": 2.0, "mean_reversion_threshold": 0.02},
            "volatility_params": {"bb_breakout_threshold": 2.5, "kc_period": 20,
                                  "kc_multiplier": 2.0, "volume_surge_mult": 1.5}},
    }


def main():
    df = load_csv()
    print(f"Data: {len(df)} candles")
    
    config = make_config()
    
    # Test 1: just create BacktestEngine
    engine = BacktestEngine(config)
    print("1. BacktestEngine created OK")
    
    # Test 2: check strategy import
    from engine.backtest_strategy import BacktestStrategy
    strategy = BacktestStrategy(config)
    print(f"2. BacktestStrategy created OK")
    
    # Test 3: generate_signal on a slice
    slice_df = df.iloc[:100].copy()
    sig = strategy.generate_signal(slice_df)
    print(f"3. Signal: {sig['signal']}, confidence={sig['confidence']:.2f}")
    
    # Test 4: full run
    result = engine.run(strategy, df)
    print(f"4. Full run: {result.total_trades} trades, WR={result.win_rate:.1%}, PF={result.profit_factor:.2f}")
    
    print("\nAll tests passed!")


if __name__ == "__main__":
    main()
