#!/usr/bin/env python3
"""
Harmesh Dashboard Data Generator
Reads all bot data files and produces data/dashboard.json
Run this before git push to refresh the dashboard.
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

BASE = Path.home() / "harmesh"
DATA = BASE / "data"
OUTPUT = DATA / "dashboard.json"

def load_json(path):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None

def build():
    print("[*] Generating Harmesh dashboard data...")

    # Load all data sources
    paper = load_json(DATA / "paper_state.json")
    opt_results = load_json(DATA / "optimization_results.json")
    backtest = load_json(DATA / "backtest_results.json")
    config = load_json(BASE / "config.json")
    build_log = load_lines(BASE / "BUILD_LOG.txt")

    # Build dashboard payload
    dashboard = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "system": {
            "name": config.get("system", {}).get("name", "Harmesh Trading System"),
            "version": config.get("system", {}).get("version", "2.0.0"),
            "mode": config.get("system", {}).get("mode", "paper_advanced"),
        },
        "phase": extract_phase(build_log),
        "paper": extract_paper(paper),
        "backtest": extract_backtest(backtest),
        "optimization": extract_optimization(opt_results),
        "config": {
            "exchange": config.get("exchange", {}).get("name", "binance"),
            "sandbox": config.get("exchange", {}).get("sandbox", True),
            "initial_capital": config.get("paper", {}).get("initial_capital", 1000),
            "min_trades_for_upgrade": config.get("paper", {}).get("min_trades_for_upgrade", 200),
            "win_rate_threshold": config.get("paper", {}).get("win_rate_threshold", 0.55),
            "profit_factor_threshold": config.get("paper", {}).get("profit_factor_threshold", 1.5),
            "fusion_method": config.get("strategy_advanced", {}).get("fusion_method", "weighted"),
        },
    }

    with open(OUTPUT, "w") as f:
        json.dump(dashboard, f, indent=2, default=str)

    size = os.path.getsize(OUTPUT)
    print(f"[+] Written: {OUTPUT} ({size:,} bytes)")
    return dashboard

def load_lines(path):
    if path.exists():
        with open(path) as f:
            return f.read()
    return ""

def extract_phase(log_text):
    """Parse phase from BUILD_LOG"""
    if "PHASE 2 UNLOCKED" in log_text or "MODE: LIVE" in log_text:
        return "LIVE"
    if "Unlock Phase 2" in log_text:
        return "PHASE 2"
    return "PHASE 1 (Paper)"

def extract_paper(paper):
    if not paper:
        return {
            "balance": None,
            "equity_curve": [],
            "open_trades": [],
            "closed_trades": [],
            "total_trades": 0,
            "win_rate": None,
        }

    equity = paper.get("equity_curve", [])
    initial = equity[0] if equity else 1000
    current = equity[-1] if equity else initial
    total_return = ((current - initial) / initial * 100) if initial else 0

    closed = paper.get("closed_trades", [])
    wins = sum(1 for t in closed if t.get("pnl", 0) > 0)
    total_closed = len(closed)

    return {
        "balance": round(paper.get("balance", 0), 2),
        "initial_capital": round(initial, 2),
        "total_return_pct": round(total_return, 2),
        "equity_curve": equity,
        "open_trades": paper.get("open_trades", []),
        "closed_trades": closed,
        "total_trades": total_closed,
        "win_rate": round(wins / total_closed * 100, 1) if total_closed > 0 else None,
    }

def extract_backtest(bt):
    if not bt:
        return None
    return {
        "win_rate": round(bt.get("win_rate", 0) * 100, 1),
        "profit_factor": round(bt.get("profit_factor", 0), 2),
        "total_return_pct": round(bt.get("total_return_pct", 0), 2),
        "max_drawdown_pct": round(bt.get("max_drawdown_pct", 0), 1),
        "sharpe_ratio": round(bt.get("sharpe_ratio", 0), 2),
        "sortino_ratio": round(bt.get("sortino_ratio", 0), 2),
        "calmar_ratio": round(bt.get("calmar_ratio", 0), 2),
        "mc_prob_profit": round(bt.get("mc_prob_profit", 0) * 100, 1),
        "trades": bt.get("trades", 0),
        "strategy": bt.get("strategy", "HarmeshAdvanced"),
        "symbol": bt.get("symbol", "BTC/USDT"),
    }

def extract_optimization(opt):
    if not opt:
        return None

    best = opt.get("best_overall", {})
    combos = opt.get("combo_results", [])

    strategies = {}
    for name in ["trend_following", "mean_reversion", "volatility_breakout"]:
        entries = opt.get("best_per_strategy", {}).get(name, [])
        if entries:
            best_entry = entries[0]
            strategies[name] = {
                "score": round(best_entry.get("score", 0), 2),
                "win_rate": round(best_entry.get("win_rate", 0) * 100, 1),
                "profit_factor": round(best_entry.get("profit_factor", 0), 2),
                "total_return_pct": round(best_entry.get("total_return_pct", 0), 2),
                "max_drawdown_pct": round(best_entry.get("max_drawdown_pct", 0), 1),
                "sharpe_ratio": round(best_entry.get("sharpe_ratio", 0), 2),
                "total_trades": best_entry.get("total_trades", 0),
                "params": best_entry.get("params", {}),
            }

    combo_list = []
    for c in combos:
        combo_list.append({
            "name": " + ".join(c.get("combo", [])),
            "score": round(c.get("score", 0), 2),
            "win_rate": round(c.get("win_rate", 0) * 100, 1),
            "profit_factor": round(c.get("profit_factor", 0), 2),
            "total_return_pct": round(c.get("total_return_pct", 0), 2),
            "max_drawdown_pct": round(c.get("max_drawdown_pct", 0), 1),
            "sharpe_ratio": round(c.get("sharpe_ratio", 0), 2),
            "total_trades": c.get("total_trades", 0),
        })

    return {
        "strategies": strategies,
        "combos": combo_list,
        "best_overall": {
            "name": " + ".join(best.get("combo", [])),
            "score": round(best.get("score", 0), 2),
            "win_rate": round(best.get("win_rate", 0) * 100, 1),
            "profit_factor": round(best.get("profit_factor", 0), 2),
            "total_return_pct": round(best.get("total_return_pct", 0), 2),
            "max_drawdown_pct": round(best.get("max_drawdown_pct", 0), 1),
            "sharpe_ratio": round(best.get("sharpe_ratio", 0), 2),
            "total_trades": best.get("total_trades", 0),
        },
        "timestamp": opt.get("timestamp", ""),
        "candles": opt.get("data", {}).get("candles", 0),
        "data_range": opt.get("data", {}).get("range", ""),
    }

if __name__ == "__main__":
    build()
