"""
Harmesh Advanced Paper Trading Engine
Phase 1 paper trading with full advanced strategy support:
- Regime-aware trading
- Multi-timeframe analysis
- Advanced risk management (Kelly, trailing stops, correlation)
- Performance analytics
"""
import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

import pandas as pd

from engine.exchange import ExchangeConnector
from engine.strategy_advanced import AdvancedStrategyEngine
from engine.regime import RegimeDetector, Regime
from engine.risk import AdvancedRiskManager
from engine.analytics import PerformanceAnalyzer

logger = logging.getLogger("harmesh.paper_advanced")


class PaperTrade:
    """A single paper trade record (compatible with original PaperTrade)."""

    def __init__(self, symbol: str, side: str, entry_price: float,
                 quantity: float, stop_loss: float, take_profit: float,
                 entry_time: str, capital_used: float):
        self.symbol = symbol
        self.side = side
        self.entry_price = entry_price
        self.quantity = quantity
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.entry_time = entry_time
        self.exit_time: Optional[str] = None
        self.exit_price: Optional[float] = None
        self.pnl: Optional[float] = None
        self.pnl_pct: Optional[float] = None
        self.exit_reason: Optional[str] = None
        self.capital_used = capital_used

    def close_trade(self, exit_price: float, reason: str = "signal"):
        self.exit_price = exit_price
        self.exit_time = datetime.now().isoformat()
        self.exit_reason = reason

        if self.side == "long":
            self.pnl = (exit_price - self.entry_price) * self.quantity
            self.pnl_pct = ((exit_price - self.entry_price) / self.entry_price) * 100
        else:
            self.pnl = (self.entry_price - exit_price) * self.quantity
            self.pnl_pct = ((self.entry_price - exit_price) / self.entry_price) * 100

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "entry_time": self.entry_time,
            "exit_time": self.exit_time or "",
            "exit_price": self.exit_price or 0.0,
            "pnl": self.pnl or 0.0,
            "pnl_pct": self.pnl_pct or 0.0,
            "exit_reason": self.exit_reason or "",
            "capital_used": self.capital_used,
        }

    @classmethod
    def from_dict(cls, d: dict):
        t = cls(
            symbol=d["symbol"],
            side=d["side"],
            entry_price=d["entry_price"],
            quantity=d["quantity"],
            stop_loss=d["stop_loss"],
            take_profit=d["take_profit"],
            entry_time=d["entry_time"],
            capital_used=d.get("capital_used", 0.0),
        )
        if d.get("exit_time"):
            t.exit_time = d["exit_time"]
            t.exit_price = d["exit_price"]
            t.pnl = d["pnl"]
            t.pnl_pct = d["pnl_pct"]
            t.exit_reason = d["exit_reason"]
        return t


