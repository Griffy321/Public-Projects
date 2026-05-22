"""
Phase 2 — Fetch earnings history for all 33 large-cap anchor tickers across 4 sectors.
Uses FMP /stable/earnings per-ticker endpoint. Normalises field names, adds sector column,
calculates surprise scores, and saves:

  data/earnings_all.parquet      — all events in backtest window, all sectors
  data/earnings_triggers.parquet — events with valid eps + epsestimated
                                   (threshold filter applied at runtime in 04)

Idempotent: skips if both parquets exist and contain a 'sector' column (Phase 2 format).
If Phase 1 parquets exist (no sector column), re-fetches all anchors.
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
SCRIPT_DIR  = Path(__file__).resolve().parent
ROOT_DIR    = SCRIPT_DIR.parent
DATA_DIR    = ROOT_DIR / "data"
CONFIG_FILE = ROOT_DIR.parent / "config.env"

OUT_ALL      = DATA_DIR / "earnings_all.parquet"
OUT_TRIGGERS = DATA_DIR / "earnings_triggers.parquet"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv(CONFIG_FILE)
API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    sys.exit("ERROR: FMP_API_KEY not found in config.env")

BASE_URL          = "https://financialmodelingprep.com/stable"
EARNINGS_ENDPOINT = f"{BASE_URL}/earnings"
REQUEST_DELAY     = 0.35

BACKTEST_START = pd.Timestamp("2021-05-20")
BACKTEST_END   = pd.Timestamp("2026-05-20")

# All 33 anchor tickers grouped by sector (Phase 2)
SECTOR_ANCHORS = {
    "Semiconductors": ["MU", "WDC", "NVDA", "AMAT", "LRCX", "MRVL", "AMD", "INTC", "QCOM", "TXN"],
    "Energy":         ["XOM", "CVX", "COP", "EOG", "PXD", "DVN", "HAL", "SLB"],
    "Financials":     ["JPM", "BAC", "WFC", "USB", "PNC", "GS", "MS"],
    "Healthcare":     ["LLY", "JNJ", "UNH", "MRK", "ABBV", "BMY", "AMGN", "GILD"],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def fetch_earnings(ticker: str) -> pd.DataFrame:
    url  = f"{EARNINGS_ENDPOINT}?symbol={ticker}&apikey={API_KEY}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    rename_map = {
        "epsActual":        "eps",
        "epsEstimated":     "epsestimated",
        "revenueActual":    "revenue",
        "revenueEstimated": "revenueestimated",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    keep = [c for c in ["symbol", "date", "eps", "epsestimated", "revenue", "revenueestimated"]
            if c in df.columns]
    df = df[keep].copy()
    df["date"]         = pd.to_datetime(df["date"], errors="coerce")
    df["eps"]          = pd.to_numeric(df.get("eps"),          errors="coerce")
    df["epsestimated"] = pd.to_numeric(df.get("epsestimated"), errors="coerce")
    return df


def calc_surprise(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["surprise"] = (df["eps"] - df["epsestimated"]) / df["epsestimated"].abs()
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # Idempotency: skip if Phase 2 format (sector column) already present
    if OUT_ALL.exists() and OUT_TRIGGERS.exists():
        try:
            existing = pd.read_parquet(OUT_ALL)
            if "sector" in existing.columns:
                trig_df = pd.read_parquet(OUT_TRIGGERS)
                print(f"Cache hit (Phase 2) — {len(existing)} total events, "
                      f"{len(trig_df)} trigger-eligible events.")
                for sector in SECTOR_ANCHORS:
                    n = (existing["sector"] == sector).sum()
                    print(f"  {sector}: {n} events")
                print("Delete parquets to re-fetch.")
                return
            print("Existing parquets are Phase 1 format (no sector column). Re-fetching for Phase 2.")
        except Exception as exc:
            print(f"Could not read existing parquets ({exc}). Re-fetching.")

    all_records = []
    total_anchors = sum(len(v) for v in SECTOR_ANCHORS.values())
    print(f"Fetching earnings for {total_anchors} anchor tickers across 4 sectors…")

    for sector, tickers in SECTOR_ANCHORS.items():
        print(f"\n  [{sector}]")
        for ticker in tqdm(tickers, desc=f"  {sector[:4]}"):
            try:
                df = fetch_earnings(ticker)
                if df.empty:
                    print(f"    {ticker}: no data returned")
                else:
                    df = calc_surprise(df)
                    df["sector"] = sector
                    all_records.append(df)
            except Exception as exc:
                print(f"    {ticker}: ERROR — {exc}")
            time.sleep(REQUEST_DELAY)

    if not all_records:
        sys.exit("ERROR: No earnings data returned for any anchor ticker.")

    earnings = pd.concat(all_records, ignore_index=True)
    earnings = earnings.dropna(subset=["date"])
    earnings = earnings.sort_values(["date", "symbol"]).reset_index(drop=True)

    in_window = (earnings["date"] >= BACKTEST_START) & (earnings["date"] <= BACKTEST_END)
    earnings_window = earnings[in_window].copy()
    earnings_window.to_parquet(OUT_ALL, index=False)
    print(f"\nSaved {len(earnings_window)} events to {OUT_ALL.name}")

    valid_mask = (
        earnings_window["eps"].notna() &
        earnings_window["epsestimated"].notna() &
        (earnings_window["epsestimated"] != 0)
    )
    triggers = earnings_window[valid_mask].copy()
    triggers.to_parquet(OUT_TRIGGERS, index=False)
    print(f"Saved {len(triggers)} trigger-eligible events to {OUT_TRIGGERS.name}")
    print("  (threshold filter is applied at runtime in 04_run_backtest.py)")

    print("\nEvents per sector (trigger-eligible, within backtest window):")
    for sector, tickers in SECTOR_ANCHORS.items():
        sector_triggers = triggers[triggers["sector"] == sector]
        print(f"  {sector}: {len(sector_triggers)} events")
        for ticker in tickers:
            n = (sector_triggers["symbol"] == ticker).sum()
            if n > 0:
                print(f"    {ticker}: {n}")


if __name__ == "__main__":
    main()
