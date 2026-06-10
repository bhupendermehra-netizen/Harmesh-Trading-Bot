#!/usr/bin/env python3
"""
Harmesh Trading System — Main Entry Point
Harmesh v1.0 — Crypto Trading Bot for Termux

Usage:
  python main.py --mode paper     # Phase 1: Paper trading
  python main.py --mode live      # Phase 2: Live trading (locked until Phase 1 passes)
  python main.py --status         # Show system status and metrics
  python main.py --reset          # Reset paper trading state
  python main.py --check-upgrade  # Check if Phase 1 thresholds are met
"""
import argparse
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

# Ensure engine/ is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.exchange import ExchangeConnector
from engine.paper import PaperTradingEngine
from engine.live import LiveTradeEngine
from engine.risk import RiskManager

console = Console()
HARMESH_DIR = os.path.dirname(os.path.abspath(__file__))


def setup_logging(config: dict):
    """Configure unified logging."""
    log_cfg = config.get("logging", {})
    level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    log_file = os.path.join(HARMESH_DIR, log_cfg.get("file", "logs/system.log"))
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = logging.getLogger()
    root.setLevel(level)

    # Always file
    fh = logging.FileHandler(log_file)
    fh.setFormatter(fmt)
    fh.setLevel(level)
    root.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    ch.setLevel(level)
    root.addHandler(ch)

    # Reduce noise from CCXT
    logging.getLogger("ccxt.base.exchange").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return logging.getLogger("harmesh")


def load_config(path: str = None) -> dict:
    """Load config.json."""
    if path is None:
        path = os.path.join(HARMESH_DIR, "config.json")
    if not os.path.exists(path):
        console.print(f"[red]ERROR: config.json not found at {path}[/red]")
        sys.exit(1)
    with open(path, "r") as f:
        return json.load(f)


def save_config(config: dict):
    """Save config.json."""
    path = os.path.join(HARMESH_DIR, "config.json")
    with open(path, "w") as f:
        json.dump(config, f, indent=2)


def draw_dashboard(paper_engine, live_engine, mode: str, ticks: int):
    """Render the live terminal dashboard."""
    console = Console()

    # Header
    header = Panel(
        Text.assemble(
            (" HARMESH TRADING SYSTEM  ", "bold white on blue"),
            (f" Mode: {mode.upper()}   ", "bold green" if mode == "paper" else "bold yellow"),
            (f" Ticks: {ticks}  ", "white"),
        ),
        style="cyan",
    )
    console.print(header)

    if paper_engine:
        m = paper_engine.get_metrics()
        metrics_table = Table(box=box.ROUNDED, title="[bold cyan]PHASE 1 — PAPER TRADING[/bold cyan]")
        metrics_table.add_column("Metric", style="cyan")
        metrics_table.add_column("Value", style="white")

        metrics_table.add_row("Balance", f"${m['balance']:.2f}")
        metrics_table.add_row("Total Equity", f"${m['total_equity']:.2f}")
        metrics_table.add_row("Total Trades", str(m["total_trades"]))
        metrics_table.add_row("Win Rate", f"{m['win_rate']:.1%}")
        metrics_table.add_row("Profit Factor", f"{m['profit_factor']:.2f}")
        metrics_table.add_row("Max Drawdown", f"{m['max_drawdown_pct']:.2f}%")
        metrics_table.add_row("Sharpe Ratio", f"{m['sharpe_ratio']:.2f}")
        metrics_table.add_row("Net PnL", f"${m['net_pnl']:.2f}")
        metrics_table.add_row("Open Trades", str(m["open_trades"]))
        metrics_table.add_row("Days Running", str(m["days_running"]))
        metrics_table.add_row("Wins / Losses", f"{m['winning_trades']} / {m['losing_trades']}")
        console.print(metrics_table)

        # Upgrade status
        can_upgrade, reason, _ = paper_engine.can_upgrade_to_live()
        if can_upgrade:
            console.print(Panel(
                "  PHASE 2 UNLOCKED — Ready for live trading!",
                title="[bold]Upgrade Status[/bold]", style="bold green"
            ))
        else:
            console.print(Panel(
                f"  Phase 2 locked — {reason}",
                title="[bold]Upgrade Status[/bold]", style="yellow"
            ))

        # Open trades
        if paper_engine.open_trades:
            opt_table = Table(box=box.SIMPLE, title="[bold]Open Positions[/bold]")
            opt_table.add_column("Symbol", style="cyan")
            opt_table.add_column("Side", style="green")
            opt_table.add_column("Entry", style="white")
            opt_table.add_column("Qty", style="white")
            opt_table.add_column("SL", style="red")
            opt_table.add_column("TP", style="green")
            opt_table.add_column("PnL%", style="yellow")
            for t in paper_engine.open_trades:
                current = paper_engine.last_prices.get(t.symbol, t.entry_price)
                unrealized_pnl = (current - t.entry_price) / t.entry_price * 100
                pnl_style = "green" if unrealized_pnl >= 0 else "red"
                opt_table.add_row(
                    t.symbol, t.side.upper(),
                    f"${t.entry_price:.2f}",
                    f"{t.quantity:.6f}",
                    f"${t.stop_loss:.2f}",
                    f"${t.take_profit:.2f}",
                    f"[{pnl_style}]{unrealized_pnl:+.2f}%[/{pnl_style}]"
                )
            console.print(opt_table)

    if live_engine:
        m = live_engine.get_metrics()
        live_table = Table(box=box.ROUNDED, title="[bold yellow]PHASE 2 — LIVE TRADING[/bold yellow]")
        live_table.add_column("Metric", style="yellow")
        live_table.add_column("Value", style="white")
        live_table.add_row("Total Trades", str(m["total_trades"]))
        live_table.add_row("Win Rate", f"{m['win_rate']:.1%}")
        live_table.add_row("Net PnL", f"${m['net_pnl']:.2f}")
        live_table.add_row("Open Orders", str(m["open_orders"]))
        live_table.add_row("Balance", f"${m['current_balance']:.2f}")
        console.print(live_table)

    return None


