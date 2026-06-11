import json
import os
import sys
from pathlib import Path


def validate_config(path=None):
    if path is None:
        path = Path(__file__).resolve().parent.parent / "config.json"

    if not os.path.exists(path):
        print(f"[VALIDATOR] Config not found: {path}")
        return False

    with open(path) as f:
        config = json.load(f)

    errors = []

    required_keys = ["system", "exchange", "paper", "trading", "risk", "backtest"]
    for key in required_keys:
        if key not in config:
            errors.append(f"Missing required section: '{key}'")

    if "exchange" in config:
        ex = config["exchange"]
        if "name" not in ex:
            errors.append("exchange.name is required")
        if ex.get("sandbox", True) and not ex.get("api_key"):
            pass  # sandbox mode without API key is OK

    if "trading" in config:
        tr = config["trading"]
        if "symbols" not in tr or not tr["symbols"]:
            errors.append("trading.symbols must have at least one symbol")
        if tr.get("timeframe") not in ("1m", "5m", "15m", "30m", "1h", "4h", "1d"):
            errors.append(f"trading.timeframe '{tr.get('timeframe')}' is not standard")

    if "backtest" in config:
        bt = config["backtest"]
        if bt.get("initial_capital", 0) <= 0:
            errors.append("backtest.initial_capital must be positive")

    if "risk" in config:
        rk = config["risk"]
        if rk.get("max_open_trades", 0) < 1:
            errors.append("risk.max_open_trades must be >= 1")
        if not (0 < rk.get("max_drawdown_pct", 0.25) < 1):
            errors.append("risk.max_drawdown_pct should be between 0 and 1")

    if errors:
        print(f"[VALIDATOR] {len(errors)} config error(s):")
        for e in errors:
            print(f"  - {e}")
        return False

    print("[VALIDATOR] Config validation passed")
    return True


if __name__ == "__main__":
    success = validate_config()
    sys.exit(0 if success else 1)
