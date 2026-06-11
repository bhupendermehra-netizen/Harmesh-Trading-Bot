#!/usr/bin/env python3
"""
Harmesh Web Dashboard — corrected after deep audit
Flask app on http://localhost:5000
Shows live paper state + corrected backtest analytics with Chart.js
"""
import json
import csv
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import math

from flask import Flask, render_template_string

app = Flask(__name__)

BASE_DIR = Path.home() / "harmesh"
STATE_FILE = BASE_DIR / "data" / "paper_state.json"
TRADES_FILE = BASE_DIR / "logs" / "paper_trades.csv"
BUILD_LOG = BASE_DIR / "BUILD_LOG.txt"
BACKTEST_RESULTS = BASE_DIR / "data" / "backtest_results.json"
EQUITY_CSV = BASE_DIR / "data" / "backtest_equity.csv"

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Harmesh Trading Bot</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
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
  flex-wrap: wrap;
  gap: 12px;
}
.topbar-left { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
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
.card-sub { font-size: 12px; color: #484f58; margin-top: 4px; }

.section-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
  color: #e6edf3;
}

/* CHART */
.chart-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}
.chart-box {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 20px;
}
.chart-box h3 { font-size: 13px; color: #8b949e; margin-bottom: 12px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }
@media (max-width:768px) { .chart-row { grid-template-columns: 1fr; } }

/* PROGRESS */
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
.text-center { text-align: center; }
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

/* METRICS GRID */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}
.metric-item {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 16px;
}
.metric-item .label { font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; }
.metric-item .value { font-size: 22px; font-weight: 700; margin-top: 4px; }
.metric-item .sub { font-size: 11px; color: #484f58; margin-top: 2px; }

/* LOG */
.log-section { margin-top: 24px; margin-bottom: 40px; }
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
.tabs { display: flex; gap: 4px; margin-bottom: 20px; flex-wrap: wrap; }
.tab {
  padding: 8px 20px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  background: #21262d;
  color: #8b949e;
  border: 1px solid #30363d;
}
.tab.active { background: #1f6feb33; color: #58a6ff; border-color: #1f6feb; }
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-left">
    <h1>Harmesh Trading Bot</h1>
    <span class="phase-badge phase-{{ 'live' if live_mode else 'paper' }}">
      {{ 'LIVE' if live_mode else 'PAPER' }}
    </span>
    <span style="font-size:12px;color:#8b949e;">v2.0 — bug-fixed audit</span>
  </div>
  <div class="topbar-time">{{ now }}</div>
</div>

<div class="cards">
  <div class="card">
    <div class="card-label">Total Equity</div>
    <div class="card-value {{ equity_color }}">${{ "%.2f"|format(equity) }}</div>
    <div class="card-sub">Initial: ${{ "%.0f"|format(initial_capital) }}</div>
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
  <div class="card">
    <div class="card-label">Win Rate</div>
    <div class="card-value {{ 'green' if bt_win_rate > 40 else 'red' }}">{{ "%.1f"|format(bt_win_rate) }}%</div>
    <div class="card-sub">Backtest (corrected)</div>
  </div>
  <div class="card">
    <div class="card-label">Profit Factor</div>
    <div class="card-value {{ 'green' if bt_profit_factor >= 1 else 'red' }}">{{ "%.2f"|format(bt_profit_factor) }}</div>
    <div class="card-sub">Backtest (corrected)</div>
  </div>
</div>

<!-- CHARTS -->
<div class="chart-row">
  <div class="chart-box">
    <h3>Equity Curve — Backtest (Corrected)</h3>
    <canvas id="equityChart" height="250"></canvas>
  </div>
  <div class="chart-box">
    <h3>Underwater Drawdown</h3>
    <canvas id="underwaterChart" height="250"></canvas>
  </div>
</div>

<!-- METRICS -->
<div class="section-title">Risk-Adjusted Performance (Corrected Backtest)</div>
<div class="metrics-grid">
  {% for m in metrics %}
  <div class="metric-item">
    <div class="label">{{ m.label }}</div>
    <div class="value" style="color:{{ m.color }}">{{ m.value }}</div>
    <div class="sub">{{ m.sub }}</div>
  </div>
  {% endfor %}
</div>

<!-- PROGRESS -->
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
    <div class="lock-badge locked">PHASE 2 — LOCKED ({{ p.reason }})</div>
  {% endif %}
</div>

<!-- TABLES -->
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
  Harmesh v2.0 — Deep Audit Edition | Auto-refresh every 30s | All backtest metrics corrected for signal/accounting bugs
</div>

<script>
const equityData = {{ equity_json|safe }};
const underwaterData = {{ underwater_json|safe }};

function gradient(ctx, c1, c2) {
  const g = ctx.createLinearGradient(0,0,0,250);
  g.addColorStop(0, c1); g.addColorStop(1, c2);
  return g;
}

const eqCtx = document.getElementById('equityChart').getContext('2d');
new Chart(eqCtx, {
  type: 'line',
  data: {
    labels: equityData.map((_,i) => i),
    datasets: [{
      data: equityData,
      borderColor: '#3fb950',
      backgroundColor: gradient(eqCtx, 'rgba(63,185,80,0.12)', 'rgba(63,185,80,0)'),
      fill: true, borderWidth: 2, pointRadius: 0, tension: 0.3,
    }]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false },
      tooltip: { callbacks: { label: ctx => '$' + ctx.parsed.y.toLocaleString(undefined,{minimumFractionDigits:2}) } }
    },
    scales: {
      x: { display: false },
      y: { grid: { color: '#21262d' }, ticks: { color: '#8b949e', callback: v => '$' + v.toLocaleString() } }
    }
  }
});

