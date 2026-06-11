# Harmesh Trading System v2.0

Crypto trading bot for Termux/Android. Two-phase system: paper trade first, then unlock live.

## 🖥️ Live Dashboard

Monitor the bot in your browser — works on GitHub Pages:

```bash
# Generate fresh dashboard data, then push to GitHub:
cd ~/harmesh && source venv/bin/activate
python scripts/generate_dashboard_data.py
git add -A && git commit -m "update dashboard" && git push
```

Then visit: `https://bhupendermehra-netizen.github.io/Harmesh-Trading-Bot/`

The dashboard shows:
- **Key Metrics** — Score, Win Rate, Profit Factor, Return, Drawdown, Sharpe
- **Strategy Comparison** — Bar/line chart of all 3 strategy families
- **Equity Curve** — Portfolio value over time
- **Strategy Combos** — Ranked table of all combinations
- **Open Trades** — Active positions with entry, SL, TP
- **Best Parameters** — Optimized params per strategy

## Quick Start

```bash
cd ~/harmesh
./start.sh
```

This shows you an interactive menu.

## Usage

```bash
# Interactive menu
./start.sh

# Phase 1: Paper trading ($1000 virtual)
source venv/bin/activate && python main.py --mode paper

# Phase 2: Live trading (locked until Phase 1 passes)
source venv/bin/activate && python main.py --mode live

# System status
source venv/bin/activate && python main.py --status

# Check if ready for live
source venv/bin/activate && python main.py --check-upgrade

# Demo mode (no exchange keys needed)
source venv/bin/activate && python main.py --mode paper --no-exchange

# Reset paper state
source venv/bin/activate && python main.py --reset
```

Or use aliases:
```bash
source ~/harmesh/scripts/aliases.sh
harmesh           # Menu
harmesh-paper     # Phase 1
harmesh-status    # Dashboard
harmesh-log       # Watch logs
```

## Architecture

```
~/harmesh/
├── start.sh                  # Entry point
├── main.py                   # CLI interface
├── config.json               # All configuration
├── .env.example              # Template for API keys
├── engine/
│   ├── exchange.py           # CCXT exchange wrapper
│   ├── paper.py              # Phase 1 paper trader
│   ├── live.py               # Phase 2 live trader
│   ├── risk.py               # Risk management
│   ├── strategy.py           # MACD+RSI & EMA strategies
│   └── mock_exchange.py      # Simulated market data
├── strategies/               # Add your own strategies
├── logs/
│   ├── system.log            # Full system log
│   └── paper_trades.csv      # All paper trades
├── data/
│   ├── paper_state.json      # Persistent paper state
│   └── live_state.json
├── freqtrade/                # Cloned for reference
├── ccxt/                     # Cloned for reference
├── venv/                     # Python virtual env
└── scripts/
    └── aliases.sh            # Shell aliases
```

## Phase 1 — Paper Trading

- Starts with $1000 virtual balance
- Runs MACD+RSI strategy on 4 pairs (configurable)
- Trades every 5 min (configurable) with 1h candles
- Logs every trade to CSV
- Tracks: win rate, profit factor, max drawdown, Sharpe ratio
- **Upgrade to Phase 2 requires:**
  - Win rate > 55%
  - Profit factor > 1.5
  - Minimum 200 trades
  - Minimum 7 days runtime

## Phase 2 — Live Trading

LOCKED until Phase 1 thresholds met. When unlocked:
- Set your API keys in config.json
- Enforces: max 2% risk per trade, mandatory stop-loss
- Same strategy as paper (proven strategy)
- Start with small capital

## Risk Controls

- Max 2% risk per trade (configurable)
- ATR-based stop-loss (2x ATR)
- ATR-based take-profit (4x ATR)
- Max 3 open trades simultaneously
- Max 50% of capital per position
- No trades below $10 minimum balance

## Configuration

Edit `config.json`:
- Change exchange (binance, kraken, coinbase, etc.)
- Add API keys
- Adjust capital, pairs, timeframe
- Set risk parameters
- Switch strategies (macd_rsi, ema_crossover)

## Offline Demo

No API keys needed:
```bash
python main.py --mode paper --no-exchange
```

Generates realistic simulated price data for testing.

## Installed Frameworks

Repo includes:
- **CCXT** — exchange connector library (installed + cloned for reference)
- **freqtrade** — reference implementation (cloned)

## Notes

- Built for Termux on aarch64/ARM64 Android devices
- Low RAM usage (~100-200MB)
- All files contained in ~/harmesh/
- State persists across restarts
- Graceful shutdown on Ctrl+C
