"""
Run full backtest with walk-forward analysis and Monte Carlo simulation.
"""
import json
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.backtest import BacktestEngine
from engine.backtest_strategy import BacktestStrategy
from engine.analytics import PerformanceAnalyzer


def main():
    with open("config.json") as f:
        config = json.load(f)

    # Load data
    data_path = "data/historical_btc_1h.csv"
    if not os.path.exists(data_path):
        print("No historical data. Run: python scripts/fetch_data.py")
        return

    df = pd.read_csv(data_path, index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]
    print(f"Loaded {len(df)} candles | {df.index[0]} to {df.index[-1]}")
    print(f"Price: ${df['low'].min():.0f} - ${df['high'].max():.0f}")
    print()

    # Create backtest engine
    engine = BacktestEngine(config)
    strategy = BacktestStrategy(config)

    # ---- Full backtest ----
    print("=" * 56)
    print("  FULL BACKTEST")
    print("=" * 56)
    result = engine.run(df, strategy, timeframe="1h")
    print(engine.print_report(result))
    print()

    # ---- Walk-forward ----
    print("=" * 56)
    print("  WALK-FORWARD ANALYSIS")
    print("=" * 56)
    wf_results = engine.run_walk_forward(df, BacktestStrategy, timeframe="1h")
    if wf_results:
        wf_trades = sum(r.total_trades for r in wf_results)
        wf_wins = sum(r.winning_trades for r in wf_results)
        wf_returns = [r.total_return_pct for r in wf_results]
        print(f"Windows tested: {len(wf_results)}")
        print(f"Total OOS trades: {wf_trades}")
        print(f"Avg OOS return: {sum(wf_returns)/len(wf_returns):+.2f}%")
        print(f"Profitable windows: {sum(1 for r in wf_results if r.total_return > 0)}/{len(wf_results)}")
    else:
        print("Walk-forward disabled in config. Set backtest.walk_forward_enabled=true")
    print()

    # ---- Monte Carlo ----
    print("=" * 56)
    print("  MONTE CARLO SIMULATION")
    print("=" * 56)
    mc_results = engine.run_monte_carlo(result)
    if mc_results:
        print(f"Simulations: {mc_results['simulations']}")
        print(f"Prob of Profit: {mc_results['prob_profit']:.1%}")
        print(f"Expected Equity: ${mc_results['expected_final_equity']:,.2f}")
        print(f"Median Equity:  ${mc_results['median_final_equity']:,.2f}")
        print(f"Worst Case:     ${mc_results['worst_case_equity']:,.2f}")
        print(f"Best Case:      ${mc_results['best_case_equity']:,.2f}")
    else:
        print("Monte Carlo disabled in config. Set backtest.monte_carlo_enabled=true")
    print()

    # ---- Performance Report ----
    print("=" * 56)
    print("  PERFORMANCE ANALYSIS")
    print("=" * 56)
    analyzer = PerformanceAnalyzer(config)
    # Build equity curve and returns from result
    equity_curve = result.equity_curve if hasattr(result, 'equity_curve') else [result.initial_capital, result.final_equity]
    returns = [t.get("pnl_pct", 0) / 100.0 if isinstance(t, dict) else getattr(t, "pnl_pct", 0) / 100.0 for t in result.trades]
    report_text = analyzer.generate_report(result.trades, equity_curve, returns)
    print(report_text)

    # ---- Verdict ----
    print("=" * 56)
    print("  VERDICT")
    print("=" * 56)
    checks = []
    if result.sharpe_ratio > 1.0:
        checks.append("Sharpe > 1.0  PASS")
    else:
        checks.append(f"Sharpe > 1.0  FAIL ({result.sharpe_ratio:.2f})")

    if result.max_drawdown_pct < 20:
        checks.append("Drawdown < 20% PASS")
    else:
        checks.append(f"Drawdown < 20% FAIL ({result.max_drawdown_pct:.2f}%)")

    if result.win_rate > 0.5:
        checks.append("Win rate > 50% PASS")
    else:
        checks.append(f"Win rate > 50% FAIL ({result.win_rate:.1%})")

    if result.profit_factor > 1.5:
        checks.append("Profit Factor > 1.5 PASS")
    else:
        checks.append(f"Profit Factor > 1.5 FAIL ({result.profit_factor:.2f})")

    for c in checks:
        print(f"  {c}")

    print()
    if result.sharpe_ratio > 1.0 and result.max_drawdown_pct < 20 and result.win_rate > 0.5:
        print("RESULT: Strategy is profitable and robust!")
    elif result.sharpe_ratio > 0.5:
        print("RESULT: Moderate. Tune parameters and re-run.")
    else:
        print("RESULT: Needs significant improvement.")

    # Save results
    os.makedirs("data", exist_ok=True)
    with open("data/backtest_results.json", "w") as f:
        json.dump({
            "strategy": strategy.name,
            "symbol": "BTC/USDT",
            "trades": result.total_trades,
            "win_rate": result.win_rate,
            "profit_factor": result.profit_factor,
            "total_return_pct": result.total_return_pct,
            "max_drawdown_pct": result.max_drawdown_pct,
            "sharpe_ratio": result.sharpe_ratio,
            "sortino_ratio": result.sortino_ratio,
            "calmar_ratio": result.calmar_ratio,
            "mc_prob_profit": mc_results.get("prob_profit", 0) if mc_results else 0,
        }, f, indent=2)
    print("Results saved to data/backtest_results.json")


if __name__ == "__main__":
    main()
