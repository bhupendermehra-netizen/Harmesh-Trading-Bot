"""
Harmesh Strategy Parameter Optimizer (Random Search + Early Stopping)
Tests parameter combinations via walk-forward backtest.
"""
import json, os, sys, copy, random, math
from datetime import datetime

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.backtest import BacktestEngine
from engine.backtest_strategy import BacktestStrategy


def load_data():
    """Load or fetch OHLCV data."""
    # Try JSON first, then CSV
    json_path = "data/btc_1h_data.json"
    csv_path = "data/historical_btc_1h.csv"
    
    if os.path.exists(json_path):
        with open(json_path) as f:
            raw = json.load(f)
        df = pd.DataFrame(raw)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp").reset_index(drop=True)
            return df
    
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        df = df.reset_index()
        df.rename(columns={"index": "timestamp"}, inplace=True)
        df = df.sort_values("timestamp").reset_index(drop=True)
        print(f"Loaded {len(df)} candles from CSV: {csv_path}")
        return df
    
    print("No data file found. Run scripts/fetch_data.py first.")
    sys.exit(1)


def make_config(params):
    return {
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
            "active_strategies": params.get("_strategies", ["trend_following", "mean_reversion"]),
            "fusion_method": "weighted", "mtf_enabled": False, "ml_enabled": False,
            "trend_params": {
                "ema_fast": params.get("ema_fast", 9),
                "ema_slow": params.get("ema_slow", 21),
                "macd_fast": params.get("macd_fast", 12),
                "macd_slow": params.get("macd_slow", 26),
                "macd_signal": params.get("macd_signal", 9),
                "adx_threshold": params.get("adx_threshold", 25),
            },
            "mean_reversion_params": {
                "rsi_period": params.get("rsi_period", 14),
                "rsi_oversold": params.get("rsi_oversold", 30),
                "rsi_overbought": params.get("rsi_overbought", 70),
                "bb_period": params.get("bb_period", 20),
                "bb_std": params.get("bb_std", 2.0),
                "mean_reversion_threshold": params.get("mean_reversion_threshold", 0.02),
            },
            "volatility_params": {
                "bb_breakout_threshold": params.get("bb_breakout_threshold", 2.5),
                "kc_period": params.get("kc_period", 20),
                "kc_multiplier": params.get("kc_multiplier", 2.0),
                "volume_surge_mult": params.get("volume_surge_mult", 1.5),
            },
        },
    }


def evaluate(params, df):
    """Run single backtest, return metrics dict."""
    config = make_config(params)
    try:
        engine = BacktestEngine(config)
        strategy = BacktestStrategy(config)
        result = engine.run(df, strategy, print_progress=False)
        score = (
            result.win_rate * 10
            + result.profit_factor * 5
            - result.max_drawdown_pct / 20
            + min(result.sharpe_ratio / 5, 2)
        )
        return {
            "win_rate": result.win_rate,
            "profit_factor": result.profit_factor,
            "total_return_pct": result.total_return_pct,
            "max_drawdown_pct": result.max_drawdown_pct,
            "sharpe_ratio": result.sharpe_ratio,
            "total_trades": result.total_trades,
            "final_equity": result.final_equity,
            "score": score,
        }
    except Exception as e:
        return {"error": str(e), "score": -999}


# Parameter search spaces (ranges for random sampling)
SPACES = {
    "trend_following": {
        "ema_fast": (3, 20, True),
        "ema_slow": (15, 50, True),
        "macd_fast": (5, 20, True),
        "macd_slow": (20, 40, True),
        "macd_signal": (5, 15, True),
        "adx_threshold": (20, 40, True),
    },
    "mean_reversion": {
        "rsi_period": (7, 21, True),
        "rsi_oversold": (20, 40, True),
        "rsi_overbought": (60, 80, True),
        "bb_period": (10, 30, True),
        "bb_std": (1.2, 3.5, False),
        "mean_reversion_threshold": (0.005, 0.05, False),
    },
    "volatility_breakout": {
        "bb_breakout_threshold": (1.5, 4.0, False),
        "kc_period": (10, 30, True),
        "kc_multiplier": (1.2, 3.5, False),
        "volume_surge_mult": (1.2, 3.0, False),
    },
}


def sample_params(space):
    p = {}
    for k, (lo, hi, is_int) in space.items():
        val = random.uniform(lo, hi)
        if is_int:
            val = int(round(val))
        p[k] = val
    return p