def run_paper_mode(config: dict, exchange: ExchangeConnector, interval: int = 300):
    """Run Phase 1 paper trading loop."""
    paper = PaperTradingEngine(config, exchange)
    ticks = 0

    console.print("\n[bold cyan]╔══════════════════════════════════════╗[/bold cyan]")
    console.print("[bold cyan]║   HARMESH PAPER TRADING — PHASE 1   ║[/bold cyan]")
    console.print("[bold cyan]╚══════════════════════════════════════╝[/bold cyan]")
    console.print(f"[white]Virtual Balance:[/white] [green]${paper.initial_capital:.2f}[/green]")
    console.print(f"[white]Strategy:[/white] [yellow]{paper.strategy_name}[/yellow]")
    console.print(f"[white]Symbols:[/white] {', '.join(paper.symbols)}")
    console.print(f"[white]Timeframe:[/white] {paper.timeframe}")
    console.print(f"[white]Tick Interval:[/white] {interval}s")
    console.print(f"[white]Trade Log:[/white] {paper.trade_log}")
    console.print(f"[white]State File:[/white] {paper.state_file}\n")

    # Restore existing state info
    paper_metrics = paper.get_metrics()
    if paper_metrics["total_trades"] > 0:
        console.print(f"[cyan]Resumed from state:[/cyan] {paper_metrics['total_trades']} trades, "
                      f"${paper_metrics['balance']:.2f} balance\n")

    # Trap Ctrl+C for graceful shutdown
    running = True

    def signal_handler(sig, frame):
        nonlocal running
        console.print("\n[yellow]Shutting down gracefully...[/yellow]")
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while running:
            ticks += 1
            console.clear()
            draw_dashboard(paper, None, "paper", ticks)

            try:
                paper.execute_tick()

                # Check upgrade thresholds
                can_upgrade, reason, metrics = paper.can_upgrade_to_live()
                if can_upgrade:
                    console.print("\n[bold green]✓ ALL THRESHOLDS MET![/bold green]")
                    console.print(f"[green]Win Rate: {metrics['win_rate']:.1%} | "
                                  f"Profit Factor: {metrics['profit_factor']:.2f}[/green]")
                    console.print("[green]You can now run: python main.py --mode live[/green]\n")
                else:
                    if ticks % 12 == 0:  # Every ~hour at 5min intervals
                        console.print(f"\n[yellow]Upgrade check: {reason}[/yellow]")

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Tick error: {e}", exc_info=True)
                console.print(f"[red]Error in tick: {e}[/red]")

            # Wait for next interval
            if running:
                try:
                    for _ in range(interval):
                        if not running:
                            break
                        time.sleep(1)
                except KeyboardInterrupt:
                    break

    except KeyboardInterrupt:
        pass

    console.print("\n[cyan]Paper trading session ended.")
    paper._save_state()
    m = paper.get_metrics()
    console.print(f"[white]Final:[/white] {m['total_trades']} trades | "
                  f"Win rate: {m['win_rate']:.1%} | "
                  f"PnL: ${m['net_pnl']:.2f} | "
                  f"Balance: ${m['balance']:.2f}")


