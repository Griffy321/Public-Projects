"""
Fetch and cache earnings history for every S&P 500 constituent (historical + current)
using the stable per-ticker endpoint: GET /stable/earnings?symbol={TICKER}

Approach: pull all unique tickers from the cached constituent change history, supplement
with any current S&P 500 members not captured there, then fetch each ticker individually.

Output: data/earnings.parquet  (raw — no filtering; that happens in 03_build_universe.py)
Idempotent: skips fetch if the parquet already exists.

Note: the per-ticker endpoint does not return a `time` (bmo/amc) field. All events will
have time=null and 03_build_universe.py will apply the spec's fallback (treat as amc,
enter at close of D+1). See spec Section 10 for full rationale.
"""

import os
import sys
import time
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
DATA_DIR = ROOT_DIR / "data"
CONSTITUENTS_FILE = DATA_DIR / "constituents.parquet"
OUT_FILE = DATA_DIR / "earnings.parquet"
CONFIG_FILE = ROOT_DIR / "config.env"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv(CONFIG_FILE)
API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    sys.exit("ERROR: FMP_API_KEY not found in config.env")

BASE_URL = "https://financialmodelingprep.com/stable"
EARNINGS_ENDPOINT = f"{BASE_URL}/earnings"
SP500_ENDPOINT = f"{BASE_URL}/sp500-constituent"

BACKTEST_START = pd.Timestamp("2011-05-19")
BACKTEST_END   = pd.Timestamp("2026-05-19")
REQUEST_DELAY  = 0.3  # seconds between API calls

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_all_tickers() -> list[str]:
    if not CONSTITUENTS_FILE.exists():
        sys.exit(f"ERROR: {CONSTITUENTS_FILE} not found. Run 01_fetch_constituents.py first.")

    constituents = pd.read_parquet(CONSTITUENTS_FILE)
    tickers = set(constituents["symbol"].dropna().unique())

    # Add any current S&P 500 members not captured in the change history
    try:
        resp = requests.get(SP500_ENDPOINT, params={"apikey": API_KEY}, timeout=30)
        resp.raise_for_status()
        current = resp.json()
        current_tickers = {r["symbol"] for r in current if r.get("symbol")}
        new = current_tickers - tickers
        if new:
            print(f"  Adding {len(new)} current members absent from change history: {sorted(new)}")
        tickers |= current_tickers
    except Exception as e:
        print(f"  WARNING: could not fetch current S&P 500 list — {e}")

    return sorted(tickers)


def fetch_ticker_earnings(symbol: str) -> list[dict]:
    resp = requests.get(
        EARNINGS_ENDPOINT,
        params={"symbol": symbol, "apikey": API_KEY},
        timeout=30,
    )
    if resp.status_code == 402:
        return []  # plan gate — skip silently
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def normalise(df: pd.DataFrame) -> pd.DataFrame:
    # Rename per-ticker field names to match the calendar endpoint convention
    df = df.rename(columns={
        "epsactual":       "eps",
        "revenueactual":   "revenue",
        "epsestimated":    "epsestimated",
        "revenueestimated": "revenueestimated",
    })
    # time field is absent from this endpoint — add as null for downstream compatibility
    if "time" not in df.columns:
        df["time"] = pd.NA
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if OUT_FILE.exists():
        print(f"Cache hit: {OUT_FILE} already exists. Skipping fetch.")
        df = pd.read_parquet(OUT_FILE)
        print(f"  Loaded {len(df):,} records from cache.")
        return

    print("Resolving ticker universe...")
    tickers = get_all_tickers()
    print(f"  Total tickers to fetch: {len(tickers):,}")

    all_records: list[dict] = []
    failed: list[str] = []

    for symbol in tqdm(tickers, unit="ticker"):
        try:
            records = fetch_ticker_earnings(symbol)
            for r in records:
                r["symbol"] = symbol
            all_records.extend(records)
        except Exception as e:
            tqdm.write(f"  WARNING: {symbol} failed — {e}")
            failed.append(symbol)
        time.sleep(REQUEST_DELAY)

    if not all_records:
        sys.exit("ERROR: No earnings records fetched.")

    df = pd.DataFrame(all_records)
    df.columns = [c.lower() for c in df.columns]

    df = normalise(df)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Filter to backtest window only
    df = df[(df["date"] >= BACKTEST_START) & (df["date"] <= BACKTEST_END)]

    # Deduplicate on (symbol, date)
    before = len(df)
    df = df.drop_duplicates(subset=["symbol", "date"]).reset_index(drop=True)
    dupes_dropped = before - len(df)

    df = df.sort_values(["date", "symbol"]).reset_index(drop=True)

    print(f"\nRecords in window  : {before:,}")
    if dupes_dropped:
        print(f"Duplicates dropped : {dupes_dropped:,}")
    print(f"Records saved      : {len(df):,}")
    print(f"Date range         : {df['date'].min().date()} to {df['date'].max().date()}")
    print(f"Unique tickers     : {df['symbol'].nunique():,}")
    print(f"Columns            : {df.columns.tolist()}")

    if failed:
        print(f"\nWARNING: {len(failed)} ticker(s) failed: {failed}")

    df.to_parquet(OUT_FILE, index=False)
    print(f"\nSaved to {OUT_FILE}")


if __name__ == "__main__":
    main()
