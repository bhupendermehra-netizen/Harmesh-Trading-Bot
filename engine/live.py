"""
Harmesh Live Trading Engine — Phase 2
Real money trading via CCXT exchange.
LOCKED until Phase 1 thresholds are met.
"""
import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

import pandas as pd

from engine.exchange import ExchangeConnector
from engine.strategy import get_strategy
from engine.risk import RiskManager

logger = logging.getLogger("harmesh.live")


class LiveTradeEngine:
    """
    Phase 2 live trading engine.
    Executes real orders on the exchange.
    Enforces: max 2% risk per trade, mandatory stop-loss.
    """

    def __init__(self, config: dict, exchange: ExchangeConnector):
        self.config = config
        self.exchange = exchange
        self.live_cfg = config.get("live", {})
        self.trading_cfg = config.get("trading", {})

        self.initial_capital = self.live_cfg.get("initial_capital", 100.0)
        self.strategy_name = self.trading_cfg.get("strategy", "macd_rsi")
        self.symbols = self.trading_cfg.get("symbols", ["BTC/USDT"])
        self.timeframe = self.trading_cfg.get("timeframe", "1h")

        self.strategy = get_strategy(self.strategy_name, config)
        self.risk = RiskManager(config)

        self.closed_trades = []
        self.open_orders = {}
        self.equity_curve = []
        self.returns = []
        self.start_time = datetime.now()

        self.trade_log = self.live_cfg["trade_log"]
        self.state_file = self.live_cfg["state_file"]

        self._load_state()

    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                self.closed_trades = state.get("closed_trades", [])
                self.equity_curve = state.get("equity_curve", [])
                self.returns = state.get("returns", [])
                self.start_time = datetime.fromisoformat(
                    state.get("start_time", datetime.now().isoformat())
                )
                logger.info(f"Live state restored: {len(self.closed_trades)} trades")
            except Exception as e:
                logger.warning(f"Could not load live state: {e}")

    def _save_state(self):
        try:
            state = {
                "closed_trades": self.closed_trades,
                "equity_curve": self.equity_curve,
                "returns": self.returns,
                "start_time": self.start_time.isoformat(),
            }
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save live state: {e}")

    def _get_balance(self) -> float:
        """Get available USDT (or quote currency) balance."""
        try:
            bal = self.exchange.fetch_balance()
            # Prefer USDT, then USDC, then BUSD, then first stable
            for stable in ["USDT", "USDC", "BUSD", "DAI", "FDUSD"]:
                if stable in bal["free"] and bal["free"][stable] > 0:
                    return float(bal["free"][stable])
            # Fallback: return all free balances summed in USD
            total = 0.0
            for cur, val in bal["free"].items():
                if val > 0:
                    try:
                        ticker = self.exchange.fetch_ticker(f"{cur}/USDT")
                        total += val * float(ticker.get("last", 0))
                    except Exception:
                        pass
            return total
        except Exception as e:
            logger.error(f"Balance fetch failed: {e}")
            return 0.0

    def execute_tick(self):
        """
        Main trading tick for live mode.
        1. Fetch portfolio state
        2. Check for filled orders
        3. Generate signals
        4. Place limit/market orders with stop-loss
        """
        logger.info("=" * 60)
        logger.info("LIVE TRADING TICK")

        balance = self._get_balance()
        logger.info(f"Available balance: ${balance:.2f}")

        # Fetch prices
        current_prices = {}
        for symbol in self.symbols:
            price = self.exchange.get_current_price(symbol)
            if price:
                current_prices[symbol] = price
                logger.info(f"  {symbol}: ${price:.4f}")

        if not current_prices:
            logger.warning("No price data — skipping tick")
            return

        # Check existing order statuses
        for symbol, order_id in list(self.open_orders.items()):
            try:
                order = self.exchange.fetch_order(order_id, symbol)
                if order.get("status") == "closed" or order.get("filled", 0) > 0:
                    logger.info(f"Order filled: {symbol} — {order}")
                    self.closed_trades.append({
                        "symbol": symbol,
                        "order_id": order_id,
                        "filled_price": order.get("price", order.get("average")),
                        "filled_amount": order.get("filled"),
                        "side": order.get("side"),
                        "timestamp": datetime.now().isoformat(),
                        "cost": order.get("cost"),
                    })
                    del self.open_orders[symbol]
                    self._save_state()
            except Exception as e:
                logger.warning(f"Order check failed for {symbol}: {e}")

        # Check for stop-loss / take-profit on open positions
        # Generate signals and place new orders
        for symbol in self.symbols:
            if symbol in self.open_orders:
                logger.info(f"  {symbol}: has pending order, skipping")
                continue

            df = self.exchange.fetch_ohlcv(symbol, self.timeframe, limit=100)
            if df.empty:
                continue

            signal = self.strategy.generate_signal(df)
            if signal == "hold":
                continue

            price = current_prices[symbol]
            atr = self.risk.compute_atr(df)
            sl = self.risk.compute_stop_loss(
                price, signal, atr,
                self.live_cfg["stop_loss_atr_multiplier"]
            )
            tp = self.risk.compute_take_profit(
                price, signal, atr,
                self.live_cfg["take_profit_atr_multiplier"]
            )

            valid, msg = self.risk.validate_trade_parameters(price, sl, balance, symbol)
            if not valid:
                logger.warning(f"  {symbol}: {msg}")
                continue

            quantity = self.risk.compute_position_size(balance, price, sl, symbol)
            if quantity <= 0:
                continue

            # Place market order
            order = self.exchange.create_order(
                symbol=symbol,
                order_type="market",
                side="buy" if signal == "long" else "sell",
                amount=quantity,
            )

            if order.get("status") != "error":
                order_id = order.get("id", "unknown")
                self.open_orders[symbol] = order_id
                logger.info(
                    f">>> LIVE {signal.upper()} {symbol}: "
                    f"{quantity:.6f} @ ~${price:.2f} | "
                    f"SL=${sl:.2f} TP=${tp:.2f}"
                )
                # Place stop-loss order
                self.exchange.create_order(
                    symbol=symbol,
                    order_type="stop_market",
                    side="sell" if signal == "long" else "buy",
                    amount=quantity,
                    params={"stopPrice": sl},
                )
                # Place take-profit limit order
                self.exchange.create_order(
                    symbol=symbol,
                    order_type="limit",
                    side="sell" if signal == "long" else "buy",
                    amount=quantity,
                    price=tp,
                )

        self._save_state()

    def get_metrics(self) -> dict:
        """Compute live trading metrics."""
        if not self.closed_trades:
            return {"total_trades": 0, "net_pnl": 0.0}

        pnls = [t.get("cost", 0) for t in self.closed_trades]
        wins = [t for t in self.closed_trades if t.get("cost", 0) > 0]
        losses = [t for t in self.closed_trades if t.get("cost", 0) <= 0]

        return {
            "total_trades": len(self.closed_trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": len(wins) / len(self.closed_trades) if self.closed_trades else 0.0,
            "net_pnl": sum(pnls),
            "open_orders": len(self.open_orders),
            "current_balance": self._get_balance(),
        }

    def reset(self):
        """WARNING: Resets live trading state (does NOT cancel orders)."""
        self.closed_trades = []
        self.open_orders = {}
        self.equity_curve = []
        self.returns = []
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
        logger.warning("Live trading state reset (orders NOT cancelled)")
