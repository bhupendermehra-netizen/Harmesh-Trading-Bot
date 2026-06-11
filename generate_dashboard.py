"""
Phase 4: Institutional Hedge-Fund Style Dashboard Generator
Generates an interactive HTML dashboard with all performance analytics.
"""
import sys, os, json, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import pandas as pd
import numpy as np
from datetime import datetime

print("=" * 70)
print("PHASE 4: GENERATING INSTITUTIONAL DASHBOARD")
print("=" * 70)

# Load backtest results
results_path = "data/backtest_results.json"
if not os.path.exists(results_path):
    print(f"ERROR: {results_path} not found. Run Phase 3 first.")
    sys.exit(1)

with open(results_path) as f:
    results = json.load(f)

# Load equity curve
equity_path = "data/backtest_equity.csv"
equity_df = pd.read_csv(equity_path) if os.path.exists(equity_path) else None

# Load trades
trades_path = "data/backtest_trades.csv"
trades_df = pd.read_csv(trades_path) if os.path.exists(trades_path) else pd.DataFrame()

# Load data
data_path = "data/historical_btc_1h.csv"
data_df = pd.read_csv(data_path)
data_df["timestamp"] = pd.to_datetime(data_df["timestamp"])

print(f"Loaded: {len(trades_df)} trades, {len(equity_df) if equity_df is not None else 0} equity points")

