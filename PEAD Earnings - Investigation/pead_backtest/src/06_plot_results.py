"""
Plot PEAD backtest results vs S&P 500 benchmark and print summary statistics.

Steps:
  1. Fetch/cache ^GSPC benchmark from FMP (3 x 5-year chunks — spec Section 2.1 Endpoint 4)
  2. Load data/portfolio_returns.parquet and data/trades.parquet from 05
  3. Align portfolio to benchmark trading calendar (fill inactive days with 0)
  4. Compute cumulative returns, annualised return, Sharpe ratio, max drawdown
  5. Save chart to output/pead_returns_vs_sp500.png
  6. Print summary stats and caveat note to console (spec Section 6.2 / 6.3)
"""

import os
import sys
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import requests
from matplotlib.transforms import blended_transform_factory
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"
CONFIG_FILE = ROOT_DIR / "config.env"

BENCHMARK_FILE = DATA_DIR / "benchmark.parquet"
PORTFOLIO_FILE = DATA_DIR / "portfolio_returns.parquet"
TRADES_FILE    = DATA_DIR / "trades.parquet"
UNIVERSE_FILE  = DATA_DIR / "universe.parquet"
MISSING_FILE   = DATA_DIR / "missing_tickers.txt"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv(CONFIG_FILE)

_holding_file = DATA_DIR / "holding_days.txt"
if not _holding_file.exists():
    sys.exit("ERROR: data/holding_days.txt not found. Run 05_run_backtest.py first.")
HOLDING_DAYS = int(_holding_file.read_text().strip())
CHART_FILE   = OUTPUT_DIR / f"pead_returns_vs_sp500_{HOLDING_DAYS}d.png"
API_KEY = os.getenv("FMP_API_KEY")
if not API_KEY:
    sys.exit("ERROR: FMP_API_KEY not found in config.env")

BASE_URL            = "https://financialmodelingprep.com/stable"
BENCHMARK_ENDPOINT  = f"{BASE_URL}/historical-price-eod/full"

BACKTEST_START = pd.Timestamp("2011-05-19")
BACKTEST_END   = pd.Timestamp("2026-05-19")

# Shaded stress periods on the chart (spec Section 6.1 — 2020 COVID at minimum)
STRESS_BANDS = [
    ("COVID-19\ncrash",           "2020-02-19", "2020-04-07"),
    ("2022 rate-hike\nbear mkt",  "2022-01-03", "2022-10-13"),
]

# ---------------------------------------------------------------------------
# Benchmark fetch
# ---------------------------------------------------------------------------

def fetch_benchmark() -> pd.DataFrame:
    """Fetch ^GSPC EOD closes from FMP in 5-year chunks. Cached to benchmark.parquet."""
    if BENCHMARK_FILE.exists():
        print(f"Cache hit: benchmark.parquet already exists.")
        df = pd.read_parquet(BENCHMARK_FILE)
        print(f"  Loaded {len(df):,} benchmark days.")
        return df

    # FMP restricts EOD calls to a 5-year window per request (spec Section 2.1 Endpoint 4)
    chunks = [
        ("2011-05-19", "2016-05-19"),
        ("2016-05-19", "2021-05-19"),
        ("2021-05-19", "2026-05-19"),
    ]

    all_records: list[dict] = []
    for from_date, to_date in chunks:
        print(f"  Fetching ^GSPC {from_date} → {to_date}...")
        resp = requests.get(
            BENCHMARK_ENDPOINT,
            # Pass ^GSPC literally; requests will URL-encode ^ → %5E automatically
            params={"symbol": "^GSPC", "from": from_date, "to": to_date, "apikey": API_KEY},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        # Handle both bare list and {"historical": [...]} wrapper
        if isinstance(data, dict):
            data = data.get("historical", [])
        all_records.extend(data if isinstance(data, list) else [])
        time.sleep(0.3)

    if not all_records:
        sys.exit("ERROR: No benchmark data returned from FMP. Check API key and plan.")

    df = pd.DataFrame(all_records)
    df.columns = [c.lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "close"])
    df = df[["date", "close"]].drop_duplicates(subset=["date"])
    df = df.sort_values("date").reset_index(drop=True)

    df.to_parquet(BENCHMARK_FILE, index=False)
    print(f"  Saved {len(df):,} benchmark days "
          f"({df['date'].min().date()} to {df['date'].max().date()})")
    return df


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------

