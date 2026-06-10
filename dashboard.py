#!/usr/bin/env python3
"""
Harmesh Web Dashboard — Flask app running on http://localhost:5000
Reads data from paper_state.json, paper_trades.csv, BUILD_LOG.txt
"""
import json
import csv
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, render_template_string

app = Flask(__name__)

BASE_DIR = Path.home() / "harmesh"
STATE_FILE = BASE_DIR / "data" / "paper_state.json"
TRADES_FILE = BASE_DIR / "logs" / "paper_trades.csv"
BUILD_LOG = BASE_DIR / "BUILD_LOG.txt"

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Harmesh Trading Bot</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #0d1117;
  color: #c9d1d9;
  padding: 20px;
  min-height: 100vh;
}
/* TOP BAR */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  margin-bottom: 24px;
}
.topbar-left { display: flex; align-items: center; gap: 16px; }
.topbar h1 {
  font-size: 20px;
  font-weight: 700;
  background: linear-gradient(135deg, #58a6ff, #3fb950);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.phase-badge {
  padding: 4px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.phase-paper { background: #1f6feb33; color: #58a6ff; border: 1px solid #1f6feb; }
.phase-live  { background: #3fb95033; color: #3fb950; border: 1px solid #3fb950; }
.topbar-time { font-size: 13px; color: #8b949e; }

/* CARDS */
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}
.card {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 20px;
}
.card-label { font-size: 12px; text-transform: uppercase; color: #8b949e; letter-spacing: 0.8px; margin-bottom: 8px; }
.card-value { font-size: 28px; font-weight: 700; }
.card-value.green { color: #3fb950; }
.card-value.red   { color: #f85149; }
.card-value.white { color: #c9d1d9; }

/* SECTION HEADER */
.section-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
  color: #e6edf3;
}

/* PROGRESS BAR WRAPPER */
.progress-container {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 24px;
}
.progress-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 20px;
  margin-bottom: 16px;
}
.progress-item .label { font-size: 12px; color: #8b949e; margin-bottom: 4px; }
.progress-item .value { font-size: 18px; font-weight: 600; }
.progress-bar-bg {
  height: 8px;
  background: #21262d;
  border-radius: 4px;
  margin-top: 6px;
  overflow: hidden;
}
.progress-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}
.lock-badge {
  display: inline-block;
  padding: 8px 24px;
  border-radius: 6px;
  font-weight: 700;
  font-size: 14px;
  text-align: center;
}
.lock-badge.locked   { background: #f8514933; color: #f85149; border: 1px solid #f85149; }
.lock-badge.unlocked { background: #3fb95033; color: #3fb950; border: 1px solid #3fb950; }

/* TABLES */
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
th {
  text-align: left;
  padding: 10px 12px;
  background: #161b22;
  color: #8b949e;
  font-weight: 600;
  text-transform: uppercase;
  font-size: 11px;
  letter-spacing: 0.5px;
  border-bottom: 2px solid #30363d;
}
td {
  padding: 10px 12px;
  border-bottom: 1px solid #21262d;
}
tr:hover td { background: #1c2128; }
.text-green { color: #3fb950; }
.text-red   { color: #f85149; }
.text-white { color: #c9d1d9; }
.text-right { text-align: right; }
.badge-win  {
  display: inline-block;
  background: #3fb95033;
  color: #3fb950;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
}
.badge-loss {
  display: inline-block;
  background: #f8514933;
  color: #f85149;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
}

/* BUILD LOG */
.log-section {
  margin-top: 24px;
  margin-bottom: 40px;
}
.log-box {
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 16px;
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #8b949e;
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
}
.log-box strong { color: #e6edf3; }
.footer {
  text-align: center;
  font-size: 12px;
  color: #484f58;
  margin-top: 32px;
  padding-bottom: 16px;
}
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-left">
    <h1>Harmesh Trading Bot</h1>
    <span class="phase-badge phase-{{ 'live' if live_mode else 'paper' }}">
      {{ 'LIVE' if live_mode else 'PAPER' }}
    </span>
  </div>
  <div class="topbar-time">{{ now }}</div>
</div>

<div class="cards">
  <div class="card">
    <div class="card-label">Total Equity</div>
    <div class="card-value {{ equity_color }}">${{ "%.2f"|format(equity) }}</div>
  </div>
  <div class="card">
    <div class="card-label">Cash Available</div>
    <div class="card-value white">${{ "%.2f"|format(balance) }}</div>
  </div>
  <div class="card">
    <div class="card-label">Open Positions</div>
    <div class="card-value white">{{ open_count }}</div>
  </div>
  <div class="card">
    <div class="card-label">Total Trades Closed</div>
    <div class="card-value white">{{ closed_count }}</div>
  </div>
</div>

{% set p = progress %}
<div class="progress-container">
  <div class="progress-grid">
    <div class="progress-item">
      <div class="label">Trades</div>
      <div class="value">{{ p.trades }}/200</div>
      <div class="progress-bar-bg">
        <div class="progress-bar-fill" style="width:{{ p.trades_pct }}%;background:#58a6ff"></div>
      </div>
    </div>
    <div class="progress-item">
      <div class="label">Days</div>
      <div class="value">{{ p.days }}/7</div>
      <div class="progress-bar-bg">
        <div class="progress-bar-fill" style="width:{{ p.days_pct }}%;background:#d29922"></div>
      </div>
    </div>
    <div class="progress-item">
      <div class="label">Win Rate</div>
      <div class="value {{ 'text-green' if p.win_rate_met else 'text-red' }}">
        {{ "%.1f"|format(p.win_rate) }}% {{ '(met)' if p.win_rate_met else '(need >55%)' }}
      </div>
      <div class="progress-bar-bg">
        <div class="progress-bar-fill" style="width:{{ p.win_rate_pct }}%;background:{{ '#3fb950' if p.win_rate_met else '#f85149' }}"></div>
      </div>
    </div>
    <div class="progress-item">
      <div class="label">Profit Factor</div>
      <div class="value {{ 'text-green' if p.pf_met else 'text-red' }}">
        {{ "%.2f"|format(p.profit_factor) }} {{ '(met)' if p.pf_met else '(need >1.5)' }}
      </div>
      <div class="progress-bar-bg">
        <div class="progress-bar-fill" style="width:{{ p.pf_pct }}%;background:{{ '#3fb950' if p.pf_met else '#f85149' }}"></div>
      </div>
    </div>
  </div>
  {% if p.all_met %}
    <div class="lock-badge unlocked">PHASE 2 — UNLOCKED</div>
  {% else %}
    <div class="lock-badge locked">PHASE 2 — LOCKED</div>
  {% endif %}
</div>

<div class="section-title">Open Positions</div>
<table>
  <thead>
    <tr>
      <th>Pair</th>
      <th class="text-right">Entry Price</th>
      <th class="text-right">Current Price</th>
      <th class="text-right">P&amp;L %</th>
      <th class="text-right">Units</th>
      <th class="text-right">Stop Loss</th>
      <th class="text-right">Take Profit</th>
    </tr>
  </thead>
  <tbody>
    {% for t in open_trades %}
    <tr>
      <td class="text-white">{{ t.symbol }}</td>
      <td class="text-right text-white">${{ "%.2f"|format(t.entry_price) }}</td>
      <td class="text-right text-white">${{ "%.2f"|format(t.current_price) }}</td>
      <td class="text-right {{ 'text-green' if t.pnl_pct >= 0 else 'text-red' }}">{{ "%+.2f"|format(t.pnl_pct) }}%</td>
      <td class="text-right text-white">{{ "%.6f"|format(t.quantity) }}</td>
      <td class="text-right text-red">${{ "%.2f"|format(t.stop_loss) }}</td>
      <td class="text-right text-green">${{ "%.2f"|format(t.take_profit) }}</td>
    </tr>
    {% else %}
    <tr><td colspan="7" style="text-align:center;color:#484f58;padding:30px;">No open positions</td></tr>
    {% endfor %}
  </tbody>
</table>

<div class="section-title" style="margin-top:28px;">Trade History (Last 20)</div>
<table>
  <thead>
    <tr>
      <th>Date</th>
      <th>Pair</th>
      <th>Side</th>
      <th class="text-right">Entry</th>
      <th class="text-right">Exit</th>
      <th class="text-right">P&amp;L</th>
      <th class="text-right">Return</th>
      <th>Result</th>
      <th>Reason</th>
    </tr>
  </thead>
  <tbody>
    {% for t in closed_trades %}
    <tr>
      <td class="text-white">{{ t.date }}</td>
      <td class="text-white">{{ t.pair }}</td>
      <td class="text-white">{{ t.side|upper }}</td>
      <td class="text-right text-white">${{ "%.2f"|format(t.entry) }}</td>
      <td class="text-right text-white">${{ "%.2f"|format(t.exit) }}</td>
      <td class="text-right {{ 'text-green' if t.pnl >= 0 else 'text-red' }}">${{ "%.2f"|format(t.pnl) }}</td>
      <td class="text-right {{ 'text-green' if t.pnl_pct >= 0 else 'text-red' }}">{{ "%+.2f"|format(t.pnl_pct) }}%</td>
      <td><span class="{{ 'badge-win' if t.pnl >= 0 else 'badge-loss' }}">{{ 'WIN' if t.pnl >= 0 else 'LOSS' }}</span></td>
      <td class="text-white">{{ t.reason }}</td>
    </tr>
    {% else %}
    <tr><td colspan="9" style="text-align:center;color:#484f58;padding:30px;">No closed trades yet</td></tr>
    {% endfor %}
  </tbody>
</table>

<div class="log-section">
  <div class="section-title">Build Log (Last 20 lines)</div>
  <div class="log-box">{{ build_log }}</div>
</div>

<div class="footer">
  Harmesh Trading System v1.0 &mdash; auto-refreshes every 30s
</div>

<script>
setTimeout(function(){ location.reload(); }, 30000);
</script>
</body>
</html>
"""

def load_state():
    """Parse paper_state.json into a dict."""
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"balance": 1000.0, "equity_curve": [1000.0], "open_trades": [],
                "closed_trades": [], "start_time": datetime.utcnow().isoformat()}

def load_trades():
    """Parse paper_trades.csv into a list of dicts (last 20)."""
    rows = []
    try:
        with open(TRADES_FILE, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except (FileNotFoundError, IOError):
        pass
    return rows[-20:]  # last 20

def load_build_log():
    """Return last 20 lines of BUILD_LOG.txt."""
    try:
        with open(BUILD_LOG) as f:
            lines = f.readlines()
        return "".join(lines[-20:])
    except (FileNotFoundError, IOError):
        return "(no build log yet)"

def compute_progress(state):
    """Compute Phase 2 unlock progress."""
    closed = state.get("closed_trades", [])
    total_trades = len(closed)
    start_str = state.get("start_time")
    days = 0
    if start_str:
        try:
            start = datetime.fromisoformat(start_str)
            days = (datetime.utcnow() - start).total_seconds() / 86400
            days = max(0, min(7, int(days)))
        except ValueError:
            days = 0

    wins = sum(1 for t in closed if t.get("pnl", 0) >= 0)
    losses = sum(1 for t in closed if t.get("pnl", 0) < 0)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0

    gross_profit = sum(t.get("pnl", 0) for t in closed if t.get("pnl", 0) > 0)
    gross_loss = abs(sum(t.get("pnl", 0) for t in closed if t.get("pnl", 0) < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)

    return {
        "trades": total_trades,
        "trades_pct": min(100, total_trades / 2),  # /200 *100 = /2
        "days": days,
        "days_pct": min(100, days / 7 * 100),
        "win_rate": win_rate,
        "win_rate_pct": min(100, win_rate),
        "win_rate_met": win_rate > 55,
        "profit_factor": profit_factor,
        "pf_pct": min(100, profit_factor / 1.5 * 100) if profit_factor > 0 else 0,
        "pf_met": profit_factor > 1.5,
        "all_met": total_trades >= 200 and days >= 7 and win_rate > 55 and profit_factor > 1.5,
    }


@app.route("/")
def dashboard():
    state = load_state()
    closed_raw = state.get("closed_trades", [])
    open_raw = state.get("open_trades", [])
    balance = state.get("balance", 1000.0)
    equity_curve = state.get("equity_curve", [balance])
    equity = equity_curve[-1] if equity_curve else balance

    progress = compute_progress(state)
    live_mode = progress["all_met"]

    # Open trades with current price
    last_prices = {}
    for t in open_raw:
        last_prices[t["symbol"]] = t.get("current_price", t["entry_price"])

    open_trades = []
    for t in open_raw:
        sym = t["symbol"]
        current = last_prices.get(sym, t["entry_price"])
        entry = t["entry_price"]
        pnl_pct = ((current - entry) / entry * 100) if entry else 0
        open_trades.append({
            "symbol": sym,
            "entry_price": entry,
            "current_price": current,
            "pnl_pct": pnl_pct,
            "quantity": t.get("quantity", 0),
            "stop_loss": t.get("stop_loss", 0),
            "take_profit": t.get("take_profit", 0),
        })

    # Closed trades
    closed_trades = []
    for t in closed_raw[-20:]:
        closed_trades.append({
            "date": t.get("exit_time", t.get("exit_date", ""))[:10],
            "pair": t["symbol"],
            "side": t.get("side", "long"),
            "entry": t.get("entry_price", 0),
            "exit": t.get("exit_price", 0),
            "pnl": t.get("pnl", 0),
            "pnl_pct": t.get("pnl_pct", 0),
            "reason": t.get("exit_reason", ""),
        })
    closed_trades.reverse()  # newest first

    build_log = load_build_log()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    equity_color = "green" if equity >= state.get("initial_capital", 1000.0) else "red"
    if equity == state.get("initial_capital", 1000.0):
        equity_color = "white"

    return render_template_string(
        HTML_TEMPLATE,
        now=now,
        live_mode=live_mode,
        equity=equity,
        equity_color=equity_color,
        balance=balance,
        open_count=len(open_trades),
        closed_count=len(closed_raw),
        progress=progress,
        open_trades=open_trades,
        closed_trades=closed_trades,
        build_log=build_log,
    )


if __name__ == "__main__":
    print(f"Harmesh Dashboard starting on http://localhost:5000")
    print(f"Reading state from: {STATE_FILE}")
    print(f"Reading trades from: {TRADES_FILE}")
    app.run(host="0.0.0.0", port=5000, debug=False)
