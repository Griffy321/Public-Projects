"""
Build the point-in-time tradeable universe.

Joins earnings events to S&P 500 constituent history to produce one row per
tradeable event, using backward-reconstruction of index membership so only
events where the ticker was actually in the S&P 500 on that date are kept.

Filters applied (per spec Section 5):
  - epsestimated must be non-null and non-zero
  - eps (actual) must be non-null
  - ticker must be a confirmed S&P 500 constituent on the earnings date

Output: data/universe.parquet
Idempotent: skips build if output already exists.
"""

import bisect
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
CONSTITUENTS_FILE = DATA_DIR / "constituents.parquet"
EARNINGS_FILE     = DATA_DIR / "earnings.parquet"
OUT_FILE          = DATA_DIR / "universe.parquet"
CONFIG_FILE       = ROOT_DIR / "config.env"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv(CONFIG_FILE)
API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    sys.exit("ERROR: FMP_API_KEY not found in config.env")

SP500_ENDPOINT = "https://financialmodelingprep.com/stable/sp500-constituent"

# ---------------------------------------------------------------------------
# Constituent reconstruction
# ---------------------------------------------------------------------------
def fetch_current_members() -> set[str]:
    resp = requests.get(SP500_ENDPOINT, params={"apikey": API_KEY}, timeout=30)
    resp.raise_for_status()
    return {r["symbol"] for r in resp.json() if r.get("symbol")}


def build_snapshots(changes_df: pd.DataFrame, current_members: set[str]):
    """
    Reconstruct point-in-time S&P 500 membership using backward walk.

    Starting from today's S&P 500, reverses each recorded addition/removal
    (most recent first) to derive what the index looked like on every change date.

    Returns:
        sorted_dates  — list of pd.Timestamp, all unique change dates ascending
        snapshots     — dict[Timestamp, frozenset[str]]  constituent set FROM each date
        genesis       — frozenset[str]  constituent set before the first recorded change
    """
    sorted_dates = sorted(changes_df["date"].dropna().unique())

    current = set(current_members)
    snapshots: dict = {}

    for change_date in reversed(sorted_dates):
        # Record the constituent set that applies FROM this date onward
        snapshots[change_date] = frozenset(current)

        # Reverse all changes on this date to recover the state before it
        day = changes_df[changes_df["date"] == change_date]
        for _, row in day.iterrows():
            current.discard(row["symbol"])
            if row["removedticker"]:
                current.add(row["removedticker"])

    genesis = frozenset(current)
    return sorted_dates, snapshots, genesis


def lookup_constituent(symbol: str, query_date: pd.Timestamp,
                       sorted_dates: list, snapshots: dict,
                       genesis: frozenset) -> bool:
    """O(log n) point-in-time membership check via binary search."""
    if not sorted_dates or query_date < sorted_dates[0]:
        return symbol in genesis
    idx = bisect.bisect_right(sorted_dates, query_date) - 1
    return symbol in snapshots[sorted_dates[idx]]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if OUT_FILE.exists():
        print(f"Cache hit: {OUT_FILE} already exists. Skipping build.")
        df = pd.read_parquet(OUT_FILE)
        print(f"  Loaded {len(df):,} tradeable events.")
        return

    for f in [CONSTITUENTS_FILE, EARNINGS_FILE]:
        if not f.exists():
            sys.exit(f"ERROR: {f} not found. Run prior scripts first.")

    changes = pd.read_parquet(CONSTITUENTS_FILE)
    events  = pd.read_parquet(EARNINGS_FILE)

    print(f"Earnings events loaded     : {len(events):,}")

    # -----------------------------------------------------------------------
    # Filter 1: EPS data quality
    # -----------------------------------------------------------------------
    before = len(events)
    events = events[events["epsestimated"].notna() & (events["epsestimated"] != 0)]
    events = events[events["eps"].notna()]
    events = events.reset_index(drop=True)
    print(f"After EPS quality filter   : {len(events):,}  (dropped {before - len(events):,})")

    # -----------------------------------------------------------------------
    # Build point-in-time snapshots
    # -----------------------------------------------------------------------
    print("\nFetching current S&P 500 members...")
    current_members = fetch_current_members()
    print(f"  Current members : {len(current_members):,}")

    print("Building constituent snapshots (backward reconstruction)...")
    sorted_dates, snapshots, genesis = build_snapshots(changes, current_members)
    print(f"  Change dates    : {len(sorted_dates):,}")
    print(f"  Genesis set     : {len(genesis):,} tickers (pre-{sorted_dates[0].year if sorted_dates else '?'})")

    # -----------------------------------------------------------------------
    # Filter 2: point-in-time constituent membership
    # -----------------------------------------------------------------------
    print("\nApplying point-in-time constituent filter...")
    mask = [
        lookup_constituent(row.symbol, row.date, sorted_dates, snapshots, genesis)
        for row in events.itertuples(index=False)
    ]
    before = len(events)
    events = events[mask].reset_index(drop=True)
    print(f"After constituent filter   : {len(events):,}  (dropped {before - len(events):,})")

    # -----------------------------------------------------------------------
    # Compute surprise score
    # -----------------------------------------------------------------------
    events["surprise"] = (events["eps"] - events["epsestimated"]) / events["epsestimated"].abs()

    # -----------------------------------------------------------------------
    # Select output columns
    # -----------------------------------------------------------------------
    keep = ["symbol", "date", "eps", "epsestimated", "revenue",
            "revenueestimated", "time", "surprise"]
    keep = [c for c in keep if c in events.columns]
    universe = events[keep].copy()

    universe.to_parquet(OUT_FILE, index=False)

    print(f"\nTradeable events saved     : {len(universe):,}")
    print(f"Unique tickers             : {universe['symbol'].nunique():,}")
    print(f"Date range                 : {universe['date'].min().date()} to {universe['date'].max().date()}")
    print(f"Surprise score range       : {universe['surprise'].min():.2f} to {universe['surprise'].max():.2f}")
    print(f"Surprise score median      : {universe['surprise'].median():.4f}")
    print(f"\nSaved to {OUT_FILE}")


if __name__ == "__main__":
    main()