# Compute additional metrics
def compute_metrics(trades_df, equity_df, data_df, results):
    metrics = {}
    
    # Basic stats
    metrics["strategy"] = results.get("strategy", results.get("strategy_name", "HarmeshAdvanced"))
    metrics["symbol"] = results.get("symbol", "BTC/USDT")
    metrics["timeframe"] = results.get("timeframe", "1h")
    metrics["period"] = f"{data_df['timestamp'].min().strftime('%Y-%m-%d')} to {data_df['timestamp'].max().strftime('%Y-%m-%d')}"
    metrics["initial_capital"] = results.get("initial_capital", 10000)
    metrics["final_equity"] = results.get("final_equity", 0)
    metrics["total_return_pct"] = results.get("total_return_pct", 0)
    metrics["total_return"] = results.get("total_return", 0)
    metrics["total_trades"] = results.get("total_trades", 0)
    metrics["winning_trades"] = results.get("winning_trades", 0)
    metrics["losing_trades"] = results.get("losing_trades", 0)
    metrics["win_rate"] = results.get("win_rate", 0) * 100
    metrics["profit_factor"] = results.get("profit_factor", 0)
    metrics["max_drawdown_pct"] = results.get("max_drawdown_pct", 0)
    metrics["sharpe_ratio"] = results.get("sharpe_ratio", 0)
    metrics["sortino_ratio"] = results.get("sortino_ratio", 0)
    metrics["calmar_ratio"] = results.get("calmar_ratio", 0)
    metrics["avg_win"] = results.get("avg_win", 0)
    metrics["avg_loss"] = results.get("avg_loss", 0)
    metrics["avg_trade"] = results.get("avg_trade", 0)
    metrics["expectancy"] = results.get("expectancy", 0)
    
    # Trade analysis
    if len(trades_df) > 0:
        metrics["long_trades"] = len(trades_df[trades_df["side"] == "long"])
        metrics["short_trades"] = len(trades_df[trades_df["side"] == "short"])
        metrics["long_pnl"] = trades_df[trades_df["side"] == "long"]["pnl"].sum()
        metrics["short_pnl"] = trades_df[trades_df["side"] == "short"]["pnl"].sum()
        metrics["long_wr"] = len(trades_df[(trades_df["side"] == "long") & (trades_df["pnl"] > 0)]) / max(metrics["long_trades"], 1) * 100
        metrics["short_wr"] = len(trades_df[(trades_df["side"] == "short") & (trades_df["pnl"] > 0)]) / max(metrics["short_trades"], 1) * 100
        
        # Exit reason breakdown
        exit_counts = trades_df["exit_reason"].value_counts()
        metrics["exit_reasons"] = exit_counts.to_dict()
        
        # Duration stats
        if "entry_time" in trades_df.columns and "exit_time" in trades_df.columns:
            try:
                entry = pd.to_datetime(trades_df["entry_time"])
                exit = pd.to_datetime(trades_df["exit_time"])
                durations = (exit - entry).dt.total_seconds() / 3600
                metrics["avg_duration_h"] = float(durations.mean())
                metrics["median_duration_h"] = float(durations.median())
            except:
                metrics["avg_duration_h"] = 0
                metrics["median_duration_h"] = 0
        
        # Best/worst trades
        best_idx = trades_df["pnl"].idxmax() if len(trades_df) > 0 else None
        worst_idx = trades_df["pnl"].idxmin() if len(trades_df) > 0 else None
        if best_idx is not None:
            metrics["best_trade"] = {
                "pnl": float(trades_df.loc[best_idx, "pnl"]),
                "side": trades_df.loc[best_idx, "side"],
                "entry": str(trades_df.loc[best_idx, "entry_price"]),
                "exit": str(trades_df.loc[best_idx, "exit_price"]),
                "reason": trades_df.loc[best_idx, "exit_reason"],
            }
        if worst_idx is not None:
            metrics["worst_trade"] = {
                "pnl": float(trades_df.loc[worst_idx, "pnl"]),
                "side": trades_df.loc[worst_idx, "side"],
                "entry": str(trades_df.loc[worst_idx, "entry_price"]),
                "exit": str(trades_df.loc[worst_idx, "exit_price"]),
                "reason": trades_df.loc[worst_idx, "exit_reason"],
            }
        
        # Consecutive wins/losses
        pnl_signs = (trades_df["pnl"] > 0).astype(int).values
        max_cons_w = 0
        max_cons_l = 0
        cur_w = 0
        cur_l = 0
        for v in pnl_signs:
            if v == 1:
                cur_w += 1
                cur_l = 0
                max_cons_w = max(max_cons_w, cur_w)
            else:
                cur_l += 1
                cur_w = 0
                max_cons_l = max(max_cons_l, cur_l)
        metrics["max_consecutive_wins"] = max_cons_w
        metrics["max_consecutive_losses"] = max_cons_l
    else:
        metrics["long_trades"] = metrics["short_trades"] = 0
        metrics["long_pnl"] = metrics["short_pnl"] = 0.0
        metrics["long_wr"] = metrics["short_wr"] = 0.0
        metrics["exit_reasons"] = {}
        metrics["avg_duration_h"] = metrics["median_duration_h"] = 0
        metrics["max_consecutive_wins"] = metrics["max_consecutive_losses"] = 0
    
    # Equity curve stats
    if equity_df is not None and len(equity_df) > 1:
        eq = equity_df["equity"].values
        returns = np.diff(eq) / eq[:-1]
        metrics["total_return_from_eq"] = float((eq[-1] - eq[0]) / eq[0] * 100)
        metrics["volatility_pct"] = float(np.std(returns) * np.sqrt(365*24) * 100)
        
        # Underwater plot data
        peak = np.maximum.accumulate(eq)
        dd = (peak - eq) / peak * 100
        metrics["underwater_max"] = float(np.max(dd))
        metrics["underwater_current"] = float(dd[-1])
        
        # Monthly returns from equity
        if data_df is not None and len(data_df) >= len(eq):
            aligned_len = min(len(data_df), len(eq))
            data_df_copy = data_df.iloc[:aligned_len].copy()
            data_df_copy["equity"] = eq[:aligned_len]
            data_df_copy["timestamp"] = pd.to_datetime(data_df_copy["timestamp"])
            data_df_copy["month"] = data_df_copy["timestamp"].dt.to_period("M")
            monthly = data_df_copy.groupby("month")["equity"].agg(["first", "last"])
            monthly["return"] = (monthly["last"] - monthly["first"]) / monthly["first"] * 100
            monthly_returns = monthly["return"].to_dict()
            metrics["monthly_returns"] = {str(k): round(float(v), 2) for k, v in monthly_returns.items()}
        else:
            metrics["monthly_returns"] = {}
    else:
        metrics["total_return_from_eq"] = 0.0
        metrics["volatility_pct"] = 0.0
        metrics["underwater_max"] = 0.0
        metrics["underwater_current"] = 0.0
        metrics["monthly_returns"] = {}
    
    # Sharpe rating
    sharpe = metrics.get("sharpe_ratio", 0)
    if sharpe >= 2.0: metrics["sharpe_rating"] = "Excellent"
    elif sharpe >= 1.5: metrics["sharpe_rating"] = "Very Good"
    elif sharpe >= 1.0: metrics["sharpe_rating"] = "Good"
    elif sharpe >= 0.5: metrics["sharpe_rating"] = "Fair"
    elif sharpe >= 0: metrics["sharpe_rating"] = "Poor"
    else: metrics["sharpe_rating"] = "Negative"
    
    # Profit factor rating
    pf = metrics.get("profit_factor", 0)
    if pf >= 2.0: metrics["pf_rating"] = "Excellent"
    elif pf >= 1.5: metrics["pf_rating"] = "Good"
    elif pf >= 1.0: metrics["pf_rating"] = "Breakeven"
    else: metrics["pf_rating"] = "Losing"
    
    # Win rate rating
    wr = metrics.get("win_rate", 0)
    if wr >= 60: metrics["wr_rating"] = "High"
    elif wr >= 40: metrics["wr_rating"] = "Moderate"
    else: metrics["wr_rating"] = "Low"
    
    return metrics