def run_live_mode(config: dict, exchange: ExchangeConnector, interval: int = 300):
    """Run Phase 2 live trading (locked until thresholds met)."""
    # First verify paper trading thresholds
    paper = PaperTradingEngine(config, exchange)
    can_upgrade, reason, metrics = paper.can_upgrade_to_live()

    if not can_upgrade:
        console.print("\n[bold red]⚠  PHASE 2 LOCKED[/bold red]")
        console.print(f"[yellow]Phase 1 thresholds not met:[/yellow]")
        console.print(f"[white]  → {reason}[/white]")
        console.print(f"\n[yellow]Current metrics:[/yellow]")
        console.print(f"  Win Rate:       {metrics['win_rate']:.1%}  (need >55%)")
        console.print(f"  Profit Factor:  {metrics['profit_factor']:.2f}  (need >1.5)")
        console.print(f"  Total Trades:   {metrics['total_trades']}  (need 200)")
        console.print(f"  Days Running:   {metrics['days_running']}  (need 7)")
        console.print(f"\n[cyan]Continue paper trading with: python main.py --mode paper[/cyan]")
        sys.exit(1)

    # Thresholds met — warn user
    console.print("\n[bold green]╔══════════════════════════════════════╗[/bold green]")
    console.print("[bold green]║   HARMESH LIVE TRADING — PHASE 2    ║[/bold green]")
    console.print("[bold green]╚══════════════════════════════════════╝[/bold green]")
    console.print("\n[bold yellow]⚠  WARNING: THIS WILL TRADE REAL MONEY ⚠[/bold yellow]")
    console.print("[yellow]Make sure your API keys in config.json are correct.[/yellow]")
    console.print(f"[yellow]Exchange: {config['exchange']['name']} "
                  f"({'SANDBOX' if config['exchange']['sandbox'] else 'LIVE'})[/yellow]")
    console.print(f"[white]Initial Capital:[/white] [green]${config['live']['initial_capital']:.2f}[/green]")
    console.print(f"[white]Max Risk/Trade:[/white] {config['live']['max_risk_per_trade']:.0%}")
    console.print(f"[white]Mandatory Stop-Loss:[/white] Yes\n")

    # Confirm
    confirm = input("Type 'CONFIRM' to start live trading: ")
    if confirm != "CONFIRM":
        console.print("[red]Aborted.[/red]")
        sys.exit(0)

    live = LiveTradeEngine(config, exchange)
    ticks = 0
    running = True

    def signal_handler(sig, frame):
        nonlocal running
        console.print("\n[yellow]Shutting down...[/yellow]")
        running = False

    signal.signal(signal.SIGINT, signal_handler)

    try:
        while running:
            ticks += 1
            console.clear()
            console.print(f"[bold cyan]HARMESH LIVE TRADING — Tick #{ticks}[/bold cyan]")
            console.print(f"[yellow]⚠  REAL MONEY MODE[/yellow]\n")

            try:
                live.execute_tick()
            except Exception as e:
                logger.error(f"Live tick error: {e}", exc_info=True)
                console.print(f"[red]Error: {e}[/red]")

            metrics = live.get_metrics()
            console.print(f"\n[white]Trades: {metrics['total_trades']} | "
                         f"Win Rate: {metrics['win_rate']:.1%} | "
                         f"PnL: ${metrics['net_pnl']:.2f} | "
                         f"Open Orders: {metrics['open_orders']}[/white]")
            console.print(f"[white]Balance: ${metrics['current_balance']:.2f}[/white]")

            if running:
                try:
                    for _ in range(interval):
                        if not running:
                            break
                        time.sleep(1)
                except KeyboardInterrupt:
                    break
    except KeyboardInterrupt:
        pass

    console.print("\n[cyan]Live trading session ended.[/cyan]")


