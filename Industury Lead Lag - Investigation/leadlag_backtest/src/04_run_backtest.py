"""
Phase 2 — Core backtest engine — Lead-Lag strategy across 4 sectors.

Loads:
  data/earnings_triggers.parquet      — all 33 anchors, all sectors (sector column required)
  data/universe_{sector}.parquet      — per-sector small-cap universe (post-liquidity-filter)
  data/prices/{TICKER}.parquet        — daily adjusted closes

Runs 12 parameter combinations (3 thresholds × 4 hold periods).
Primary parameters locked from Phase 1 heatmap: BEAT_THRESHOLD=10%, HOLD_DAYS=20.

Saves per-combination results to data/results/:
  portfolio_returns_bt{N}_hd{N}.parquet  — daily returns: combined + per-sector + benchmarks
  trades_bt{N}_hd{N}.parquet            — individual trade records (all sectors)
  sweep_sharpes.parquet                 — Sharpe grid for heatmap

Prints full summary statistics for primary parameters.
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR  = Path(__file__).resolve().parent
ROOT_DIR    = SCRIPT_DIR.parent
DATA_DIR    = ROOT_DIR / "data"
RESULTS_DIR = DATA_DIR / "results"
PRICES_DIR  = DATA_DIR / "prices"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------
BEAT_THRESHOLDS = [0.03, 0.05, 0.10]
HOLD_DAYS_LIST  = [5, 10, 20, 60]

PRIMARY_BEAT_THRESHOLD = 0.10
PRIMARY_HOLD_DAYS      = 20
MAX_ENTRY_SLIP         = 3

BACKTEST_START = pd.Timestamp("2021-05-20")
BACKTEST_END   = pd.Timestamp("2026-05-20")

SECTORS = ["Semiconductors", "Energy", "Financials", "Healthcare"]

SECTOR_ANCHORS = {
    "Semiconductors": ["MU", "WDC", "NVDA", "AMAT", "LRCX", "MRVL", "AMD", "INTC", "QCOM", "TXN"],
    "Energy":         ["XOM", "CVX", "COP", "EOG", "PXD", "DVN", "HAL", "SLB"],
    "Financials":     ["JPM", "BAC", "WFC", "USB", "PNC", "GS", "MS"],
    "Healthcare":     ["LLY", "JNJ", "UNH", "MRK", "ABBV", "BMY", "AMGN", "GILD"],
}

SECTOR_ETFS = {
    "Semiconductors": "SOXX",
    "Energy":         "XLE",
    "Financials":     "XLF",
    "Healthcare":     "XLV",
}

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
def load_data() -> tuple[pd.DataFrame, dict[str, list[str]], dict[str, pd.Series]]:
    triggers_file = DATA_DIR / "earnings_triggers.parquet"
    if not triggers_file.exists():
        sys.exit("ERROR: earnings_triggers.parquet not found. Run 01_fetch_earnings_triggers.py first.")

    triggers = pd.read_parquet(triggers_file)
    triggers["date"] = pd.to_datetime(triggers["date"])

    if "sector" not in triggers.columns:
        sys.exit(
            "ERROR: earnings_triggers.parquet lacks 'sector' column.\n"
            "Re-run 01_fetch_earnings_triggers.py to generate Phase 2 format."
        )

    sector_universes: dict[str, list[str]] = {}
    for sector in SECTORS:
        uni_file = DATA_DIR / f"universe_{sector.lower()}.parquet"
        if not uni_file.exists():
            sys.exit(f"ERROR: {uni_file.name} not found. Run 03_fetch_prices.py first.")
        df      = pd.read_parquet(uni_file)
        tickers = sorted(df["symbol"].dropna().unique().tolist())
        sector_universes[sector] = tickers

    # Load closes for all required tickers
    all_small_caps = sorted({t for tickers in sector_universes.values() for t in tickers})
    benchmarks     = ["SPY"] + list(SECTOR_ETFS.values())
    all_load       = list(dict.fromkeys(all_small_caps + benchmarks))

    closes: dict[str, pd.Series] = {}
    missing: list[str] = []
    for ticker in all_load:
        pf = PRICES_DIR / f"{ticker}.parquet"
        if pf.exists():
            df = pd.read_parquet(pf)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if "Close" in df.columns:
                closes[ticker] = df["Close"].dropna()
        else:
            missing.append(ticker)

    if missing:
        print(
            f"WARNING: No price file for {len(missing)} tickers: "
            f"{missing[:10]}{'...' if len(missing) > 10 else ''}"
        )

    for bench in benchmarks:
        if bench not in closes:
            sys.exit(f"ERROR: {bench} price data not found. Run 03_fetch_prices.py first.")

    return triggers, sector_universes, closes


# ---------------------------------------------------------------------------
# Trading day utilities
# ---------------------------------------------------------------------------
def get_trading_dates(closes: dict[str, pd.Series]) -> pd.DatetimeIndex:
    """Use SPY as the master trading calendar for Phase 2."""
    return closes["SPY"].loc[BACKTEST_START:BACKTEST_END].index


def next_trading_day_after(
    date: pd.Timestamp, trading_dates: pd.DatetimeIndex
) -> pd.Timestamp | None:
    pos = trading_dates.searchsorted(date, side="right")
    return trading_dates[pos] if pos < len(trading_dates) else None


def get_price_on_or_after(
    closes: pd.Series, date: pd.Timestamp, max_lag: int = MAX_ENTRY_SLIP
) -> float | None:
    idx = closes.index
    pos = idx.searchsorted(date)
    for offset in range(max_lag + 1):
        i = pos + offset
        if i >= len(idx):
            break
        price = closes.iloc[i]
        if pd.notna(price) and price > 0:
            return float(price)
    return None


def trading_day_pos(
    date: pd.Timestamp, trading_dates: pd.DatetimeIndex
) -> int | None:
    pos = trading_dates.searchsorted(date)
    if pos < len(trading_dates) and trading_dates[pos] == date:
        return int(pos)
    return None


# ---------------------------------------------------------------------------
# Backtest for one sector + one parameter set
# ---------------------------------------------------------------------------
def run_sector(
    sector:           str,
    triggers_all:     pd.DataFrame,
    universe_tickers: list[str],
    closes:           dict[str, pd.Series],
    trading_dates:    pd.DatetimeIndex,
    beat_threshold:   float,
    hold_days:        int,
    skipped_log:      list[str],
) -> tuple[pd.Series, pd.DataFrame, int]:
    """
    Run backtest for one sector with given parameters.

    Returns:
      sector_daily  — pd.Series of daily portfolio returns (0 when no basket active)
      trades_df     — individual trade records for this sector
      overlap_count — number of days with >1 concurrent basket
    """
    mask = (
        (triggers_all["sector"] == sector) &
        (triggers_all["date"] >= BACKTEST_START) &
        (triggers_all["date"] <= BACKTEST_END) &
        (triggers_all["surprise"] >= beat_threshold)
    )
    triggers = triggers_all[mask].copy().reset_index(drop=True)

    available = [t for t in universe_tickers if t in closes]
    if not available or triggers.empty:
        return pd.Series(0.0, index=trading_dates), pd.DataFrame(), 0

    ret_dict = {t: closes[t].reindex(trading_dates).pct_change() for t in available}
    returns_matrix = pd.DataFrame(ret_dict, index=trading_dates)

    portfolio_return_sum = pd.Series(0.0, index=trading_dates)
    basket_count         = pd.Series(0,   index=trading_dates)
    trade_records: list[dict] = []

    for _, trig in triggers.iterrows():
        earnings_date = pd.Timestamp(trig["date"])
        entry_date    = next_trading_day_after(earnings_date, trading_dates)
        if entry_date is None:
            continue

        entry_pos = trading_day_pos(entry_date, trading_dates)
        if entry_pos is None:
            continue

        # Returns accumulate from the day after entry through the hold period
        active_start = entry_pos + 1
        active_end   = min(entry_pos + hold_days, len(trading_dates) - 1)
        if active_start > active_end:
            continue

        active_dates = trading_dates[active_start : active_end + 1]
        basket_rets  = returns_matrix.loc[active_dates].mean(axis=1)

        portfolio_return_sum.loc[active_dates] += basket_rets.values
        basket_count.loc[active_dates]         += 1

        exit_date = trading_dates[active_end]

        for ticker in available:
            entry_price = get_price_on_or_after(closes[ticker], entry_date)
            if entry_price is None:
                skipped_log.append(
                    f"sector={sector} bt={beat_threshold} hd={hold_days} | "
                    f"trigger {earnings_date.date()} | {ticker}: no entry price "
                    f"within {MAX_ENTRY_SLIP} days of {entry_date.date()}"
                )
                continue

            ticker_closes = closes[ticker]
            ticker_idx    = ticker_closes.index
            exit_pos_in_ticker = ticker_idx.searchsorted(exit_date)
            if exit_pos_in_ticker >= len(ticker_idx):
                exit_pos_in_ticker = len(ticker_idx) - 1

            exit_price   = float(ticker_closes.iloc[exit_pos_in_ticker])
            actual_exit  = ticker_closes.index[exit_pos_in_ticker]
            early_exit   = actual_exit < exit_date
            trade_return = (exit_price - entry_price) / entry_price

            entry_tpos     = trading_dates.searchsorted(entry_date)
            actual_exit_tp = trading_dates.searchsorted(actual_exit)
            actual_hold    = max(0, int(actual_exit_tp) - int(entry_tpos))

            trade_records.append({
                "sector":           sector,
                "anchor":           trig["symbol"],
                "earnings_date":    earnings_date,
                "surprise":         trig["surprise"],
                "ticker":           ticker,
                "entry_date":       entry_date,
                "exit_date":        actual_exit,
                "intended_exit":    exit_date,
                "entry_price":      entry_price,
                "exit_price":       exit_price,
                "trade_return":     trade_return,
                "actual_hold_days": actual_hold,
                "early_exit":       early_exit,
            })

    active_mask  = basket_count > 0
    sector_daily = pd.Series(0.0, index=trading_dates)
    sector_daily[active_mask] = (
        portfolio_return_sum[active_mask] / basket_count[active_mask]
    )

    overlap_count = int((basket_count > 1).sum())
    trades_df     = pd.DataFrame(trade_records) if trade_records else pd.DataFrame()

    return sector_daily, trades_df, overlap_count


# ---------------------------------------------------------------------------
# Run all sectors → combined portfolio
# ---------------------------------------------------------------------------
def run_all_sectors(
    triggers_all:     pd.DataFrame,
    sector_universes: dict[str, list[str]],
    closes:           dict[str, pd.Series],
    trading_dates:    pd.DatetimeIndex,
    beat_threshold:   float,
    hold_days:        int,
    skipped_log:      list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run backtest for all sectors and combine.

    Returns:
      portfolio_df — daily returns: combined_return, spy_return,
                     {sector}_return, {etf}_return per sector
      trades_df    — all individual trade records across all sectors
    """
    sector_returns: dict[str, pd.Series] = {}
    all_trades: list[pd.DataFrame] = []

    for sector in SECTORS:
        daily, trades_df, _ = run_sector(
            sector, triggers_all, sector_universes[sector],
            closes, trading_dates, beat_threshold, hold_days, skipped_log,
        )
        sector_returns[sector] = daily
        if not trades_df.empty:
            all_trades.append(trades_df)

    # Combined = equal-weight average of 4 sector sub-portfolios
    combined = pd.DataFrame(sector_returns, index=trading_dates).mean(axis=1)

    spy_rets  = closes["SPY"].reindex(trading_dates).pct_change().fillna(0)

    portfolio_data: dict[str, pd.Series] = {
        "combined_return": combined,
        "spy_return":      spy_rets,
    }
    for sector in SECTORS:
        portfolio_data[f"{sector.lower()}_return"] = sector_returns[sector]
    for sector, etf in SECTOR_ETFS.items():
        portfolio_data[f"{etf.lower()}_return"] = (
            closes[etf].reindex(trading_dates).pct_change().fillna(0)
        )

    portfolio_df = pd.DataFrame(portfolio_data, index=trading_dates)
    trades_df    = (
        pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    )

    return portfolio_df, trades_df