m = compute_metrics(trades_df, equity_df, data_df, results)

# Build the equity curve JSON for the chart
equity_json = "[]"
if equity_df is not None and len(equity_df) > 1:
    # Downsample to ~200 points for the chart
    eq_len = len(equity_df)
    step = max(1, eq_len // 200)
    sampled = equity_df.iloc[::step]
    equity_json = json.dumps([round(float(v), 2) for v in sampled["equity"].values])

# Build underwater JSON
underwater_json = "[]"
if equity_df is not None and len(equity_df) > 1:
    eq = equity_df["equity"].values
    peak = np.maximum.accumulate(eq)
    dd = (peak - eq) / peak * 100
    step = max(1, len(dd) // 200)
    underwater_json = json.dumps([round(float(v), 2) for v in dd[::step]])

# Build monthly returns JSON
monthly_json = json.dumps(m.get("monthly_returns", {}))

# Build trade PnL distribution JSON
trade_pnls_json = "[]"
trade_labels_json = "[]"
if len(trades_df) > 0:
    trade_pnls_json = json.dumps([round(float(v), 2) for v in trades_df["pnl"].values])
    trade_labels_json = json.dumps([
        f"{row['side']} ${row['pnl']:.0f}" for _, row in trades_df.iterrows()
    ][:50])

# Color scheme
COLORS = {
    "bg": "#0a0e17",
    "card": "#111827",
    "border": "#1e293b",
    "text": "#e2e8f0",
    "muted": "#64748b",
    "green": "#22c55e",
    "red": "#ef4444",
    "blue": "#3b82f6",
    "yellow": "#eab308",
    "accent": "#8b5cf6",
}

def card(title, value, subtitle="", color="blue", icon=""):
    colors = {"green": COLORS["green"], "red": COLORS["red"], "blue": COLORS["blue"], 
              "yellow": COLORS["yellow"], "accent": COLORS["accent"], "muted": COLORS["muted"]}
    c = colors.get(color, COLORS["blue"])
    return f"""
    <div style="background:{COLORS['card']};border:1px solid {COLORS['border']};border-radius:12px;padding:20px;border-left:4px solid {c};">
        <div style="color:{COLORS['muted']};font-size:13px;font-weight:500;text-transform:uppercase;letter-spacing:0.5px;">{icon} {title}</div>
        <div style="color:{COLORS['text']};font-size:28px;font-weight:700;margin-top:8px;">{value}</div>
        {f'<div style="color:{COLORS["muted"]};font-size:13px;margin-top:4px;">{subtitle}</div>' if subtitle else ''}
    </div>"""

def rating_badge(rating):
    colors = {"Excellent": COLORS["green"], "Very Good": COLORS["blue"], "Good": COLORS["blue"],
              "Fair": COLORS["yellow"], "Poor": COLORS["red"], "Negative": COLORS["red"],
              "High": COLORS["green"], "Moderate": COLORS["yellow"], "Low": COLORS["red"],
              "Breakeven": COLORS["yellow"], "Losing": COLORS["red"]}
    c = colors.get(rating, COLORS["muted"])
    return f'<span style="background:{c}22;color:{c};padding:2px 10px;border-radius:99px;font-size:12px;font-weight:600;">{rating}</span>'

# Generate HTML
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Harmesh — Performance Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:{COLORS['bg']}; color:{COLORS['text']}; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; }}
.header {{ background:linear-gradient(135deg,#0f172a,#1e293b); border-bottom:1px solid {COLORS['border']}; padding:24px 32px; }}
.header h1 {{ font-size:24px; font-weight:700; }}
.header .sub {{ color:{COLORS['muted']}; font-size:14px; margin-top:4px; }}
.dashboard {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:16px; padding:24px 32px; }}
.section {{ padding:0 32px 24px; }}
.section h2 {{ font-size:18px; font-weight:600; margin-bottom:16px; color:{COLORS['muted']}; text-transform:uppercase; letter-spacing:0.5px; }}
.chart-grid {{ display:grid; grid-template-columns:2fr 1fr; gap:16px; padding:0 32px 24px; }}
.chart-full {{ padding:0 32px 24px; }}
.chart-box {{ background:{COLORS['card']}; border:1px solid {COLORS['border']}; border-radius:12px; padding:20px; }}
.chart-box h3 {{ font-size:14px; color:{COLORS['muted']}; margin-bottom:12px; font-weight:500; }}
.metrics-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin-top:12px; }}
.metric-item {{ padding:12px; background:{COLORS['bg']}; border-radius:8px; }}
.metric-item .label {{ color:{COLORS['muted']}; font-size:12px; }}
.metric-item .value {{ font-size:18px; font-weight:600; margin-top:2px; }}
.row {{ display:flex; gap:16px; padding:0 32px 24px; flex-wrap:wrap; }}
.row > div {{ flex:1; min-width:200px; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ text-align:left; color:{COLORS['muted']}; font-weight:500; text-transform:uppercase; font-size:11px; padding:8px 12px; border-bottom:1px solid {COLORS['border']}; }}
td {{ padding:8px 12px; border-bottom:1px solid {COLORS['border']}; color:{COLORS['text']}; }}
.pos {{ color:{COLORS['green']}; }}
.neg {{ color:{COLORS['red']}; }}
@media (max-width:768px) {{ .chart-grid {{ grid-template-columns:1fr; }} .dashboard {{ grid-template-columns:1fr 1fr; }} }}
</style>
</head>
<body>

