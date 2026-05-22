"""
Phase 2 — Download yfinance price history for all tickers across 4 sectors.

Downloads:
  - All small-cap candidates from data/candidates_{sector}.parquet (4 sectors)
  - All 33 anchor tickers (reference)
  - Benchmark ETFs: SPY, SOXX, XLE, XLF, XLV

Applies liquidity filters per sector and saves:
  data/prices/{TICKER}.parquet      — per-ticker daily OHLCV (adjusted)
  data/universe_{sector}.parquet    — post-liquidity-filter universe per sector
  data/excluded_tickers.txt         — tickers dropped with sector and reason

Idempotent: skips price files already cached in data/prices/.
Liquidity filter and universe files are regenerated each run.
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
SCRIPT_DIR    = Path(__file__).resolve().parent
ROOT_DIR      = SCRIPT_DIR.parent
DATA_DIR      = ROOT_DIR / "data"
PRICES_DIR    = DATA_DIR / "prices"
EXCLUDED_FILE = DATA_DIR / "excluded_tickers.txt"

DATA_DIR.mkdir(parents=True, exist_ok=True)
PRICES_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FETCH_START        = "2019-01-01"
FETCH_END          = "2026-05-20"
BACKTEST_START     = pd.Timestamp("2021-05-20")
PRE_BACKTEST_START = pd.Timestamp("2019-01-01")
PRE_BACKTEST_END   = pd.Timestamp("2021-05-19")

MIN_BARS          = 504
MIN_VOLUME        = 500_000
MIN_UNIVERSE_SIZE = 10

SECTOR_ANCHORS = {
    "Semiconductors": ["MU", "WDC", "NVDA", "AMAT", "LRCX", "MRVL", "AMD", "INTC", "QCOM", "TXN"],
    "Energy":         ["XOM", "CVX", "COP", "EOG", "PXD", "DVN", "HAL", "SLB"],
    "Financials":     ["JPM", "BAC", "WFC", "USB", "PNC", "GS", "MS"],
    "Healthcare":     ["LLY", "JNJ", "UNH", "MRK", "ABBV", "BMY", "AMGN", "GILD"],
}

BENCHMARKS = ["SPY", "SOXX", "XLE", "XLF", "XLV"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def fetch_and_save(ticker: str) -> pd.DataFrame | None:
    """Download history for one ticker. Returns the DataFrame or None on failure."""
    out_path = PRICES_DIR / f"{ticker}.parquet"
    if out_path.exists():
        return pd.read_parquet(out_path)
    try:
        df = yf.download(ticker, start=FETCH_START, end=FETCH_END,
                         progress=False, auto_adjust=True)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.index = pd.to_datetime(df.index)
        df.to_parquet(out_path)
        return df
    except Exception as exc:
        print(f"  {ticker}: download failed — {exc}")
        return None


def check_liquidity(df: pd.DataFrame) -> tuple[bool, str]:
    """Return (passes, reason_if_excluded)."""
    if len(df) < MIN_BARS:
        return False, f"only {len(df)} bars total (minimum {MIN_BARS})"
    pre = df.loc[PRE_BACKTEST_START:PRE_BACKTEST_END]
    if pre.empty:
        return False, "no data in pre-backtest window (2019-01-01 to 2021-05-19)"
    avg_vol = pre["Volume"].mean()
    if avg_vol < MIN_VOLUME:
        return False, f"avg daily volume {avg_vol:,.0f} < {MIN_VOLUME:,} in pre-backtest window"
    return True, ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # Load all sector candidate files
    sector_candidates: dict[str, list[str]] = {}
    for sector in SECTOR_ANCHORS:
        cand_file = DATA_DIR / f"candidates_{sector.lower()}.parquet"
        if not cand_file.exists():
            sys.exit(
                f"ERROR: {cand_file.name} not found. Run 02_build_universe.py first."
            )
        df      = pd.read_parquet(cand_file)
        tickers = sorted(df["symbol"].dropna().unique().tolist())
        # Exclude anchor tickers from their own sector's small-cap list
        anchor_set = set(SECTOR_ANCHORS[sector])
        tickers    = [t for t in tickers if t not in anchor_set]
        sector_candidates[sector] = tickers
        print(f"Loaded {sector}: {len(tickers)} candidate small-caps")

    all_small_caps = sorted({t for tickers in sector_candidates.values() for t in tickers})
    all_anchors    = sorted({t for tickers in SECTOR_ANCHORS.values() for t in tickers})
    all_tickers    = list(dict.fromkeys(all_small_caps + all_anchors + BENCHMARKS))

    print(
        f"\nFetching prices for {len(all_tickers)} tickers "
        f"({len(all_small_caps)} small-caps, {len(all_anchors)} anchors, "
        f"{len(BENCHMARKS)} benchmarks)…"
    )
    print("Skipping any ticker whose .parquet already exists in data/prices/\n")

    prices: dict[str, pd.DataFrame] = {}
    failed: list[str] = []

    for ticker in tqdm(all_tickers):
        df = fetch_and_save(ticker)
        if df is not None:
            prices[ticker] = df
        else:
            failed.append(ticker)
        time.sleep(0.1)

    if failed:
        print(f"\nFailed to download ({len(failed)}): {failed}")

    # ------------------------------------------------------------------
    # Liquidity filter — per sector
    # ------------------------------------------------------------------
    print("\nApplying liquidity filter per sector…")
    excluded_rows: list[tuple[str, str, str]] = []

    for sector in SECTOR_ANCHORS:
        tickers = sector_candidates[sector]
        passed: list[str] = []

        for ticker in tickers:
            if ticker not in prices:
                excluded_rows.append((ticker, sector, "download failed or no data returned"))
                continue
            ok, reason = check_liquidity(prices[ticker])
            if ok:
                passed.append(ticker)
            else:
                excluded_rows.append((ticker, sector, reason))

        n_excluded = len(tickers) - len(passed)
        print(f"  {sector}: {len(passed)} passed, {n_excluded} excluded")

        if len(passed) < MIN_UNIVERSE_SIZE:
            print(
                f"  WARNING: {sector} has only {len(passed)} tickers after liquidity filter "
                f"(< {MIN_UNIVERSE_SIZE}). Results should be treated with caution."
            )

        # Save per-sector universe (post-liquidity-filter)
        cand_file   = DATA_DIR / f"candidates_{sector.lower()}.parquet"
        cand_df     = pd.read_parquet(cand_file)
        universe_df = cand_df[cand_df["symbol"].isin(passed)].copy()
        out_file    = DATA_DIR / f"universe_{sector.lower()}.parquet"
        universe_df.to_parquet(out_file, index=False)
        print(f"  Saved {len(universe_df)} tickers to {out_file.name}")

    # Write excluded log
    with open(EXCLUDED_FILE, "w") as f:
        f.write("ticker\tsector\treason\n")
        for ticker, sector, reason in excluded_rows:
            f.write(f"{ticker}\t{sector}\t{reason}\n")
    print(f"\n{len(excluded_rows)} excluded tickers logged to {EXCLUDED_FILE.name}")

    # Verify benchmarks
    print()
    for bench in BENCHMARKS:
        if bench not in prices:
            print(f"WARNING: {bench} benchmark not downloaded. Check yfinance and retry.")
        else:
            n_bars = len(prices[bench].loc[BACKTEST_START:])
            print(f"{bench}: {n_bars} bars available from {BACKTEST_START.date()}")


if __name__ == "__main__":
    main()