const uwCtx = document.getElementById('underwaterChart').getContext('2d');
new Chart(uwCtx, {
  type: 'line',
  data: {
    labels: underwaterData.map((_,i) => i),
    datasets: [{
      data: underwaterData,
      borderColor: '#f85149',
      backgroundColor: gradient(uwCtx, 'rgba(248,81,73,0.15)', 'rgba(248,81,73,0)'),
      fill: true, borderWidth: 2, pointRadius: 0, tension: 0.3,
    }]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { display: false },
      y: { grid: { color: '#21262d' }, ticks: { color: '#8b949e', callback: v => v.toFixed(1) + '%' }, reverse: true }
    }
  }
});

setTimeout(function(){ location.reload(); }, 30000);
</script>
</body>
</html>"""


def load_state():
    """Parse paper_state.json into a dict."""
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"balance": 1000.0, "equity_curve": [1000.0], "open_trades": [],
                "closed_trades": [], "start_time": datetime.utcnow().isoformat(),
                "initial_capital": 1000.0}


def load_backtest_results():
    """Load corrected backtest results."""
    try:
        with open(BACKTEST_RESULTS) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_equity_curve():
    """Load equity curve from CSV."""
    try:
        with open(EQUITY_CSV) as f:
            lines = f.readlines()[1:]  # skip header
        values = [float(line.strip()) for line in lines if line.strip()]
        # Downsample for chart
        step = max(1, len(values) // 250)
        return values[::step]
    except (FileNotFoundError, IOError, ValueError):
        return []


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
    return rows[-20:]


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

    all_met = total_trades >= 200 and days >= 7 and win_rate > 55 and profit_factor > 1.5
    reasons = []
    if total_trades < 200: reasons.append(f"trades {total_trades}/200")
    if days < 7: reasons.append(f"days {days}/7")
    if win_rate <= 55: reasons.append(f"WR {win_rate:.1f}% > need 55%")
    if profit_factor <= 1.5: reasons.append(f"PF {profit_factor:.2f} > need 1.5")
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


@app.route("/")
def dashboard():
    state = load_state()
    bt = load_backtest_results()

    closed_raw = state.get("closed_trades", [])
    open_raw = state.get("open_trades", [])
    balance = state.get("balance", 1000.0)
    initial_capital = state.get("initial_capital", 1000.0)
    equity_curve = state.get("equity_curve", [balance])
    equity = equity_curve[-1] if equity_curve else balance

    progress = compute_progress(state)
    live_mode = progress["all_met"]

    # Corrected backtest metrics
    bt_win_rate = bt.get("win_rate", 0) * 100
    bt_profit_factor = bt.get("profit_factor", 0)
    bt_sharpe = bt.get("sharpe_ratio", 0)
    bt_sortino = bt.get("sortino_ratio", 0)
    bt_max_dd = bt.get("max_drawdown_pct", 0)
    bt_return = bt.get("total_return_pct", 0)
    bt_avg_trade = bt.get("avg_trade", 0)

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
            "pair": t.get("symbol", "BTC/USDT"),
            "side": t.get("side", "long"),
            "entry": t.get("entry_price", 0),
            "exit": t.get("exit_price", 0),
            "pnl": t.get("pnl", 0),
            "pnl_pct": t.get("pnl_pct", 0),
            "reason": t.get("exit_reason", ""),
        })
    closed_trades.reverse()

    build_log = load_build_log()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    equity_color = "green" if equity >= initial_capital else "red"
    if equity == initial_capital:
        equity_color = "white"

    # Equity curve data for chart
    eq_values = load_equity_curve()
    equity_json = json.dumps(eq_values)

    # Underwater chart
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

    # Metrics for display
    metrics = [
        {"label": "Total Return", "value": f"{bt_return:+.2f}%",
         "color": "#3fb950" if bt_return >= 0 else "#f85149",
         "sub": f"${bt.get('initial_capital',10000):.0f} → ${bt.get('final_equity',0):.2f}"},
        {"label": "Max Drawdown", "value": f"{bt_max_dd:.1f}%",
         "color": "#f85149", "sub": "Peak-to-trough"},
        {"label": "Sharpe Ratio", "value": f"{bt_sharpe:.2f}",
         "color": "#d2a8ff" if bt_sharpe >= 1 else ( "#58a6ff" if bt_sharpe > 0 else "#f85149"),
         "sub": "Corrected (hourly returns)"},
        {"label": "Sortino Ratio", "value": f"{bt_sortino:.2f}",
         "color": "#58a6ff", "sub": "Downside deviation"},
        {"label": "Win Rate", "value": f"{bt_win_rate:.1f}%",
         "color": "#f85149" if bt_win_rate < 40 else "#3fb950",
         "sub": f"{bt.get('winning_trades',0)}W / {bt.get('losing_trades',0)}L"},
        {"label": "Profit Factor", "value": f"{bt_profit_factor:.2f}",
         "color": "#f85149" if bt_profit_factor < 1 else "#3fb950",
         "sub": "Gross profit / Gross loss"},
        {"label": "Avg Trade", "value": f"${bt_avg_trade:+.2f}",
         "color": "#d29922", "sub": "Per trade expectancy"},
        {"label": "Trades", "value": str(bt.get("total_trades", 0)),
         "color": "#c9d1d9", "sub": "Total backtest"},
    ]

    return render_template_string(
        HTML_TEMPLATE,
        now=now,
        live_mode=live_mode,
        equity=equity,
        equity_color=equity_color,
        balance=balance,
        initial_capital=initial_capital,
        open_count=len(open_trades),
        closed_count=len(closed_raw),
        bt_win_rate=bt_win_rate,
        bt_profit_factor=bt_profit_factor,
        progress=progress,
        open_trades=open_trades,
        closed_trades=closed_trades,
        build_log=build_log,
        metrics=metrics,
        equity_json=equity_json,
        underwater_json=underwater_json,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