<div class="header">
<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px;">
<div>
<h1>Harmesh Performance Dashboard</h1>
<div class="sub">{m['strategy']} | {m['symbol']} ({m['timeframe']}) | {m['period']}</div>
</div>
<div style="text-align:right;">
<div style="font-size:36px;font-weight:700;color:{'#22c55e' if m['total_return_pct'] >= 0 else '#ef4444'}">{m['total_return_pct']:+.2f}%</div>
<div style="color:{COLORS['muted']};font-size:13px;">${m['initial_capital']:,.0f} → ${m['final_equity']:,.2f}</div>
</div>
</div>
<div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;">
{rating_badge(m['sharpe_rating'])} {rating_badge(m['pf_rating'])} {rating_badge(m['wr_rating'])}
</div>
</div>

<div class="dashboard">
{card('Total Trades', str(m['total_trades']), f"{m['winning_trades']}W / {m['losing_trades']}L", 'blue', '📊')}
{card('Win Rate', f"{m['win_rate']:.1f}%", m['wr_rating'], 'green' if m['win_rate'] >= 40 else 'red', '🎯')}
{card('Profit Factor', f"{m['profit_factor']:.2f}", m['pf_rating'], 'green' if m['profit_factor'] >= 1 else 'red', '💰')}
{card('Max Drawdown', f"{m['max_drawdown_pct']:.1f}%", f"Current: {m.get('underwater_current',0):.1f}%", 'red', '📉')}
{card('Sharpe Ratio', f"{m['sharpe_ratio']:.2f}", m['sharpe_rating'], 'blue', '📈')}
{card('Sortino Ratio', f"{m['sortino_ratio']:.2f}", 'Downside-focused', 'accent', '🛡️')}
{card('Calmar Ratio', f"{m['calmar_ratio']:.2f}", 'Return / Max DD', 'yellow', '⚡')}
{card('Expectancy', f"${m['expectancy']:+.2f}", f"Avg trade: ${m['avg_trade']:+.2f}", 'green' if m['expectancy'] >= 0 else 'red', '📋')}
</div>

