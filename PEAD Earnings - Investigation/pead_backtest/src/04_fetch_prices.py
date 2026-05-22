"""
Fetch and cache per-ticker price history from yfinance for all unique tickers
in the tradeable universe.

For each ticker in universe.parquet:
  - Download daily OHLCV from 2011-05-19 to 2026-05-19 (split- and dividend-adjusted)
  - Apply filters: drop tickers with <200 bars or avg daily volume <100k
  - Cache passing tickers to data/prices/{TICKER}.parquet (date, close, volume columns)
  - Log excluded tickers to data/missing_tickers.txt

Idempotent: skips tickers that already have a cached parquet file.
See spec Section 2.2 and Section 5 for filter rationale and known gaps.
"""

import sys
import time
import pandas as pd
import yfinance as yf
from pathlib import Path
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
DATA_DIR = ROOT_DIR / "data"
PRICES_DIR = DATA_DIR / "prices"
UNIVERSE_FILE = DATA_DIR / "universe.parquet"
MISSING_FILE = DATA_DIR / "missing_tickers.txt"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BACKTEST_START = "2011-05-19"
BACKTEST_END   = "2026-05-19"
MIN_BARS       = 200
MIN_AVG_VOLUME = 100_000
REQUEST_DELAY  = 0.1  # seconds between yfinance calls — respectful pacing

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_excluded_tickers() -> set[str]:
    """Read tickers already logged to missing_tickers.txt to avoid duplicate entries."""
    if not MISSING_FILE.exists():
        return set()
    lines = MISSING_FILE.read_text().splitlines()
    # Format is "TICKER: reason" — split on first colon only
    return {line.split(":")[0].strip() for line in lines if line.strip()}


def append_exclusions(entries: list[tuple[str, str]]) -> None:
    """Append new exclusion entries to missing_tickers.txt, skipping duplicates."""
    existing = load_excluded_tickers()
    new_lines = [
        f"{ticker}: {reason}"
        for ticker, reason in entries
        if ticker not in existing
    ]
    if new_lines:
        with MISSING_FILE.open("a") as f:
            for line in new_lines:
                f.write(line + "\n")


def download_prices(ticker: str) -> pd.DataFrame | None:
    """
    Download adjusted daily OHLCV for one ticker via yfinance.

    Returns a DataFrame with columns [date, close, volume] or None if the
    download fails or returns no data.
    """
    try:
        df = yf.download(
            ticker,
            start=BACKTEST_START,
            end=BACKTEST_END,
            progress=False,
            auto_adjust=True,
        )
    except Exception:
        return None

    if df is None or df.empty:
        return None

    # Flatten MultiIndex columns — defensive guard for single-ticker downloads
    # in some yfinance >= 1.0 builds
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.columns = [c.lower() for c in df.columns]

    # Bring the DatetimeIndex into a regular column named "date"
    df.index.name = "date"
    df = df.reset_index()

    # Strip timezone info if present (yfinance >= 1.0 sometimes returns tz-aware)
    if pd.api.types.is_datetime64tz_dtype(df["date"]):
        df["date"] = df["date"].dt.tz_convert(None)

    df["date"] = pd.to_datetime(df["date"])

    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    PRICES_DIR.mkdir(parents=True, exist_ok=True)

    if not UNIVERSE_FILE.exists():
        sys.exit(f"ERROR: {UNIVERSE_FILE} not found. Run 03_build_universe.py first.")

    universe = pd.read_parquet(UNIVERSE_FILE)
    tickers = sorted(universe["symbol"].dropna().unique())

    already_cached = sum(1 for t in tickers if (PRICES_DIR / f"{t}.parquet").exists())
    to_fetch = len(tickers) - already_cached

    print(f"Unique tickers in universe : {len(tickers):,}")
    print(f"Already cached             : {already_cached:,}")
    print(f"To fetch                   : {to_fetch:,}")
    print()

    new_exclusions: list[tuple[str, str]] = []
    fetched = 0
    skipped = 0

    for ticker in tqdm(tickers, unit="ticker"):
        out_path = PRICES_DIR / f"{ticker}.parquet"

        if out_path.exists():
            skipped += 1
            continue

        df = download_prices(ticker)

        if df is None or df.empty:
            tqdm.write(f"  EXCLUDED {ticker}: no data from yfinance")
            new_exclusions.append((ticker, "no_data"))
            time.sleep(REQUEST_DELAY)
            continue

        if len(df) < MIN_BARS:
            tqdm.write(f"  EXCLUDED {ticker}: insufficient bars ({len(df)})")
            new_exclusions.append((ticker, f"insufficient_bars ({len(df)} bars)"))
            time.sleep(REQUEST_DELAY)
            continue

        if "volume" not in df.columns or "close" not in df.columns:
            tqdm.write(f"  EXCLUDED {ticker}: missing close or volume column")
            new_exclusions.append((ticker, "missing_columns"))
            time.sleep(REQUEST_DELAY)
            continue

        avg_vol = df["volume"].mean()
        if avg_vol < MIN_AVG_VOLUME:
            tqdm.write(f"  EXCLUDED {ticker}: avg daily volume {avg_vol:,.0f} < {MIN_AVG_VOLUME:,}")
            new_exclusions.append((ticker, f"illiquid (avg_vol: {avg_vol:,.0f})"))
            time.sleep(REQUEST_DELAY)
            continue

        df[["date", "close", "volume"]].to_parquet(out_path, index=False)
        fetched += 1
        time.sleep(REQUEST_DELAY)

    if new_exclusions:
        append_exclusions(new_exclusions)

    # Summary
    cached_total = sum(1 for t in tickers if (PRICES_DIR / f"{t}.parquet").exists())
    excluded_total = len(tickers) - cached_total

    print(f"\nRun summary")
    print(f"  Fetched this run   : {fetched:,}")
    print(f"  Skipped (cached)   : {skipped:,}")
    print(f"  Excluded this run  : {len(new_exclusions):,}")
    print(f"  Cached total       : {cached_total:,} / {len(tickers):,} tickers")
    print(f"  Total excluded     : {excluded_total:,}")
    if MISSING_FILE.exists():
        print(f"  Exclusion log      : {MISSING_FILE}")


if __name__ == "__main__":
    main()