def show_status(config: dict, exchange: ExchangeConnector):
    """Display comprehensive system status."""
    paper = PaperTradingEngine(config, exchange)
    m = paper.get_metrics()

    console.print("\n[bold cyan]═══ HARMESH SYSTEM STATUS ═══[/bold cyan]\n")

    # System info
    console.print("[bold]System:[/bold]")
    console.print(f"  Config:       ~/harmesh/config.json")
    console.print(f"  Logs:         ~/harmesh/logs/")
    console.print(f"  Exchange:     {config['exchange']['name']} "
                  f"({'sandbox' if config['exchange']['sandbox'] else 'live'})")
    console.print(f"  Strategy:     {config['trading']['strategy']}")
    console.print(f"  Symbols:      {', '.join(config['trading']['symbols'])}")
    console.print(f"  Timeframe:    {config['trading']['timeframe']}")
    console.print()

    # Phase 1 status
    console.print("[bold]Phase 1 — Paper Trading:[/bold]")
    if m["total_trades"] == 0:
        console.print("  [yellow]No trades yet — run: python main.py --mode paper[/yellow]")
    else:
        console.print(f"  Balance:       ${m['balance']:.2f} (start: ${m['start_balance']:.2f})")
        console.print(f"  Total Equity:  ${m['total_equity']:.2f}")
        console.print(f"  Net PnL:       ${m['net_pnl']:+.2f}")
        console.print(f"  Total Trades:  {m['total_trades']}")
        console.print(f"  Win Rate:      {m['win_rate']:.1%}")
        console.print(f"  Profit Factor: {m['profit_factor']:.2f}")
        console.print(f"  Max DD:        {m['max_drawdown_pct']:.2f}%")
        console.print(f"  Sharpe:        {m['sharpe_ratio']:.2f}")
        console.print(f"  Days Running:  {m['days_running']}")
        console.print(f"  Open Trades:   {m['open_trades']}")

        can_upgrade, reason, _ = paper.can_upgrade_to_live()
        if can_upgrade:
            console.print(f"\n  [bold green]✓ PHASE 2 UNLOCKED[/bold green]")
        else:
            console.print(f"\n  [yellow]→ {reason}[/yellow]")

    console.print()

    # Phase 2
    console.print("[bold]Phase 2 — Live Trading:[/bold]")
    live_enabled = config.get("live", {}).get("enabled", False)
    if live_enabled:
        console.print("  [green]Enabled[/green]")
    else:
        console.print("  [yellow]Disabled[/yellow]")
    console.print(f"  Max Risk/Trade: {config['live']['max_risk_per_trade']:.0%}")
    console.print(f"  Initial Capital: ${config['live']['initial_capital']:.2f}")
    console.print()

    # Recent trades
    trade_log = config["paper"]["trade_log"]
    if os.path.exists(trade_log):
        try:
            df = pd.read_csv(trade_log)
            recent = df.tail(10)
            if not recent.empty:
                console.print("[bold]Recent Trades (last 10):[/bold]")
                console.print(recent.to_string(index=False))
        except Exception:
            pass


def cmd_reset(config: dict):
    """Reset paper trading state."""
    exchange = ExchangeConnector(config)
    paper = PaperTradingEngine(config, exchange)
    paper.reset()
    console.print("[green]Paper trading state reset.[/green]")