<div class="chart-grid">
<div class="chart-box">
<h3>Equity Curve</h3>
<canvas id="equityChart" height="280"></canvas>
</div>
<div class="chart-box">
<h3>Underwater (Drawdown)</h3>
<canvas id="underwaterChart" height="280"></canvas>
</div>
</div>

<div class="chart-grid">
<div class="chart-box">
<h3>PnL Distribution (per trade)</h3>
<canvas id="pnlChart" height="200"></canvas>
</div>
<div class="chart-box">
<h3>Monthly Returns</h3>
<canvas id="monthlyChart" height="200"></canvas>
</div>
</div>

<div class="section">
<h2>Trade Details</h2>
<div style="background:{COLORS['card']};border:1px solid {COLORS['border']};border-radius:12px;overflow-x:auto;">
<table>
<thead>
<tr>
<th>#</th><th>Side</th><th>Entry</th><th>Exit</th><th>Entry Price</th><th>Exit Price</th><th>PnL</th><th>PnL%</th><th>Reason</th>
</tr>
</thead>
<tbody>
"""

# Add trade rows
trades = results.get("trades", [])
for i, t in enumerate(trades[:100]):
    pnl = t.get("pnl", 0)
    cls = "pos" if pnl > 0 else "neg"
    html += f"""<tr>
<td>{i+1}</td>
<td style="text-transform:uppercase;font-weight:600;">{t.get('side','')}</td>
<td>{t.get('entry_time','')[:19]}</td>
<td>{t.get('exit_time','')[:19]}</td>
<td>${t.get('entry_price',0):.2f}</td>
<td>${t.get('exit_price',0):.2f}</td>
<td class="{cls}">${pnl:+.2f}</td>
<td class="{cls}">{t.get('pnl_pct',0):+.2f}%</td>
<td>{t.get('exit_reason','')}</td>
</tr>"""

if len(trades) > 100:
    html += f'<tr><td colspan="9" style="text-align:center;color:{COLORS["muted"]};">... and {len(trades)-100} more trades</td></tr>'

html += """
</tbody>
</table>
</div>
</div>