class AdvancedPaperTradingEngine:
    """
    Phase 1 paper trading engine with advanced features.
    Uses regime detection, multi-strategy fusion, MTF, and advanced risk.
    """

    def __init__(self, config: dict, exchange: ExchangeConnector):
        self.config = config
        self.exchange = exchange
        paper_cfg = config.get("paper", {})
        trading_cfg = config.get("trading", {})

        self.initial_capital = paper_cfg.get("initial_capital", 1000.0)
        self.balance = self.initial_capital
        self.symbols = trading_cfg.get("symbols", ["BTC/USDT"])
        self.timeframe = trading_cfg.get("timeframe", "1h")

        # Advanced components
        self.strategy = AdvancedStrategyEngine(config)
        self.regime = RegimeDetector(config)
        self.risk = AdvancedRiskManager(config)
        self.analytics = PerformanceAnalyzer(config)

        # Multi-timeframe data cache
        self.mtf_timeframes = config.get("advanced_strategy", {}).get(
            "mtf_timeframes", ["15m", "1h", "4h"]
        )
        self._mtf_cache: dict[str, dict[str, pd.DataFrame]] = {}

        # Price history for correlation
        self._price_history: dict[str, list[float]] = {}

        self.open_trades: list[PaperTrade] = []
        self.closed_trades: list[PaperTrade] = []
        self.equity_curve = [self.initial_capital]
        self.returns = []
        self.start_time = datetime.now()

        # Paths
        self.trade_log = paper_cfg["trade_log"]
        self.state_file = paper_cfg["state_file"]

        # Load state if exists
        self._load_state()

        self.last_prices = {}
        self._last_regime = None

    def _load_state(self):
        """Restore paper trading state from disk."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                self.balance = state.get("balance", self.initial_capital)
                self.equity_curve = state.get("equity_curve", [self.initial_capital])
                self.returns = state.get("returns", [])
                self.start_time = datetime.fromisoformat(
                    state.get("start_time", datetime.now().isoformat())
                )
                for td in state.get("open_trades", []):
                    self.open_trades.append(PaperTrade.from_dict(td))
                for td in state.get("closed_trades", []):
                    self.closed_trades.append(PaperTrade.from_dict(td))
                logger.info(f"Paper state restored: balance=${self.balance:.2f}, "
                           f"{len(self.open_trades)} open, {len(self.closed_trades)} closed")
            except Exception as e:
                logger.warning(f"Could not load paper state: {e}")

    def _save_state(self):
        """Persist paper trading state to disk."""
        try:
            state = {
                "balance": self.balance,
                "equity_curve": self.equity_curve,
                "returns": self.returns,
                "start_time": self.start_time.isoformat(),
                "open_trades": [t.to_dict() for t in self.open_trades],
                "closed_trades": [t.to_dict() for t in self.closed_trades],
            }
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _log_trade(self, trade: PaperTrade):
        """Append trade to CSV log."""
        try:
            os.makedirs(os.path.dirname(self.trade_log), exist_ok=True)
            file_exists = os.path.exists(self.trade_log)
            d = trade.to_dict()
            df = pd.DataFrame([d])
            df.to_csv(self.trade_log, mode="a", header=not file_exists, index=False)
        except Exception as e:
            logger.error(f"Failed to log trade: {e}")

    def _check_stops(self, current_prices: dict):
        """Check if any open trades hit stop-loss or take-profit (with trailing)."""
        to_close = []
        for trade in self.open_trades:
            price = current_prices.get(trade.symbol)
            if price is None:
                continue

            # Update trailing stop if enabled
            if self.risk.trailing_stop:
                trade.stop_loss = self.risk.update_trailing_stop(
                    price, trade.entry_price, trade.side, trade.stop_loss
                )

            if trade.side == "long":
                if price <= trade.stop_loss:
                    trade.close_trade(trade.stop_loss, reason="stop_loss")
                    to_close.append(trade)
                    logger.info(f"STOP LOSS: {trade.symbol} @ {trade.stop_loss:.2f}")
                elif price >= trade.take_profit:
                    trade.close_trade(trade.take_profit, reason="take_profit")
                    to_close.append(trade)
                    logger.info(f"TAKE PROFIT: {trade.symbol} @ {trade.take_profit:.2f}")
            else:  # short
                if price >= trade.stop_loss:
                    trade.close_trade(trade.stop_loss, reason="stop_loss")
                    to_close.append(trade)
                    logger.info(f"STOP LOSS (short): {trade.symbol} @ {trade.stop_loss:.2f}")
                elif price <= trade.take_profit:
                    trade.close_trade(trade.take_profit, reason="take_profit")
                    to_close.append(trade)
                    logger.info(f"TAKE PROFIT (short): {trade.symbol} @ {trade.take_profit:.2f}")

        for t in to_close:
            self.open_trades.remove(t)
            self.closed_trades.append(t)
            self.balance += (t.capital_used + (t.pnl or 0.0))
            self.returns.append((t.pnl_pct or 0.0) / 100.0)
            equity = self.balance + sum(
                ot.quantity * self.last_prices.get(ot.symbol, ot.entry_price)
                for ot in self.open_trades
            )
            self.equity_curve.append(equity)
            self._log_trade(t)

            # Update drawdown tracker
            self.risk.update_drawdown(equity)

    def _fetch_mtf_data(self) -> dict[str, pd.DataFrame]:
        """Fetch data for all configured timeframes."""
        mtf_dfs = {}
        for symbol in self.symbols[:1]:  # MTF on primary symbol
            for tf in self.mtf_timeframes:
                if tf == self.timeframe:
                    continue  # Main timeframe fetched separately
                try:
                    df = self.exchange.fetch_ohlcv(symbol, tf, limit=100)
                    if not df.empty and len(df) > 50:
                        mtf_dfs[tf] = df
                except Exception as e:
                    logger.debug(f"MTF fetch error {symbol} {tf}: {e}")
        return mtf_dfs

    def execute_tick(self):
        """
        Main loop tick with advanced features:
        1. Fetch prices for all symbols
        2. Detect market regime
        3. Check stop/take-profit levels (with trailing)
        4. Generate signals with regime & MTF awareness
        5. Execute new trades with advanced risk sizing
        """
        logger.info("=" * 60)
        logger.info(f"ADVANCED PAPER TICK — Balance: ${self.balance:.2f} | "
                    f"Open trades: {len(self.open_trades)}")

        current_prices = {}
        for symbol in self.symbols:
            price = self.exchange.get_current_price(symbol)
            if price:
                current_prices[symbol] = price
                # Track price history for correlation
                if symbol not in self._price_history:
                    self._price_history[symbol] = []
                self._price_history[symbol].append(price)
                if len(self._price_history[symbol]) > 100:
                    self._price_history[symbol] = self._price_history[symbol][-100:]

        self.last_prices = current_prices

        if not current_prices:
            logger.warning("No price data available")
            return

        for sym, p in current_prices.items():
            logger.info(f"  {sym}: ${p:.4f}")

        # 1. Detect market regime
        regime_info = None
        try:
            primary_symbol = self.symbols[0]
            df_main = self.exchange.fetch_ohlcv(primary_symbol, self.timeframe, limit=200)
            if not df_main.empty and len(df_main) > 50:
                regime_info = self.regime.detect_regime(df_main)
                current_regime = regime_info["regime"]
                if self._last_regime != current_regime:
                    logger.info(f"REGIME CHANGE: {self._last_regime} → {current_regime}")
                    self._last_regime = current_regime
                logger.info(f"  Regime: {current_regime.value} "
                           f"(ADX={regime_info['details']['adx']}, "
                           f"vol={regime_info['details']['volatility']:.4f})")
        except Exception as e:
            logger.warning(f"Regime detection failed: {e}")

        # 2. Check stops on existing trades
        self._check_stops(current_prices)

        # 3. Fetch MTF data
        mtf_dfs = self._fetch_mtf_data()

        # 4. Generate signals for each symbol
        for symbol in self.symbols:
            # Skip if already have open trade on this symbol
            if any(t.symbol == symbol for t in self.open_trades):
                logger.info(f"  {symbol}: already has open trade, skipping")
                continue

            # Check if we can open more trades
            # Compute portfolio correlation if we have open trades
            portfolio_corr = 0.0
            if self.open_trades and len(self._price_history.get(symbol, [])) > 20:
                for ot in self.open_trades:
                    other_history = self._price_history.get(ot.symbol, [])
                    this_history = self._price_history.get(symbol, [])
                    if len(other_history) > 20 and len(this_history) > 20:
                        corr = self.risk.check_correlation(symbol, ot.symbol, this_history, other_history)
                        portfolio_corr = max(portfolio_corr, abs(corr))

            allowed, reason = self.risk.can_open_trade(
                len(self.open_trades), self.balance, portfolio_correlation=portfolio_corr
            )
            if not allowed:
                logger.info(f"  Cannot open trade: {reason}")
                continue

            # Fetch OHLCV data
            df = self.exchange.fetch_ohlcv(symbol, self.timeframe, limit=200)
            if df.empty or len(df) < 50:
                continue

            # Fetch MTF data for this symbol
            symbol_mtf = {}
            for tf in self.mtf_timeframes:
                if tf != self.timeframe:
                    try:
                        tf_df = self.exchange.fetch_ohlcv(symbol, tf, limit=100)
                        if not tf_df.empty and len(tf_df) > 50:
                            symbol_mtf[tf] = tf_df
                    except Exception:
                        pass

            # Generate signal with full context
            signal_result = self.strategy.generate_signal(
                df, regime_info=regime_info, mtf_dfs=symbol_mtf if symbol_mtf else None
            )
            signal = signal_result["signal"]
            confidence = signal_result.get("confidence", 0.0)

            if signal == "hold":
                logger.info(f"  {symbol}: HOLD (conf={confidence:.2f})")
                continue

            logger.info(f"  {symbol}: {signal.upper()} signal (conf={confidence:.2f})")

            price = current_prices[symbol]
            atr = self.risk.compute_atr(df)

            # Get regime-based parameter adjustments
            regime_mult = 1.0
            if regime_info and regime_info.get("regime"):
                regime_params = self.regime.get_regime_params(regime_info["regime"])
                regime_mult = regime_params.get("position_size_mult", 1.0)

            # Compute stop-loss with regime adjustment
            sl_mult = config_live_sl = self.config["live"]["stop_loss_atr_multiplier"]
            if regime_info and regime_info.get("regime"):
                sl_mult *= self.regime.get_regime_params(regime_info["regime"]).get("stop_loss_mult", 1.0)

            tp_mult = self.config["live"]["take_profit_atr_multiplier"]
            if regime_info and regime_info.get("regime"):
                tp_mult *= self.regime.get_regime_params(regime_info["regime"]).get("take_profit_mult", 1.0)

            sl = self.risk.compute_stop_loss(price, signal, atr, sl_mult, regime_mult)
            tp = self.risk.compute_take_profit(price, signal, atr, tp_mult, regime_mult)

            # Compute position size with advanced method
            win_rate = self.get_metrics()["win_rate"]
            avg_win = self.get_metrics()["avg_win"]
            avg_loss = self.get_metrics()["avg_loss"]
            volatility = atr / price if price > 0 else 0.0

            quantity = self.risk.compute_position_size(
                self.balance, price, sl, symbol=symbol,
                volatility=volatility,
                win_rate=win_rate if win_rate > 0 else 0.5,
                avg_win=avg_win if avg_win else 0,
                avg_loss=abs(avg_loss) if avg_loss else 0,
                regime_mult=regime_mult,
            )

            if quantity <= 0:
                logger.warning(f"  {symbol}: Zero quantity, skipping")
                continue

            # Adjust for exchange precision
            try:
                precision = self.exchange.get_precision(symbol)
                qty_prec = precision["amount"]
                quantity = round(quantity, int(qty_prec)) if qty_prec > 0 else quantity
            except Exception:
                quantity = round(quantity, 6)

            capital_used = quantity * price
            if capital_used > self.balance:
                logger.warning(f"  {symbol}: Insufficient balance "
                               f"(need ${capital_used:.2f}, have ${self.balance:.2f})")
                continue

            # Execute paper trade
            trade = PaperTrade(
                symbol=symbol,
                side=signal,
                entry_price=price,
                quantity=quantity,
                stop_loss=sl,
                take_profit=tp,
                entry_time=datetime.now().isoformat(),
                capital_used=capital_used,
            )
            self.open_trades.append(trade)
            self.balance -= capital_used
            logger.info(
                f"  >>> PAPER {signal.upper()} {symbol}: "
                f"{quantity:.6f} @ ${price:.2f} | "
                f"SL=${sl:.2f} TP=${tp:.2f} | "
                f"Cost=${capital_used:.2f} | "
                f"Regime={regime_info['regime'].value if regime_info else 'N/A'}"
            )

        # Update equity curve
        total_equity = self.balance + sum(
            t.quantity * current_prices.get(t.symbol, t.entry_price)
            for t in self.open_trades
        )
        self.equity_curve.append(total_equity)

        # Update drawdown
        self.risk.update_drawdown(total_equity)

        # Save state
        self._save_state()

    def get_metrics(self) -> dict:
        """Compute and return all performance metrics."""
        total_trades = len(self.closed_trades)
        if total_trades == 0:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "net_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "balance": self.balance,
                "total_equity": self.balance,
                "open_trades": len(self.open_trades),
                "days_running": (datetime.now() - self.start_time).days,
                "start_balance": self.initial_capital,
                "current_regime": self._last_regime.value if self._last_regime else "unknown",
            }

        wins = [t for t in self.closed_trades if t.pnl and t.pnl > 0]
        losses = [t for t in self.closed_trades if t.pnl and t.pnl <= 0]
        win_rate = len(wins) / total_trades if total_trades > 0 else 0.0

        gross_profit = sum(t.pnl for t in wins) if wins else 0.0
        gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.0

        dd_metrics = self.risk.compute_max_drawdown(self.equity_curve)
        sharpe = self.risk.compute_sharpe_ratio(self.returns)
        sortino = self.risk.compute_sortino_ratio(self.returns)
        net_pnl = sum(t.pnl for t in self.closed_trades) if self.closed_trades else 0.0

        avg_win = gross_profit / len(wins) if wins else 0.0
        avg_loss = gross_loss / len(losses) if losses else 0.0

        days_running = (datetime.now() - self.start_time).days

        return {
            "total_trades": total_trades,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown_pct": dd_metrics["max_dd_pct"],
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "net_pnl": net_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "balance": self.balance,
            "total_equity": self.equity_curve[-1] if self.equity_curve else self.balance,
            "open_trades": len(self.open_trades),
            "days_running": days_running,
            "start_balance": self.initial_capital,
            "current_regime": self._last_regime.value if self._last_regime else "unknown",
        }

    def can_upgrade_to_live(self) -> tuple:
        """Check if Phase 1 thresholds are met."""
        paper_cfg = self.config.get("paper", {})
        min_trades = paper_cfg.get("min_trades_for_upgrade", 200)
        min_days = paper_cfg.get("min_days_for_upgrade", 7)
        win_threshold = paper_cfg.get("win_rate_threshold", 0.55)
        pf_threshold = paper_cfg.get("profit_factor_threshold", 1.5)

        metrics = self.get_metrics()
        days_running = metrics["days_running"]
        total_trades = metrics["total_trades"]
        win_rate = metrics["win_rate"]
        profit_factor = metrics["profit_factor"]

        reasons = []
        if days_running < min_days:
            reasons.append(f"Need {min_days - days_running} more days")
        if total_trades < min_trades:
            reasons.append(f"Need {min_trades - total_trades} more trades")
        if win_rate <= win_threshold:
            reasons.append(f"Win rate {win_rate:.1%} <= {win_threshold:.0%}")
        if profit_factor <= pf_threshold:
            reasons.append(f"Profit factor {profit_factor:.2f} <= {pf_threshold:.1f}")

        if reasons:
            return False, "; ".join(reasons), metrics
        return True, "ALL THRESHOLDS MET — ready for Phase 2!", metrics

    def generate_report(self) -> str:
        """Generate a comprehensive performance report."""
        return self.analytics.generate_report(
            self.closed_trades, self.equity_curve, self.returns
        )

    def reset(self):
        """Reset paper trading state."""
        self.balance = self.initial_capital
        self.open_trades = []
        self.closed_trades = []
        self.equity_curve = [self.initial_capital]
        self.returns = []
        self.start_time = datetime.now()
        self.last_prices = {}
        self._price_history = {}
        self._last_regime = None
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
        if os.path.exists(self.trade_log):
            os.remove(self.trade_log)
        logger.info("Advanced paper trading state reset")