def random_search(strategy_name, df, n_trials=40):
    """Random search over a strategy family."""
    space = SPACES[strategy_name]
    results = []
    best_score = -999
    no_improve = 0
    
    print(f"\n--- Random Search: {strategy_name} ({n_trials} trials) ---")
    for i in range(n_trials):
        params = sample_params(space)
        params["_strategies"] = [strategy_name]
        
        metrics = evaluate(params, df)
        if "error" in metrics:
            print(f"  [{i+1}/{n_trials}] ERROR: {metrics['error']}")
            continue
        
        metrics["params"] = params
        results.append(metrics)
        
        score = metrics["score"]
        if score > best_score:
            best_score = score
            no_improve = 0
            print(f"  [{i+1}/{n_trials}] ** NEW BEST ** WR={metrics['win_rate']:.1%} "
                  f"PF={metrics['profit_factor']:.2f} Ret={metrics['total_return_pct']:+.2f}% "
                  f"DD={metrics['max_drawdown_pct']:.1f}% Score={score:.2f}")
        else:
            no_improve += 1
        
        # Early stopping: no improvement in 15 trials
        if no_improve >= 15 and i >= 20:
            print(f"  Early stopping at trial {i+1} (no improvement in {no_improve})")
            break
        
        sys.stdout.flush()
    
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:5]


def main():
    print("Harmesh Strategy Parameter Optimizer")
    print(f"Started: {datetime.now().isoformat()}\n")
    
    df = load_data()
    print(f"Data: {len(df)} candles, {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"BTC: ${df['close'].min():.0f} - ${df['close'].max():.0f}\n")
    
    # Phase 1: Optimize each strategy family independently
    all_best = {}
    for name in ["trend_following", "mean_reversion", "volatility_breakout"]:
        top = random_search(name, df, n_trials=40)
        all_best[name] = top
        if top:
            b = top[0]
            print(f"\nBest {name}: WR={b['win_rate']:.1%} PF={b['profit_factor']:.2f} "
                  f"Ret={b['total_return_pct']:+.2f}% DD={b['max_drawdown_pct']:.1f}% "
                  f"Score={b['score']:.2f}")
            print(f"  Params: {b['params']}")
    
    # Phase 2: Composite (best params combined) + Combined strategies
    print("\n" + "="*60)
    print("PHASE 2: TESTING COMBINATIONS")
    print("="*60)
    
    # Pull best params from each family
    best_params = {}
    for name in ["trend_following", "mean_reversion", "volatility_breakout"]:
        if all_best.get(name):
            p = all_best[name][0]["params"]
            for k, v in p.items():
                if k != "_strategies":
                    best_params[k] = v
    
    results = []
    
    # Test all strategy combos with best params
    combos = [
        ["trend_following"],
        ["mean_reversion"],
        ["volatility_breakout"],
        ["trend_following", "mean_reversion"],
        ["trend_following", "volatility_breakout"],
        ["mean_reversion", "volatility_breakout"],
        ["trend_following", "mean_reversion", "volatility_breakout"],
    ]
    
    for combo in combos:
        params = dict(best_params)
        params["_strategies"] = combo
        m = evaluate(params, df)
        if "error" not in m:
            m["combo"] = combo
            results.append(m)
            print(f"  {','.join(combo):45s}: WR={m['win_rate']:.1%} PF={m['profit_factor']:.2f} "
                  f"Ret={m['total_return_pct']:+.2f}% DD={m['max_drawdown_pct']:.1f}% "
                  f"Score={m['score']:.2f}")
    
    results.sort(key=lambda r: r["score"], reverse=True)
    
    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "data": {"candles": len(df), "range": f"{df['timestamp'].min()} to {df['timestamp'].max()}"},
        "best_per_strategy": {
            name: [{"score": r["score"], "win_rate": r["win_rate"], "profit_factor": r["profit_factor"],
                    "total_return_pct": r["total_return_pct"], "max_drawdown_pct": r["max_drawdown_pct"],
                    "sharpe_ratio": r["sharpe_ratio"], "total_trades": r["total_trades"],
                    "params": {k: v for k, v in r["params"].items() if k != "_strategies"}}
                   for r in top]
            for name, top in all_best.items()
        },
        "combo_results": [
            {"combo": r["combo"], "score": r["score"], "win_rate": r["win_rate"],
             "profit_factor": r["profit_factor"], "total_return_pct": r["total_return_pct"],
             "max_drawdown_pct": r["max_drawdown_pct"], "sharpe_ratio": r["sharpe_ratio"],
             "total_trades": r["total_trades"]}
            for r in results
        ],
        "best_overall": None,
    }
    if results:
        output["best_overall"] = output["combo_results"][0]
    
    os.makedirs("data", exist_ok=True)
    with open("data/optimization_results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResults saved to data/optimization_results.json")
    
    if results:
        best = results[0]
        print(f"\n{'='*60}")
        print(f"BEST OVERALL: {','.join(best['combo'])}")
        print(f"  Win Rate:       {best['win_rate']:.1%}")
        print(f"  Profit Factor:  {best['profit_factor']:.2f}")
        print(f"  Return:         {best['total_return_pct']:+.2f}%")
        print(f"  Max Drawdown:   {best['max_drawdown_pct']:.1f}%")
        print(f"  Sharpe:         {best['sharpe_ratio']:.2f}")
        print(f"  Trades:         {best['total_trades']}")
        print(f"  Score:          {best['score']:.2f}")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