# ---------------------------------------------------------------------------
# Performance metrics
# ---------------------------------------------------------------------------
def sharpe(returns: pd.Series) -> float:
    std = returns.std()
    if std == 0 or np.isnan(std):
        return float("nan")
    return float(returns.mean() / std * np.sqrt(252))


def annualised_return(cum_returns: pd.Series) -> float:
    total   = cum_returns.iloc[-1]
    n_years = len(cum_returns) / 252
    if n_years <= 0 or total <= 0:
        return float("nan")
    return float(total ** (1 / n_years) - 1)


def max_drawdown(cum_returns: pd.Series) -> float:
    rolling_max = cum_returns.cummax()
    drawdown    = (cum_returns - rolling_max) / rolling_max
    return float(drawdown.min())


# ---------------------------------------------------------------------------
# Print summary statistics
# ---------------------------------------------------------------------------
def print_summary(
    triggers_all:     pd.DataFrame,
    sector_universes: dict[str, list[str]],
    portfolio_df:     pd.DataFrame,
    trades_df:        pd.DataFrame,
    beat_threshold:   float,
    hold_days:        int,
) -> None:
    combined_rets = portfolio_df["combined_return"]
    spy_rets      = portfolio_df["spy_return"]

    cum_combined = (1 + combined_rets).cumprod()
    cum_spy      = (1 + spy_rets).cumprod()

    ann_combined    = annualised_return(cum_combined)
    ann_spy         = annualised_return(cum_spy)
    sharpe_combined = sharpe(combined_rets)
    sharpe_spy      = sharpe(spy_rets)
    mdd_combined    = max_drawdown(cum_combined)

    total_triggers = int(
        (
            (triggers_all["surprise"] >= beat_threshold) &
            (triggers_all["date"] >= BACKTEST_START) &
            (triggers_all["date"] <= BACKTEST_END)
        ).sum()
    )

    total_trades = 0
    early_exits  = 0
    trade_wins   = 0
    basket_wins  = 0
    n_baskets    = 0

    if not trades_df.empty:
        total_trades = len(trades_df)
        early_exits  = int(trades_df["early_exit"].sum())
        trade_wins   = int((trades_df["trade_return"] > 0).sum())
        for _, grp in trades_df.groupby(["sector", "anchor", "earnings_date"]):
            n_baskets += 1
            if grp["trade_return"].mean() > 0:
                basket_wins += 1

    print("\n" + "=" * 74)
    print("  LEAD-LAG BACKTEST (PHASE 2: 4 SECTORS) — SUMMARY STATISTICS")
    print("=" * 74)
    print(f"Backtest period:              {BACKTEST_START.date()} to {BACKTEST_END.date()}")
    print(f"Parameters:                   BEAT_THRESHOLD={beat_threshold*100:.0f}%, HOLD_DAYS={hold_days}d")
    print()
    print("--- COMBINED PORTFOLIO ---")
    print(f"Total trigger events fired:   {total_triggers}  (across all sectors)")
    print(f"Total individual trades:      {total_trades}")
    print(f"Trades with early exit:       {early_exits}")
    print(f"Trades skipped (no price):    see data/skipped_trades.txt")
    print()
    print(f"Combined annualised return:   {ann_combined*100:.1f}%")
    print(f"SPY benchmark return:         {ann_spy*100:.1f}%")
    ann_excess = ann_combined - ann_spy
    print(f"Excess return vs SPY:         {ann_excess*100:+.1f}pp")
    print()
    print(f"Combined Sharpe ratio:        {sharpe_combined:.2f}")
    print(f"SPY Sharpe ratio:             {sharpe_spy:.2f}")
    print(f"Combined max drawdown:        {mdd_combined*100:.1f}%")
    print()
    if n_baskets > 0:
        print(f"Win rate (baskets):           {basket_wins/n_baskets*100:.1f}%")
    if total_trades > 0:
        print(f"Win rate (individual trades): {trade_wins/total_trades*100:.1f}%")

    print()
    print("--- PER SECTOR ---")
    col_w = 16
    hdr = (
        f"{'Sector':<{col_w}} | {'Universe':>8} | {'Triggers':>8} | "
        f"{'Ann. Return':>11} | {'Sector ETF':>10} | {'Excess':>8} | {'Sharpe':>6}"
    )
    print(hdr)
    print("-" * len(hdr))

    for sector in SECTORS:
        etf        = SECTOR_ETFS[sector]
        s_rets     = portfolio_df[f"{sector.lower()}_return"]
        e_rets     = portfolio_df[f"{etf.lower()}_return"]
        cum_s      = (1 + s_rets).cumprod()
        cum_e      = (1 + e_rets).cumprod()
        ann_s      = annualised_return(cum_s)
        ann_e      = annualised_return(cum_e)
        sh_s       = sharpe(s_rets)
        excess     = ann_s - ann_e
        n_uni      = len(sector_universes[sector])
        n_trig     = int(
            (
                (triggers_all["sector"] == sector) &
                (triggers_all["surprise"] >= beat_threshold) &
                (triggers_all["date"] >= BACKTEST_START) &
                (triggers_all["date"] <= BACKTEST_END)
            ).sum()
        )
        excess_str = f"{excess*100:+.1f}pp" if not np.isnan(excess) else "  N/A"
        ann_s_str  = f"{ann_s*100:.1f}%" if not np.isnan(ann_s) else "N/A"
        ann_e_str  = f"{ann_e*100:.1f}%" if not np.isnan(ann_e) else "N/A"
        print(
            f"{sector:<{col_w}} | {n_uni:>8} | {n_trig:>8} | "
            f"{ann_s_str:>11} | {ann_e_str:>10} | {excess_str:>8} | {sh_s:>6.2f}"
        )

    print("=" * 74)
    print("""
NOTE: Survivor-only universe. Small-cap stocks delisted, acquired, or bankrupt
during 2021-2026 are excluded. Returns biased upward by unknown magnitude.
Phase 3 will add survivorship bias correction.

NOTE: Fixed universe. IPOs after 2021-05-20 and stocks that moved in/out of the
small-cap range during the backtest window are not captured.

NOTE: No transaction costs modelled. Small-cap bid-ask spreads reduce live returns,
especially in Healthcare/Biotech where spreads are widest.

NOTE: Healthcare/Biotech small-cap universe may be small (< 10 tickers after
liquidity filter). Results for this sector should be treated with caution.
""")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Loading data…")
    triggers_all, sector_universes, closes = load_data()
    trading_dates = get_trading_dates(closes)

    print(f"  Trading dates in backtest window: {len(trading_dates)}")
    print(f"  Trigger-eligible events loaded: {len(triggers_all)}")
    for sector in SECTORS:
        n_events = (triggers_all["sector"] == sector).sum()
        n_tickers = len(sector_universes[sector])
        print(f"    {sector}: {n_events} events, {n_tickers} small-cap universe")

    sweep_results: list[dict] = []
    skipped_log:   list[str]  = []

    n_combos = len(BEAT_THRESHOLDS) * len(HOLD_DAYS_LIST)
    print(f"\nRunning {n_combos} parameter combinations across 4 sectors…")

    for beat_threshold in BEAT_THRESHOLDS:
        for hold_days in HOLD_DAYS_LIST:
            label = f"bt={beat_threshold*100:.0f}%  hd={hold_days:2d}d"
            print(f"  {label}…", end=" ", flush=True)

            portfolio_df, trades_df = run_all_sectors(
                triggers_all, sector_universes, closes, trading_dates,
                beat_threshold, hold_days, skipped_log,
            )

            sh = sharpe(portfolio_df["combined_return"])
            print(f"Sharpe = {sh:.3f}")

            sweep_results.append({
                "beat_threshold": beat_threshold,
                "hold_days":      hold_days,
                "sharpe":         sh,
            })

            bt_tag = f"{beat_threshold*100:.0f}"
            hd_tag = f"{hold_days}"
            portfolio_df.to_parquet(
                RESULTS_DIR / f"portfolio_returns_bt{bt_tag}_hd{hd_tag}.parquet"
            )
            if not trades_df.empty:
                trades_df.to_parquet(
                    RESULTS_DIR / f"trades_bt{bt_tag}_hd{hd_tag}.parquet"
                )

            if beat_threshold == PRIMARY_BEAT_THRESHOLD and hold_days == PRIMARY_HOLD_DAYS:
                print_summary(
                    triggers_all, sector_universes, portfolio_df,
                    trades_df, beat_threshold, hold_days,
                )

    sweep_df = pd.DataFrame(sweep_results)
    sweep_df.to_parquet(RESULTS_DIR / "sweep_sharpes.parquet", index=False)
    print(f"\nSharpe grid saved to {RESULTS_DIR.name}/sweep_sharpes.parquet")

    if skipped_log:
        skipped_path = DATA_DIR / "skipped_trades.txt"
        with open(skipped_path, "w") as f:
            f.write("\n".join(skipped_log))
        print(f"{len(skipped_log)} skipped trades logged to {skipped_path.name}")

    print("\nBacktest complete.")


if __name__ == "__main__":
    main()