def cmd_check_upgrade(config: dict):
    """Check if Phase 1 thresholds are met for upgrade."""
    exchange = ExchangeConnector(config)
    paper = PaperTradingEngine(config, exchange)
    can_upgrade, reason, metrics = paper.can_upgrade_to_live()

    console.print("\n[bold cyan]═══ UPGRADE READINESS CHECK ═══[/bold cyan]\n")

    # Requirements table
    reqs = [
        ("Total Trades", metrics["total_trades"], 200,
         metrics["total_trades"] >= 200),
        ("Days Running", metrics["days_running"], 7,
         metrics["days_running"] >= 7),
        ("Win Rate", f"{metrics['win_rate']:.1%}", ">55%",
         metrics["win_rate"] > 0.55),
        ("Profit Factor", f"{metrics['profit_factor']:.2f}", ">1.5",
         metrics["profit_factor"] > 1.5),
    ]

    console.print(f"[bold]{'Requirement':<20} {'Current':<15} {'Target':<10} {'Status':<10}[/bold]")
    console.print("-" * 55)
    for name, current, target, passed in reqs:
        status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        console.print(f"  {name:<18} {str(current):<15} {str(target):<10} {status}")
    console.print()

    if can_upgrade:
        console.print("[bold green]✓ ALL THRESHOLDS MET![/bold green]")
        console.print("[green]You can start live trading with: python main.py --mode live[/green]")
    else:
        console.print(f"[yellow]✗ Not ready yet:[/yellow]")
        console.print(f"[white]  {reason}[/white]")
        console.print(f"\n[cyan]Continue paper trading: python main.py --mode paper[/cyan]")

    # Show full metrics
    console.print(f"\n[bold]Full Metrics:[/bold]")
    console.print(f"  Net PnL:         ${metrics['net_pnl']:+.2f}")
    console.print(f"  Avg Win:         ${metrics['avg_win']:.2f}")
    console.print(f"  Avg Loss:        ${metrics['avg_loss']:.2f}")
    console.print(f"  Max Drawdown:    {metrics['max_drawdown_pct']:.2f}%")
    console.print(f"  Sharpe Ratio:    {metrics['sharpe_ratio']:.2f}")
    console.print(f"  Current Balance: ${metrics['balance']:.2f}")
    console.print(f"  Total Equity:    ${metrics['total_equity']:.2f}")


def main():
    parser = argparse.ArgumentParser(description="Harmesh Crypto Trading System")
    parser.add_argument("--mode", choices=["paper", "live"], help="Trading mode")
    parser.add_argument("--status", action="store_true", help="Show system status")
    parser.add_argument("--reset", action="store_true", help="Reset paper trading state")
    parser.add_argument("--check-upgrade", action="store_true", help="Check Phase 1 → Phase 2 upgrade")
    parser.add_argument("--interval", type=int, default=300, help="Tick interval in seconds (default: 300)")
    parser.add_argument("--config", type=str, default=None, help="Path to config.json")
    parser.add_argument("--no-exchange", action="store_true", help="Run without exchange connection (demo)")
    args = parser.parse_args()

    config = load_config(args.config)
    logger = setup_logging(config)

    # If no args, show status
    if not any([args.mode, args.status, args.reset, args.check_upgrade]):
        args.status = True

    if args.status:
        if args.no_exchange:
            exchange = None
        else:
            exchange = ExchangeConnector(config)
        show_status(config, exchange)
        return

    if args.reset:
        cmd_reset(config)
        return

    if args.check_upgrade:
        cmd_check_upgrade(config)
        return

    # Initialize exchange connection
    if args.no_exchange:
        from engine.mock_exchange import MockExchange
        logger.warning("Running without live exchange — using simulated price data")
        console.print("[yellow]⚠  Demo mode: using simulated price data[/yellow]")
        exchange = MockExchange(config)
    else:
        exchange = ExchangeConnector(config)

    if args.mode == "paper":
        run_paper_mode(config, exchange, args.interval)
    elif args.mode == "live":
        run_live_mode(config, exchange, args.interval)


if __name__ == "__main__":
    main()
