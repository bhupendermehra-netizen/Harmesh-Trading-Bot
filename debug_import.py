"""Debug: check imports."""
import sys
print("start", flush=True)
sys.stdout.flush()
try:
    from engine.backtest import BacktestEngine
    print("engine ok", flush=True)
    from engine.backtest_strategy import BacktestStrategy
    print("strategy ok", flush=True)
except Exception as e:
    print(f"ERROR: {e}", flush=True)
print("done", flush=True)
