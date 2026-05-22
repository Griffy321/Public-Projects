"""
Run the PEAD backtest.

For each tradeable event in universe.parquet:
  - Entry: close of D+1, treating all events as amc (spec Section 10.5 — time field is null).
    If D+1 is not a trading day, advance to the next available date in the price calendar.
  - Exit: close of entry + 10 trading days (price calendar), or last available close if
    the stock is delisted before the 10th day.
  - Daily portfolio return = equal-weighted mean of all active trade daily returns on that day.
  - Overlapping positions for the same ticker are allowed (spec Section 5).

Outputs:
  data/trades.parquet            — per-trade results (symbol, dates, prices, return, surprise)
  data/portfolio_returns.parquet — daily portfolio returns for active trading days only.
    Note: 06_plot_results.py reindexes this to the benchmark calendar, filling inactive days
    with 0, before computing annualised stats and cumulative curves.

Idempotent: skips if both output files already exist.
"""

import sys
import numpy as np
import pandas as pd
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
TRADES_FILE = DATA_DIR / "trades.parquet"
PORTFOLIO_FILE = DATA_DIR / "portfolio_returns.parquet"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
HOLDING_DAYS = 45   # trading days
# To change the holding period:
#   1. Update HOLDING_DAYS here and in 06_plot_results.py (must match).
#   2. Delete the two stale cached outputs so the idempotency check re-runs the backtest:
#
#      Remove-Item "c:\Users\james\OneDrive\Desktop\Public-Projects\Earnings Investigation\pead_backtest\data\trades.parquet"
#      Remove-Item "c:\Users\james\OneDrive\Desktop\Public-Projects\Earnings Investigation\pead_backtest\data\portfolio_returns.parquet"
#
#   Charts in output\ are named by holding period (e.g. _10d.png, _30d.png),
#   so previous charts are preserved automatically — no need to delete them.

# One-way transaction cost in basis points (spread + commission).
# 5 bps each way = 10 bps round-trip, a realistic estimate for liquid S&P 500
# constituents (typical bid-ask spread 2–4 bps + small commission).
COST_BPS = 5
COST     = COST_BPS / 10_000

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_excluded_tickers() -> set[str]:
    if not MISSING_FILE.exists():
        return set()
    return {
        line.split(":")[0].strip()
        for line in MISSING_FILE.read_text().splitlines()
        if line.strip()
    }