def annualised_return(cumulative: pd.Series, n_trading_days: int) -> float:
    """CAGR from a cumulative return series starting at 1.0."""
    total = float(cumulative.iloc[-1]) - 1.0
    years = n_trading_days / 252
    return (1 + total) ** (1 / years) - 1


def sharpe_ratio(daily_returns: pd.Series) -> float:
    """Annualised Sharpe ratio (risk-free rate = 0)."""
    std = daily_returns.std()
    if std == 0:
        return 0.0
    return float(daily_returns.mean() / std * np.sqrt(252))


def max_drawdown(cumulative: pd.Series) -> float:
    """Maximum peak-to-trough drawdown of a cumulative return series."""
    peak = cumulative.cummax()
    return float(((cumulative - peak) / peak).min())


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

def build_chart(dates: pd.Series, bench_cum: pd.Series, strat_cum: pd.Series) -> None:
    fig, ax = plt.subplots(figsize=(13, 7))
    fig.patch.set_facecolor("#f8f9fa")
    ax.set_facecolor("#f8f9fa")

    # Stress-period shading — drawn first so lines render on top
    trans = blended_transform_factory(ax.transData, ax.transAxes)
    for label, start, end in STRESS_BANDS:
        ax.axvspan(pd.Timestamp(start), pd.Timestamp(end),
                   color="#cccccc", alpha=0.55, zorder=0)
        mid = pd.Timestamp(start) + (pd.Timestamp(end) - pd.Timestamp(start)) / 2
        ax.text(mid, 0.97, label, transform=trans,
                ha="center", va="top", fontsize=7.5, color="#666666")

    # Reference line at 1.0
    ax.axhline(1.0, color="#aaaaaa", linewidth=0.8, linestyle="--", zorder=1)

    # Main lines
    ax.plot(dates, bench_cum.values, color="#e67e22", linewidth=1.9,
            label="S&P 500 (benchmark)", zorder=2)
    ax.plot(dates, strat_cum.values, color="#2980b9", linewidth=1.9,
            label="PEAD strategy",       zorder=3)

    # End-point value annotations
    last_date = dates.iloc[-1]
    ax.annotate(f"  {bench_cum.iloc[-1]:.2f}×",
                xy=(last_date, bench_cum.iloc[-1]),
                fontsize=9, color="#e67e22", va="center")
    ax.annotate(f"  {strat_cum.iloc[-1]:.2f}×",
                xy=(last_date, strat_cum.iloc[-1]),
                fontsize=9, color="#2980b9", va="center")

    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.tick_params(axis="x", rotation=0, labelsize=9)
    ax.tick_params(axis="y", labelsize=9)
    ax.set_xlabel("Year", fontsize=10)
    ax.set_ylabel("Cumulative return  (indexed to 1.0)", fontsize=10)
    ax.set_title(
        "Post-Earnings Announcement Drift (PEAD) — S&P 500 Constituents\n"
        f"2011–2026  ·  {HOLDING_DAYS}-day holding period  ·  Equal-weight  ·  No transaction costs",
        fontsize=11, pad=14,
    )
    ax.legend(loc="upper left", fontsize=9, framealpha=0.7)
    ax.grid(axis="y", color="#dddddd", linewidth=0.7, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(CHART_FILE, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Chart saved → {CHART_FILE}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    for f in [PORTFOLIO_FILE, TRADES_FILE, UNIVERSE_FILE]:
        if not f.exists():
            sys.exit(f"ERROR: {f} not found. Run prior scripts first.")

    # -----------------------------------------------------------------------
    # Benchmark
    # -----------------------------------------------------------------------
    print("Fetching/loading benchmark (^GSPC)...")
    bm = fetch_benchmark()
    bm = bm[
        (bm["date"] >= BACKTEST_START) &
        (bm["date"] <= BACKTEST_END)
    ].reset_index(drop=True)
    bm["bm_return"] = bm["close"].pct_change().fillna(0.0)

    # -----------------------------------------------------------------------
    # Align portfolio returns to benchmark calendar
    # -----------------------------------------------------------------------
    port = pd.read_parquet(PORTFOLIO_FILE)
    port["date"] = pd.to_datetime(port["date"])

    # Left join: inactive days (no open trades) get 0 return
    aligned = bm[["date", "bm_return"]].merge(
        port.rename(columns={"portfolio_return": "strat_return"}),
        on="date",
        how="left",
    )
    aligned["strat_return"] = aligned["strat_return"].fillna(0.0)

    # -----------------------------------------------------------------------
    # Cumulative returns (indexed to 1.0 at day 0)
    # -----------------------------------------------------------------------
    aligned["bench_cum"] = (1 + aligned["bm_return"]).cumprod()
    aligned["strat_cum"]  = (1 + aligned["strat_return"]).cumprod()

    n_days = len(aligned)

    # -----------------------------------------------------------------------
    # Summary stats
    # -----------------------------------------------------------------------
    strat_ann  = annualised_return(aligned["strat_cum"],  n_days)
    bench_ann  = annualised_return(aligned["bench_cum"], n_days)
    excess_ann = strat_ann - bench_ann

    strat_sharpe = sharpe_ratio(aligned["strat_return"])
    bench_sharpe = sharpe_ratio(aligned["bm_return"])

    strat_dd = max_drawdown(aligned["strat_cum"])
    bench_dd = max_drawdown(aligned["bench_cum"])

    trades_df  = pd.read_parquet(TRADES_FILE)
    universe_df = pd.read_parquet(UNIVERSE_FILE)
    win_rate = (trades_df["trade_return"] > 0).mean() * 100

    excluded_count = 0
    if MISSING_FILE.exists():
        excluded_count = sum(
            1 for line in MISSING_FILE.read_text().splitlines() if line.strip()
        )

    # -----------------------------------------------------------------------
    # Chart
    # -----------------------------------------------------------------------
    build_chart(aligned["date"], aligned["bench_cum"], aligned["strat_cum"])

    # -----------------------------------------------------------------------
    # Console output — spec Section 6.2
    # -----------------------------------------------------------------------
    print()
    print("=" * 55)
    print(f"Backtest period:         {BACKTEST_START.date()} to {BACKTEST_END.date()}")
    print(f"Total earnings events:   {len(universe_df):,}")
    print(f"Events traded:           {len(trades_df):,}")
    print(f"Tickers excluded:        {excluded_count:,}  (see data/missing_tickers.txt)")
    print()
    print(f"Strategy annualised return:   {strat_ann * 100:+.1f}%")
    print(f"Benchmark annualised return:  {bench_ann * 100:+.1f}%")
    print(f"Excess return (annualised):   {excess_ann * 100:+.1f}%")
    print()
    print(f"Strategy Sharpe ratio:   {strat_sharpe:.2f}")
    print(f"Benchmark Sharpe ratio:  {bench_sharpe:.2f}")
    print()
    print(f"Strategy max drawdown:   {strat_dd * 100:.1f}%")
    print(f"Benchmark max drawdown:  {bench_dd * 100:.1f}%")
    print()
    print(f"Win rate (trades):       {win_rate:.1f}%")
    print("=" * 55)

    # Spec Section 6.3
    print()
    print(
        "NOTE: 184 of ~600 historical constituent tickers have confirmed price data.\n"
        "Pre-2010 bankruptcies (Lehman, Enron, WorldCom, Bear Stearns, Circuit City)\n"
        "are excluded due to unavailable price data. Results may overstate returns\n"
        "slightly due to this partial survivorship bias for the earliest period."
    )


if __name__ == "__main__":
    main()
