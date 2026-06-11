import json
import csv
import os
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

STATE_FILE = BASE_DIR / "data" / "paper_state.json"
TRADES_FILE = BASE_DIR / "logs" / "paper_trades.csv"
BUILD_LOG = BASE_DIR / "BUILD_LOG.txt"
BACKTEST_RESULTS = BASE_DIR / "data" / "backtest_results.json"
EQUITY_CSV = BASE_DIR / "data" / "backtest_equity.csv"
TRADES_CSV = BASE_DIR / "data" / "backtest_trades.csv"


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_state():
    state = load_json(STATE_FILE)
    return state or {
        "balance": 1000.0,
        "equity_curve": [1000.0],
        "open_trades": [],
        "closed_trades": [],
        "start_time": datetime.now(timezone.utc).isoformat(),
        "initial_capital": 1000.0,
    }


def load_backtest_results():
    return load_json(BACKTEST_RESULTS)


def load_equity_curve():
    try:
        df = pd.read_csv(EQUITY_CSV)
        values = df["equity"].dropna().tolist()
        step = max(1, len(values) // 300)
        return values[::step]
    except (FileNotFoundError, IOError, ValueError):
        return []


def load_trades_csv(path=None, n=50):
    path = path or TRADES_CSV
    try:
        df = pd.read_csv(path)
        return df.tail(n).to_dict("records")
    except (FileNotFoundError, IOError):
        return []


def load_build_log(n=30):
    try:
        with open(BUILD_LOG) as f:
            lines = f.readlines()
        return "".join(lines[-n:])
    except (FileNotFoundError, IOError):
        return "(no build log)"


def compute_progress(state):
    closed = state.get("closed_trades", [])
    total_trades = len(closed)
    start_str = state.get("start_time")
    days = 0
    if start_str:
        try:
            start = datetime.fromisoformat(start_str)
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            days = max(0, min(7, int((datetime.now(timezone.utc) - start).total_seconds() / 86400)))
        except (ValueError, TypeError):
            days = 0

    wins = sum(1 for t in closed if t.get("pnl", 0) > 0)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0

    gross_profit = sum(t.get("pnl", 0) for t in closed if t.get("pnl", 0) > 0)
    gross_loss = abs(sum(t.get("pnl", 0) for t in closed if t.get("pnl", 0) < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)

    all_met = total_trades >= 200 and days >= 7 and win_rate > 55 and profit_factor > 1.5
    reasons = []
    if total_trades < 200:
        reasons.append(f"trades {total_trades}/200")
    if days < 7:
        reasons.append(f"days {days}/7")
    if win_rate <= 55:
        reasons.append(f"WR {win_rate:.1f}% > need 55%")
    if profit_factor <= 1.5:
        reasons.append(f"PF {profit_factor:.2f} > need 1.5")
    reason = ", ".join(reasons) if reasons else "all met"

    return {
        "trades": total_trades,
        "trades_pct": min(100, total_trades / 2),
        "days": days,
        "days_pct": min(100, days / 7 * 100),
        "win_rate": win_rate,
        "win_rate_pct": min(100, win_rate),
        "win_rate_met": win_rate > 55,
        "profit_factor": profit_factor,
        "pf_pct": min(100, profit_factor / 1.5 * 100) if profit_factor > 0 else 0,
        "pf_met": profit_factor > 1.5,
        "all_met": all_met,
        "reason": reason,
    }


def compute_corrected_sharpe(trades, risk_free_rate=0.02):
    if len(trades) < 2:
        return 0.0
    pnls = np.array([t.get("pnl_pct", 0) for t in trades if t.get("pnl") is not None])
    if len(pnls) < 2:
        return 0.0
    excess = pnls - (risk_free_rate * 100 / 365)
    if np.std(excess) == 0:
        return 0.0
    return float(np.mean(excess) / np.std(excess) * np.sqrt(365))


def get_risk_metrics(results, trades):
    if not results:
        return []
    bt = results
    metrics = [
        {"label": "Total Return", "value": f"{bt.get('total_return_pct', 0):+.2f}%",
         "color": "#5cbd6c" if bt.get('total_return_pct', 0) >= 0 else "#ff6b6b",
         "sub": f"${bt.get('initial_capital', 10000):.0f} -> ${bt.get('final_equity', 0):.2f}"},
        {"label": "Max Drawdown", "value": f"{bt.get('max_drawdown_pct', 0):.1f}%",
         "color": "#ff6b6b", "sub": "Peak-to-trough"},
        {"label": "Sharpe Ratio", "value": f"{compute_corrected_sharpe(trades):.2f}",
         "color": "#eacd5c", "sub": "Trade-based (corrected)"},
        {"label": "Win Rate", "value": f"{bt.get('win_rate', 0) * 100:.1f}%",
         "color": "#5cbd6c" if bt.get('win_rate', 0) > 0.4 else "#ff6b6b",
         "sub": f"{bt.get('winning_trades', 0)}W / {bt.get('losing_trades', 0)}L"},
        {"label": "Profit Factor", "value": f"{bt.get('profit_factor', 0):.2f}",
         "color": "#5cbd6c" if bt.get('profit_factor', 0) > 1 else "#ff6b6b",
         "sub": "Gross profit / Gross loss"},
        {"label": "Avg Trade", "value": f"${bt.get('avg_trade', 0):+.2f}",
         "color": "#5c9bdb", "sub": "Per trade expectancy"},
        {"label": "Total Trades", "value": str(bt.get("total_trades", 0)),
         "color": "#b3b1ad", "sub": f"Strategy: {bt.get('strategy_name', 'Harmesh')}"},
        {"label": "Calmar Ratio", "value": f"{bt.get('calmar_ratio', 0):.2f}",
         "color": "#eacd5c", "sub": "Return / Max DD"},
    ]
    return metrics