<div class="section">
<h2>Risk & Performance Metrics</h2>
<div style="background:{COLORS['card']};border:1px solid {COLORS['border']};border-radius:12px;padding:20px;">
<div class="metrics-grid">
"""

risk_metrics = [
    ("Total Return", f"{m['total_return_pct']:+.2f}%", "Return including open positions"),
    ("Annualized Return", f"{m.get('total_return_from_eq',0):+.2f}%", "Annualized from equity curve"),
    ("Volatility (ann.)", f"{m.get('volatility_pct',0):.2f}%", "Annualized std dev of returns"),
    ("Max Drawdown", f"{m['max_drawdown_pct']:.2f}%", "Peak-to-trough decline"),
    ("Sharpe Ratio", f"{m['sharpe_ratio']:.2f}", f"Rating: {m['sharpe_rating']}"),
    ("Sortino Ratio", f"{m['sortino_ratio']:.2f}", "Downside deviation only"),
    ("Calmar Ratio", f"{m['calmar_ratio']:.2f}", "Return / Max DD"),
    ("Profit Factor", f"{m['profit_factor']:.2f}", "Gross profit / gross loss"),
    ("Win Rate", f"{m['win_rate']:.1f}%", f"{m['winning_trades']} of {m['total_trades']}"),
    ("Avg Win", f"${m['avg_win']:+.2f}", "Average winning trade"),
    ("Avg Loss", f"${m['avg_loss']:+.2f}", "Average losing trade"),
    ("Avg Trade", f"${m['avg_trade']:+.2f}", "Average trade PnL"),
    ("Best Trade", f"${m.get('best_trade',{}).get('pnl',0):+.2f}", f"{m.get('best_trade',{}).get('side','')} @ ${m.get('best_trade',{}).get('entry',0)}"),
    ("Worst Trade", f"${m.get('worst_trade',{}).get('pnl',0):+.2f}", f"{m.get('worst_trade',{}).get('side','')} @ ${m.get('worst_trade',{}).get('entry',0)}"),
    ("Avg Duration", f"{m.get('avg_duration_h',0):.1f}h", f"Median: {m.get('median_duration_h',0):.1f}h"),
    ("Max Consec Wins", str(m.get('max_consecutive_wins',0)), "Best streak"),
    ("Max Consec Losses", str(m.get('max_consecutive_losses',0)), "Worst streak"),
    ("Expectancy", f"${m['expectancy']:+.2f}", "Expected value per trade"),
]

for label, val, sub in risk_metrics:
    is_pos = val.startswith("+") and label not in ["Max Drawdown", "Volatility"]
    is_neg = val.startswith("-")
    c = COLORS["green"] if is_pos else (COLORS["red"] if is_neg else COLORS["text"])
    html += f"""<div class="metric-item">
<div class="label">{label}</div>
<div class="value" style="color:{c};">{val}</div>
<div style="color:{COLORS['muted']};font-size:11px;margin-top:2px;">{sub}</div>
</div>"""

html += """
</div>
</div>
</div>

<div class="section" style="padding-bottom:32px;">
<h2>Trade Statistics by Side</h2>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
"""

for side in ["long", "short"]:
    pnl_val = m.get(f"{side}_pnl", 0)
    wr_val = m.get(f"{side}_wr", 0)
    count = m.get(f"{side}_trades", 0)
    cls = "pos" if pnl_val > 0 else "neg"
    html += f"""<div style="background:{COLORS['card']};border:1px solid {COLORS['border']};border-radius:12px;padding:16px;">
<div style="font-size:14px;font-weight:600;text-transform:uppercase;color:{COLORS['muted']};margin-bottom:8px;">{side.upper()} Trades</div>
<div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span style="color:{COLORS['muted']};">Count</span><span>{count}</span></div>
<div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span style="color:{COLORS['muted']};">Win Rate</span><span>{wr_val:.1f}%</span></div>
<div style="display:flex;justify-content:space-between;"><span style="color:{COLORS['muted']};">Net P&L</span><span class="{cls}">${pnl_val:+.2f}</span></div>
</div>"""

html += """
</div>
</div>

