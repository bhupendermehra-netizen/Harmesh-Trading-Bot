"""
Fetch historical OHLCV data from Binance for backtesting.
No API key needed for public data.
"""
import json
import os
import sys
from datetime import datetime, timedelta
import ccxt
import pandas as pd

SYMBOL = "BTC/USDT"
TIMEFRAME = "1h"
LIMIT = 1000  # max per request
OUTPUT = "data/historical_btc_1h.csv"
DATA_DIR = "data"

def fetch_ohlcv(symbol, timeframe, limit=1000, since=None):
    exchange = ccxt.binance({"enableRateLimit": True})
    all_ohlcv = []

    try:
        if since:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        else:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

        all_ohlcv.extend(ohlcv)
        print(f"Fetched {len(ohlcv)} candles")
        return all_ohlcv
    except Exception as e:
        print(f"Error: {e}")
        return all_ohlcv

def ohlcv_to_dataframe(ohlcv):
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df

def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    # Fetch last ~60 days of 1h data
    now = int(datetime.now().timestamp() * 1000)
    sixty_days_ago = now - (60 * 24 * 60 * 60 * 1000)

    all_data = []
    since = sixty_days_ago
    total = 0

    print(f"Fetching {SYMBOL} {TIMEFRAME} data from Binance...")
    while True:
        chunk = fetch_ohlcv(SYMBOL, TIMEFRAME, LIMIT, since)
        if not chunk:
            break
        all_data.extend(chunk)
        total += len(chunk)
        # Move since to last timestamp + 1ms
        since = chunk[-1][0] + 1
        print(f"Total so far: {total} candles")
        if len(chunk) < LIMIT:
            break

    if not all_data:
        print("No data fetched. Generating synthetic data for demo...")
        # Generate synthetic data as fallback
        generate_synthetic_data()
        return

    df = ohlcv_to_dataframe(all_data)
    df.to_csv(OUTPUT)
    print(f"Saved {len(df)} candles to {OUTPUT}")
    print(f"Date range: {df.index[0]} to {df.index[-1]}")
    print(f"Price range: ${df['low'].min():.2f} - ${df['high'].max():.2f}")

def generate_synthetic_data():
    """Fallback: generate realistic synthetic BTC data."""
    import numpy as np
    np.random.seed(42)

    periods = 1000
    base_price = 65000.0
    dates = pd.date_range(end=datetime.now(), periods=periods, freq="1h")

    # Random walk with drift and volatility clustering
    returns = np.random.normal(0.0001, 0.002, periods)
    # Add some trending periods
    for i in range(200, 400):
        returns[i] += 0.0003
    for i in range(600, 800):
        returns[i] -= 0.0002

    price = base_price * np.exp(np.cumsum(returns))
    volume = np.random.lognormal(10, 1, periods)

    df = pd.DataFrame({
        "open": price * (1 - np.random.uniform(0, 0.005, periods)),
        "high": price * (1 + np.random.uniform(0, 0.01, periods)),
        "low": price * (1 - np.random.uniform(0, 0.01, periods)),
        "close": price,
        "volume": volume,
    }, index=dates)
    df["open"] = df["open"].round(2)
    df["high"] = df["high"].round(2)
    df["low"] = df["low"].round(2)
    df["close"] = df["close"].round(2)
    df["volume"] = df["volume"].round(4)

    df.to_csv(OUTPUT)
    print(f"Generated {len(df)} synthetic candles to {OUTPUT}")
    print(f"Date range: {df.index[0]} to {df.index[-1]}")
    print(f"Price range: ${df['low'].min():.2f} - ${df['high'].max():.2f}")

if __name__ == "__main__":
    main()
