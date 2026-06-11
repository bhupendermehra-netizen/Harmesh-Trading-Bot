from flask import Blueprint, render_template, jsonify
from datetime import datetime, timezone
import json

from app.utils import (
    load_state, load_backtest_results, load_equity_curve,
    load_trades_csv, load_build_log, compute_progress, get_risk_metrics
)

dashboard_bp = Blueprint("dashboard", __name__, template_folder="templates")


@dashboard_bp.route("/")
def dashboard():
    state = load_state()
    bt = load_backtest_results()
    trades_csv = load_trades_csv()

    closed_raw = state.get("closed_trades", [])
    open_raw = state.get("open_trades", [])
    balance = state.get("balance", 1000.0)
    initial_capital = state.get("initial_capital", 1000.0)
    equity_curve = state.get("equity_curve", [balance])
    equity = equity_curve[-1] if equity_curve else balance

    progress = compute_progress(state)
    live_mode = progress["all_met"]
    equity_color = "green" if equity > initial_capital else ("red" if equity < initial_capital else "white")

    open_trades = []
    for t in open_raw:
        current = t.get("current_price", t["entry_price"])
        entry = t["entry_price"]
        pnl_pct = ((current - entry) / entry * 100) if entry else 0
        open_trades.append({
            "symbol": t["symbol"], "entry_price": entry,
            "current_price": current, "pnl_pct": pnl_pct,
            "quantity": t.get("quantity", 0),
            "stop_loss": t.get("stop_loss", 0),
            "take_profit": t.get("take_profit", 0),
        })

    closed_trades = []
    for t in reversed(closed_raw[-30:]):
        closed_trades.append({
            "date": t.get("exit_time", t.get("exit_date", ""))[:10],
            "pair": t.get("symbol", "BTC/USDT"),
            "side": t.get("side", "long"),
            "entry": t.get("entry_price", 0),
            "exit": t.get("exit_price", 0),
            "pnl": t.get("pnl", 0),
            "pnl_pct": t.get("pnl_pct", 0),
            "reason": t.get("exit_reason", ""),
        })

    bt_trades = bt.get("trades", [])
    metrics = get_risk_metrics(bt, bt_trades)
    eq_values = load_equity_curve()
    equity_json = json.dumps(eq_values)

    if eq_values and len(eq_values) > 1:
        peak = []
        current_peak = eq_values[0]
        for v in eq_values:
            current_peak = max(current_peak, v)
            peak.append(current_peak)
        dd = [(peak[i] - eq_values[i]) / peak[i] * 100 if peak[i] > 0 else 0 for i in range(len(eq_values))]
    else:
        dd = []
    underwater_json = json.dumps(dd)

    bt_trades_json = json.dumps([
        {"pnl": t.get("pnl", 0), "side": t.get("side", "long"),
         "entry": t.get("entry_price", 0), "exit": t.get("exit_price", 0),
         "exit_reason": t.get("exit_reason", ""), "pnl_pct": t.get("pnl_pct", 0)}
        for t in bt_trades[-100:]
    ])

    return render_template("dashboard.html",
        now=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        live_mode=live_mode, equity=equity, equity_color=equity_color,
        balance=balance, initial_capital=initial_capital,
        open_count=len(open_trades), closed_count=len(closed_raw),
        progress=progress, open_trades=open_trades, closed_trades=closed_trades,
        build_log=load_build_log(), metrics=metrics,
        equity_json=equity_json, underwater_json=underwater_json,
        bt_trades_json=bt_trades_json,
    )


@dashboard_bp.route("/api/status")
def api_status():
    state = load_state()
    bt = load_backtest_results()
    return jsonify({
        "paper": {
            "balance": state.get("balance", 0),
            "open_trades": len(state.get("open_trades", [])),
            "closed_trades": len(state.get("closed_trades", [])),
        },
        "backtest": {
            "win_rate": bt.get("win_rate", 0),
            "profit_factor": bt.get("profit_factor", 0),
            "total_return_pct": bt.get("total_return_pct", 0),
            "total_trades": bt.get("total_trades", 0),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