<script>
const equityData = """ + equity_json + """;
const underwaterData = """ + underwater_json + """;
const monthlyData = """ + monthly_json + """;
const tradePnls = """ + trade_pnls_json + """;
const tradeLabels = """ + trade_labels_json + """;

// Helper: gradient fill
function gradient(ctx, c1, c2) {
    const g = ctx.createLinearGradient(0,0,0,280);
    g.addColorStop(0, c1);
    g.addColorStop(1, c2);
    return g;
}

// Equity curve
new Chart(document.getElementById('equityChart'), {
    type: 'line',
    data: {
        labels: equityData.map((_,i) => i),
        datasets: [{
            data: equityData,
            borderColor: '#3b82f6',
            backgroundColor: gradient(document.getElementById('equityChart').getContext('2d'), 'rgba(59,130,246,0.15)', 'rgba(59,130,246,0)'),
            fill: true,
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
            x: { display: false },
            y: { 
                grid: { color: '#1e293b' },
                ticks: { color: '#64748b', callback: v => '$' + v.toLocaleString() }
            }
        }
    }
});

// Underwater
new Chart(document.getElementById('underwaterChart'), {
    type: 'line',
    data: {
        labels: underwaterData.map((_,i) => i),
        datasets: [{
            data: underwaterData,
            borderColor: '#ef4444',
            backgroundColor: gradient(document.getElementById('underwaterChart').getContext('2d'), 'rgba(239,68,68,0.2)', 'rgba(239,68,68,0)'),
            fill: true,
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
            x: { display: false },
            y: { 
                grid: { color: '#1e293b' },
                ticks: { color: '#64748b', callback: v => v.toFixed(1) + '%' },
                reverse: true
            }
        }
    }
});

// PnL Distribution
new Chart(document.getElementById('pnlChart'), {
    type: 'bar',
    data: {
        labels: tradePnls.map((_,i) => i+1),
        datasets: [{
            data: tradePnls,
            backgroundColor: tradePnls.map(v => v >= 0 ? '#22c55e' : '#ef4444'),
            borderWidth: 0,
            borderRadius: 2,
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { 
            legend: { display: false },
            tooltip: { callbacks: { label: ctx => '$' + ctx.parsed.y.toFixed(2) } }
        },
        scales: {
            x: { display: false },
            y: { 
                grid: { color: '#1e293b' },
                ticks: { color: '#64748b', callback: v => '$' + v }
            }
        }
    }
});

// Monthly Returns
new Chart(document.getElementById('monthlyChart'), {
    type: 'bar',
    data: {
        labels: Object.keys(monthlyData),
        datasets: [{
            data: Object.values(monthlyData),
            backgroundColor: Object.values(monthlyData).map(v => v >= 0 ? '#22c55e' : '#ef4444'),
            borderWidth: 0,
            borderRadius: 4,
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { 
            legend: { display: false },
            tooltip: { callbacks: { label: ctx => ctx.parsed.y.toFixed(2) + '%' } }
        },
        scales: {
            x: { 
                grid: { color: '#1e293b' },
                ticks: { color: '#64748b', maxRotation: 45 }
            },
            y: { 
                grid: { color: '#1e293b' },
                ticks: { color: '#64748b', callback: v => v.toFixed(1) + '%' }
            }
        }
    }
});
</script>

<div style="text-align:center;padding:16px 32px;color:#475569;font-size:12px;border-top:1px solid #1e293b;">
Harmesh Trading System | Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} | All data from corrected backtest
</div>

</body>
</html>"""

# Write the dashboard
out_path = "dashboard.html"
with open(out_path, "w") as f:
    f.write(html)
print(f"Dashboard written to {out_path}")

file_size = os.path.getsize(out_path)
print(f"File size: {file_size:,} bytes")
print("PHASE 4: DASHBOARD GENERATED ✓")
