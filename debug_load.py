"""Debug: check load_data."""
import sys, pandas as pd
print("start", flush=True)

# Reproduce load_data from optimizer
csv_path = "data/historical_btc_1h.csv"
print(f"loading {csv_path}...", flush=True)
df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
print(f"loaded {len(df)} rows", flush=True)
print(f"cols: {list(df.columns)}", flush=True)
print(f"index name: {df.index.name}", flush=True)
df = df.reset_index()
print(f"after reset: {list(df.columns)}", flush=True)
if "index" in df.columns:
    df.rename(columns={"index": "timestamp"}, inplace=True)
print(f"final: {list(df.columns)}", flush=True)
print("done", flush=True)
