"""
Fetch and cache the S&P 500 historical constituent change history from FMP.
Output: data/constituents.parquet
Idempotent: skips fetch if the parquet already exists.
"""

import os
import sys
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
DATA_DIR = ROOT_DIR / "data"
OUT_FILE = DATA_DIR / "constituents.parquet"
CONFIG_FILE = ROOT_DIR / "config.env"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv(CONFIG_FILE)
API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    sys.exit("ERROR: FMP_API_KEY not found in config.env")

BASE_URL = "https://financialmodelingprep.com/stable"
ENDPOINT = f"{BASE_URL}/historical-sp500-constituent"

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def fetch_constituents() -> pd.DataFrame:
    print(f"Fetching S&P 500 constituent history from FMP...")
    resp = requests.get(ENDPOINT, params={"apikey": API_KEY}, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if not data:
        sys.exit("ERROR: API returned empty response. Check API key or plan tier.")

    df = pd.DataFrame(data)

    # Normalise column names to lowercase
    df.columns = [c.lower() for c in df.columns]

    # Spec: handle null / empty removedTicker and removedSecurity
    for col in ("removedticker", "removedsecurity"):
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    # Parse date
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Sort chronologically (oldest first)
    df = df.sort_values("date").reset_index(drop=True)

    print(f"  Records fetched : {len(df):,}")
    print(f"  Date range      : {df['date'].min().date()} to {df['date'].max().date()}")
    return df


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if OUT_FILE.exists():
        print(f"Cache hit: {OUT_FILE} already exists. Skipping fetch.")
        df = pd.read_parquet(OUT_FILE)
        print(f"  Loaded {len(df):,} records from cache.")
        return

    df = fetch_constituents()
    df.to_parquet(OUT_FILE, index=False)
    print(f"Saved to {OUT_FILE}")


if __name__ == "__main__":
    main()
