"""
Phase 2 — Build small-cap candidate universes for all 4 sectors.

For each sector:
  1. FMP stock screener with sector+industry filters ($100M–$2B, NASDAQ/NYSE, US)
     If < 10 results, broadens to sector-only filter and logs the broadening.
  2. FMP stock-peers for each anchor — catch tickers missed by screener
  3. Profile endpoint — validate market cap for peer-sourced tickers
  4. Exclude anchor tickers from each sector's universe
  5. Save to data/candidates_{sector}.parquet

Idempotent: skips sectors whose candidate parquet already exists.
For Semiconductors: if data/small_cap_candidates.parquet exists (Phase 1), copies it
to candidates_semiconductors.parquet rather than re-fetching.
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

DATA_DIR.mkdir(parents=True, exist_ok=True)

PHASE1_SEMI_FILE = DATA_DIR / "small_cap_candidates.parquet"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv(CONFIG_FILE)
API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    sys.exit("ERROR: FMP_API_KEY not found in config.env")

BASE_URL      = "https://financialmodelingprep.com/stable"
REQUEST_DELAY = 0.35
MKTCAP_MIN    = 100_000_000
MKTCAP_MAX    = 2_000_000_000
MIN_CANDIDATES = 10

SECTOR_ANCHORS = {
    "Semiconductors": {"MU", "WDC", "NVDA", "AMAT", "LRCX", "MRVL", "AMD", "INTC", "QCOM", "TXN"},
    "Energy":         {"XOM", "CVX", "COP", "EOG", "PXD", "DVN", "HAL", "SLB"},
    "Financials":     {"JPM", "BAC", "WFC", "USB", "PNC", "GS", "MS"},
    "Healthcare":     {"LLY", "JNJ", "UNH", "MRK", "ABBV", "BMY", "AMGN", "GILD"},
}

# FMP sector/industry filter params per sector
SECTOR_SCREENER = {
    "Semiconductors": {"sector": "Technology",         "industry": "Semiconductors"},
    "Energy":         {"sector": "Energy",             "industry": "Oil & Gas E&P"},
    "Financials":     {"sector": "Financial Services", "industry": "Banks—Regional"},
    "Healthcare":     {"sector": "Healthcare",         "industry": "Biotechnology"},
}

# Tracks which sectors needed broadening (logged to console, see spec Section 12)
BROADENED_SECTORS: list[str] = []

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get(url: str) -> dict | list:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_screener(sector_key: str, include_industry: bool = True) -> list[dict]:
    params = SECTOR_SCREENER[sector_key]
    url = f"{BASE_URL}/company-screener?sector={params['sector']}"
    if include_industry:
        url += f"&industry={params['industry']}"
    url += (
        f"&marketCapMoreThan={MKTCAP_MIN}"
        f"&marketCapLessThan={MKTCAP_MAX}"
        f"&exchange=NASDAQ,NYSE"
        f"&country=US"
        f"&apikey={API_KEY}"
    )
    data = get(url)
    return data if isinstance(data, list) else []


def fetch_peers(anchor: str) -> list[str]:
    url  = f"{BASE_URL}/stock-peers?symbol={anchor}&apikey={API_KEY}"
    data = get(url)
    if isinstance(data, list) and data:
        peers = []
        for item in data:
            if isinstance(item, dict):
                peers.extend(item.get("peersList", []))
            elif isinstance(item, str):
                peers.append(item)
        return peers
    return []


def fetch_profile(ticker: str) -> dict:
    url  = f"{BASE_URL}/profile?symbol={ticker}&apikey={API_KEY}"
    data = get(url)
    if isinstance(data, list) and data:
        return data[0]
    if isinstance(data, dict):
        return data
    return {}


def results_to_rows(results: list[dict], anchors: set[str], source: str) -> list[dict]:
    rows = []
    for item in results:
        sym = str(item.get("symbol", "")).upper()
        if sym and sym not in anchors:
            rows.append({
                "symbol":            sym,
                "companyName":       item.get("companyName", ""),
                "marketCap":         item.get("marketCap", None),
                "sector":            item.get("sector", ""),
                "industry":          item.get("industry", ""),
                "exchangeShortName": item.get("exchangeShortName", ""),
                "country":           item.get("country", ""),
                "source":            source,
            })
    return rows


def build_sector_universe(sector_key: str) -> pd.DataFrame:
    anchors = SECTOR_ANCHORS[sector_key]

    # Semiconductors: reuse Phase 1 file if available
    if sector_key == "Semiconductors" and PHASE1_SEMI_FILE.exists():
        print(f"  Using Phase 1 candidates file: {PHASE1_SEMI_FILE.name}")
        df = pd.read_parquet(PHASE1_SEMI_FILE)
        df = df[~df["symbol"].isin(anchors)].copy()
        return df

    # Step 1 — Screener with industry filter
    print(f"  Calling FMP screener (with industry)…", end=" ", flush=True)
    try:
        results = fetch_screener(sector_key, include_industry=True)
    except Exception as exc:
        print(f"ERROR: {exc}")
        results = []

    screener_tickers: set[str] = set()
    if results:
        df_raw = pd.DataFrame(results)
        if "symbol" in df_raw.columns:
            screener_tickers = set(df_raw["symbol"].dropna().str.upper()) - anchors
    print(f"{len(screener_tickers)} non-anchor tickers")
    time.sleep(REQUEST_DELAY)

    # Broaden if too few results (spec Section 2.1)
    if len(screener_tickers) < MIN_CANDIDATES:
        print(f"  Only {len(screener_tickers)} candidates — broadening to sector-only filter…", end=" ")
        BROADENED_SECTORS.append(sector_key)
        try:
            results_broad = fetch_screener(sector_key, include_industry=False)
        except Exception as exc:
            print(f"ERROR: {exc}")
            results_broad = []
        if results_broad:
            df_broad = pd.DataFrame(results_broad)
            if "symbol" in df_broad.columns:
                screener_tickers = set(df_broad["symbol"].dropna().str.upper()) - anchors
            results = results_broad
        print(f"{len(screener_tickers)} non-anchor tickers (broadened)")
        time.sleep(REQUEST_DELAY)

    rows = results_to_rows(results, anchors, "screener")

    # Step 2 — Peers for each anchor
    all_peer_tickers: set[str] = set()
    print(f"  Fetching peers for {len(anchors)} anchors…")
    for anchor in tqdm(sorted(anchors), desc=f"  {sector_key[:4]} peers"):
        try:
            peers = fetch_peers(anchor)
            all_peer_tickers |= {p.upper() for p in peers if isinstance(p, str)}
        except Exception as exc:
            print(f"    {anchor}: peers failed — {exc}")
        time.sleep(REQUEST_DELAY)

    new_peers = all_peer_tickers - screener_tickers - anchors
    print(f"  {len(new_peers)} peer tickers not already in screener")

    # Step 3 — Validate new peers via profile
    if new_peers:
        print(f"  Validating {len(new_peers)} peer tickers via profile endpoint…")
        for ticker in tqdm(sorted(new_peers), desc=f"  {sector_key[:4]} profiles"):
            try:
                profile  = fetch_profile(ticker)
                mkt_cap  = profile.get("mktCap", 0) or 0
                country  = (profile.get("country") or "").upper()
                exchange = (profile.get("exchangeShortName") or "").upper()
                if (MKTCAP_MIN <= mkt_cap <= MKTCAP_MAX
                        and country == "US"
                        and exchange in {"NASDAQ", "NYSE"}):
                    rows.append({
                        "symbol":            ticker,
                        "companyName":       profile.get("companyName", ""),
                        "marketCap":         mkt_cap,
                        "sector":            profile.get("sector", ""),
                        "industry":          profile.get("industry", ""),
                        "exchangeShortName": exchange,
                        "country":           country,
                        "source":            "peers",
                    })
            except Exception as exc:
                print(f"    {ticker}: profile failed — {exc}")
            time.sleep(REQUEST_DELAY)

    if not rows:
        print(f"WARNING: {sector_key} universe is empty.")
        return pd.DataFrame()

    candidates = pd.DataFrame(rows).drop_duplicates(subset="symbol").reset_index(drop=True)
    return candidates


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    for sector_key in SECTOR_ANCHORS:
        out_file = DATA_DIR / f"candidates_{sector_key.lower()}.parquet"

        if out_file.exists():
            df = pd.read_parquet(out_file)
            print(f"Cache hit — {sector_key}: {len(df)} candidates. Skipping.")
            continue

        print(f"\n{'─'*60}")
        print(f"Building universe: {sector_key}")
        print(f"{'─'*60}")

        candidates = build_sector_universe(sector_key)

        if candidates.empty:
            print(f"WARNING: {sector_key} universe is empty — saving empty parquet.")
        else:
            src_counts = candidates.get("source", pd.Series()).value_counts()
            print(f"  Total candidates: {len(candidates)}")
            for src, cnt in src_counts.items():
                print(f"    {src}: {cnt}")
            ticker_list = sorted(candidates["symbol"].tolist())
            preview = ticker_list[:20]
            print(f"  Tickers: {preview}{'...' if len(ticker_list) > 20 else ''}")

        candidates.to_parquet(out_file, index=False)
        print(f"  Saved to {out_file.name}")

    if BROADENED_SECTORS:
        print(f"\nNOTE (spec Section 12): Broadened to sector-only screener for: {BROADENED_SECTORS}")
        print("  These sectors had < 10 candidates from the industry-level filter.")

    print("\nAll sector candidate files ready.")


if __name__ == "__main__":
    main()