def load_price(ticker: str) -> pd.DataFrame | None:
    path = PRICES_DIR / f"{ticker}.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def find_entry_idx(earnings_date: pd.Timestamp, price_dates: pd.Series) -> int | None:
    """
    Return the positional index of the entry close in price_dates.

    Entry is at close of D+1 (amc fallback). If D+1 is not a trading day,
    the first available trading day on or after D+1 is used.
    Returns None if the price series has no data on or after D+1.
    """
    target = earnings_date + pd.Timedelta(days=1)
    candidates = price_dates[price_dates >= target]
    if candidates.empty:
        return None
    # candidates.index[0] is the pandas label, which equals the positional index
    # because price_df was reset_index(drop=True) before this call.
    return int(candidates.index[0])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if TRADES_FILE.exists() and PORTFOLIO_FILE.exists():
        print("Cache hit: both output files already exist. Skipping backtest.")
        trades = pd.read_parquet(TRADES_FILE)
        port = pd.read_parquet(PORTFOLIO_FILE)
        print(f"  Trades loaded          : {len(trades):,}")
        print(f"  Portfolio days loaded  : {len(port):,}")
        return

    if not UNIVERSE_FILE.exists():
        sys.exit(f"ERROR: {UNIVERSE_FILE} not found. Run 03_build_universe.py first.")

    universe = pd.read_parquet(UNIVERSE_FILE)
    universe["date"] = pd.to_datetime(universe["date"])

    excluded = load_excluded_tickers()
    tickers = sorted(universe["symbol"].unique())

    print(f"Total events in universe  : {len(universe):,}")
    print(f"Unique tickers            : {len(tickers):,}")
    print(f"Tickers excluded (04)     : {len(excluded):,}")
    print(f"Transaction cost          : {COST_BPS} bps each way ({COST_BPS * 2} bps round-trip)")
    print()

    trade_records: list[dict] = []
    # One row per (active trade, day): date + that trade's daily return.
    # Grouping by date and taking the mean gives equal-weight portfolio daily returns.
    daily_contributions: list[tuple[pd.Timestamp, float]] = []

    skipped_no_price = 0
    skipped_no_entry = 0
    skipped_bad_price = 0

    for ticker in tqdm(tickers, unit="ticker"):
        price_df = load_price(ticker)
        if price_df is None:
            skipped_no_price += int((universe["symbol"] == ticker).sum())
            continue

        price_dates = price_df["date"]
        closes = price_df["close"].values  # numpy array — positional indexing

        ticker_events = universe[universe["symbol"] == ticker]

        for row in ticker_events.itertuples(index=False):
            entry_idx = find_entry_idx(row.date, price_dates)
            if entry_idx is None:
                skipped_no_entry += 1
                continue

            # Exit at the 10th trading day after entry, capped at the last available bar.
            exit_idx = min(entry_idx + HOLDING_DAYS, len(price_df) - 1)

            entry_price = closes[entry_idx]
            exit_price = closes[exit_idx]

            if pd.isna(entry_price) or pd.isna(exit_price) or entry_price == 0:
                skipped_bad_price += 1
                continue

            entry_date = price_dates.iloc[entry_idx]
            exit_date = price_dates.iloc[exit_idx]
            # Net of costs: pay spread/commission to enter and to exit
            trade_return = (exit_price * (1 - COST)) / (entry_price * (1 + COST)) - 1

            trade_records.append({
                "symbol":        ticker,
                "earnings_date": row.date,
                "entry_date":    entry_date,
                "exit_date":     exit_date,
                "entry_price":   entry_price,
                "exit_price":    exit_price,
                "trade_return":  trade_return,
                "surprise":      row.surprise,
            })

            # Accumulate daily returns for each day in the holding window.
            # Day entry_idx is the entry close (t=0); returns are earned from
            # entry_idx+1 through exit_idx (inclusive).
            for t in range(entry_idx + 1, exit_idx + 1):
                prev_close = closes[t - 1]
                curr_close = closes[t]
                if prev_close == 0 or pd.isna(prev_close) or pd.isna(curr_close):
                    continue
                daily_ret = curr_close / prev_close - 1
                if t == entry_idx + 1:
                    daily_ret -= COST  # entry cost: spread/commission to buy
                if t == exit_idx:
                    daily_ret -= COST  # exit cost: spread/commission to sell
                daily_contributions.append((price_dates.iloc[t], daily_ret))

    print(f"Results")
    print(f"  Events traded          : {len(trade_records):,}")
    print(f"  Skipped — no price     : {skipped_no_price:,}")
    print(f"  Skipped — no entry day : {skipped_no_entry:,}")
    print(f"  Skipped — bad price    : {skipped_bad_price:,}")

    if not trade_records:
        sys.exit("ERROR: No trades generated. Check that data/prices/ is populated.")

    # -----------------------------------------------------------------------
    # Per-trade output
    # -----------------------------------------------------------------------
    trades_df = pd.DataFrame(trade_records)
    trades_df.to_parquet(TRADES_FILE, index=False)
    (DATA_DIR / "holding_days.txt").write_text(str(HOLDING_DAYS))

    win_rate = (trades_df["trade_return"] > 0).mean() * 100
    print(f"  Win rate (trades)      : {win_rate:.1f}%")
    print(f"  Median trade return    : {trades_df['trade_return'].median() * 100:.2f}%")
    print(f"  Mean trade return      : {trades_df['trade_return'].mean() * 100:.2f}%")

    # -----------------------------------------------------------------------
    # Daily portfolio returns (equal-weight across all active trades each day)
    # -----------------------------------------------------------------------
    daily_df = pd.DataFrame(daily_contributions, columns=["date", "daily_return"])
    portfolio_returns = (
        daily_df
        .groupby("date")["daily_return"]
        .mean()
        .reset_index()
        .rename(columns={"daily_return": "portfolio_return"})
        .sort_values("date")
        .reset_index(drop=True)
    )
    portfolio_returns.to_parquet(PORTFOLIO_FILE, index=False)

    # Cumulative return: product over active days only.
    # Inactive days (no open trades) contribute a factor of 1.0 and don't
    # change the total, so this equals the true 15-year cumulative return.
    cumulative = (1 + portfolio_returns["portfolio_return"]).prod() - 1

    print(f"\nPortfolio")
    print(f"  Active trading days    : {len(portfolio_returns):,}")
    print(f"  Date range             : {portfolio_returns['date'].min().date()} "
          f"to {portfolio_returns['date'].max().date()}")
    print(f"  Cumulative return      : {cumulative * 100:.1f}%")
    print(f"  (Annualised stats computed in 06_plot_results.py against the benchmark calendar)")

    print(f"\nSaved")
    print(f"  {TRADES_FILE}")
    print(f"  {PORTFOLIO_FILE}")


if __name__ == "__main__":
    main()
