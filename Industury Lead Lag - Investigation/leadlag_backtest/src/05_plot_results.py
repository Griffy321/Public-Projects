"""
Phase 2 — Generate output charts:
  output/leadlag_returns_vs_spy.png   — two-panel chart (cumulative returns + excess return bars)
  output/parameter_sweep_heatmap.png  — Sharpe heatmap with Phase 1 comparison note

Two-panel layout:
  Top:    Combined strategy + SPY (bold) + 4 sector sub-portfolios (thin/muted)
  Bottom: Per-sector excess return bars vs each sector's ETF (annualised, pp)
"""

import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR  = Path(__file__).resolve().parent
ROOT_DIR    = SCRIPT_DIR.parent
DATA_DIR    = ROOT_DIR / "data"
RESULTS_DIR = DATA_DIR / "results"
OUTPUT_DIR  = ROOT_DIR / "output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PRIMARY_BT = "10"
PRIMARY_HD = "20"

BACKTEST_START = pd.Timestamp("2021-05-20")

SECTORS = ["Semiconductors", "Energy", "Financials", "Healthcare"]
SECTOR_ETFS = {
    "Semiconductors": "SOXX",
    "Energy":         "XLE",
    "Financials":     "XLF",
    "Healthcare":     "XLV",
}

# Muted colours for the thin sector sub-portfolio lines
SECTOR_COLORS = {
    "Semiconductors": "#aec7e8",
    "Energy":         "#ffbb78",
    "Financials":     "#98df8a",
    "Healthcare":     "#ff9896",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def annualised_return(cum_returns: pd.Series) -> float:
    total   = cum_returns.iloc[-1]
    n_years = len(cum_returns) / 252
    if n_years <= 0 or total <= 0:
        return float("nan")
    return float(total ** (1 / n_years) - 1)


def load_primary_results() -> pd.DataFrame:
    pf = RESULTS_DIR / f"portfolio_returns_bt{PRIMARY_BT}_hd{PRIMARY_HD}.parquet"
    if not pf.exists():
        sys.exit(f"ERROR: {pf} not found. Run 04_run_backtest.py first.")
    return pd.read_parquet(pf)


def load_sweep_sharpes() -> pd.DataFrame:
    pf = RESULTS_DIR / "sweep_sharpes.parquet"
    if not pf.exists():
        sys.exit("ERROR: sweep_sharpes.parquet not found. Run 04_run_backtest.py first.")
    return pd.read_parquet(pf)


def count_triggers() -> int:
    trig_file = DATA_DIR / "earnings_triggers.parquet"
    if not trig_file.exists():
        return -1
    df = pd.read_parquet(trig_file)
    df["date"] = pd.to_datetime(df["date"])
    mask = (
        (df["surprise"] >= float(PRIMARY_BT) / 100) &
        (df["date"] >= BACKTEST_START)
    )
    return int(mask.sum())


# ---------------------------------------------------------------------------
# Chart 1 — Two-panel chart
# ---------------------------------------------------------------------------
def plot_two_panel(portfolio_df: pd.DataFrame) -> None:
    combined_rets = portfolio_df["combined_return"].fillna(0)
    spy_rets      = portfolio_df["spy_return"].fillna(0)

    cum_combined = (1 + combined_rets).cumprod()
    cum_spy      = (1 + spy_rets).cumprod()

    ann_combined = annualised_return(cum_combined)
    ann_spy      = annualised_return(cum_spy)

    # Compute per-sector and per-ETF annualised returns for bottom panel
    sector_ann: dict[str, float] = {}
    etf_ann:    dict[str, float] = {}
    sector_cum: dict[str, pd.Series] = {}

    for sector in SECTORS:
        col = f"{sector.lower()}_return"
        s_rets = (
            portfolio_df[col].fillna(0)
            if col in portfolio_df.columns
            else pd.Series(0.0, index=portfolio_df.index)
        )
        cum_s = (1 + s_rets).cumprod()
        sector_cum[sector]  = cum_s
        sector_ann[sector]  = annualised_return(cum_s)

        etf  = SECTOR_ETFS[sector]
        ecol = f"{etf.lower()}_return"
        e_rets = (
            portfolio_df[ecol].fillna(0)
            if ecol in portfolio_df.columns
            else pd.Series(0.0, index=portfolio_df.index)
        )
        etf_ann[sector] = annualised_return((1 + e_rets).cumprod())

    # ── Figure layout ────────────────────────────────────────────────────────
    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(12, 9),
        gridspec_kw={"height_ratios": [3, 1.5]},
    )

    # ── Top panel ───────────────────────────────────────────────────────────
    # Sector sub-portfolio lines (thin, muted, drawn first so bold lines sit on top)
    for sector in SECTORS:
        cum_s    = sector_cum[sector]
        ann_s    = sector_ann[sector]
        ann_str  = f"{ann_s*100:+.1f}%" if not np.isnan(ann_s) else "N/A"
        ax_top.plot(
            cum_s.index, cum_s.values,
            color=SECTOR_COLORS[sector], linewidth=0.9, alpha=0.65,
            label=f"{sector} ({ann_str} ann.)",
        )

    # Combined strategy and SPY (bold, drawn on top)
    ann_comb_str = f"{ann_combined*100:+.1f}%" if not np.isnan(ann_combined) else "N/A"
    ann_spy_str  = f"{ann_spy*100:+.1f}%"      if not np.isnan(ann_spy)      else "N/A"

    ax_top.plot(
        cum_combined.index, cum_combined.values,
        color="#1f77b4", linewidth=2.2, zorder=5,
        label=f"Combined Strategy  ({ann_comb_str} ann.)",
    )
    ax_top.plot(
        cum_spy.index, cum_spy.values,
        color="#d62728", linewidth=2.0, linestyle="--", zorder=5,
        label=f"SPY Benchmark  ({ann_spy_str} ann.)",
    )

    ax_top.axhline(1.0, color="gray", linewidth=0.6, linestyle=":")
    ax_top.set_title(
        "Intra-Industry Lead-Lag Strategy — Cumulative Returns vs SPY",
        fontsize=13, fontweight="bold",
    )
    ax_top.set_ylabel("Cumulative Return (indexed to 1.0 at 2021-05-20)", fontsize=10)
    ax_top.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax_top.xaxis.set_major_locator(mdates.YearLocator())
    ax_top.legend(fontsize=9, loc="upper left")
    ax_top.grid(axis="y", alpha=0.3)

    n_triggers = count_triggers()
    subtitle = (
        f"Parameters: BEAT_THRESHOLD={PRIMARY_BT}%, HOLD_DAYS={PRIMARY_HD}d  |  "
        f"Total trigger events: {n_triggers if n_triggers >= 0 else 'N/A'}"
    )
    ax_top.text(
        0.5, -0.025, subtitle,
        transform=ax_top.transAxes, ha="center", fontsize=8.5, color="gray",
    )

    # ── Bottom panel — excess return bars ────────────────────────────────────
    excess_pp = []
    for sector in SECTORS:
        s_ann = sector_ann[sector]
        e_ann = etf_ann[sector]
        if np.isnan(s_ann) or np.isnan(e_ann):
            excess_pp.append(float("nan"))
        else:
            excess_pp.append((s_ann - e_ann) * 100)

    bar_colors = []
    for v in excess_pp:
        if np.isnan(v):
            bar_colors.append("gray")
        elif v >= 0:
            bar_colors.append("#2ca02c")
        else:
            bar_colors.append("#d62728")

    x_pos   = range(len(SECTORS))
    bars    = ax_bot.bar(x_pos, excess_pp, color=bar_colors, width=0.5, zorder=3)

    ax_bot.axhline(0, color="black", linewidth=0.9, zorder=4)
    ax_bot.set_xticks(list(x_pos))
    ax_bot.set_xticklabels(SECTORS, fontsize=10)
    ax_bot.set_ylabel("Excess Return vs Sector ETF\n(annualised, pp)", fontsize=9)
    ax_bot.set_title("Per-Sector Excess Return vs Sector ETF", fontsize=10, fontweight="bold")
    ax_bot.grid(axis="y", alpha=0.3, zorder=0)

    # Annotate each bar with value and ETF name
    y_lim = ax_bot.get_ylim()
    y_range = y_lim[1] - y_lim[0]

    for bar, val, sector in zip(bars, excess_pp, SECTORS):
        etf = SECTOR_ETFS[sector]
        if np.isnan(val):
            label = "N/A"
        else:
            label = f"{val:+.1f}pp"

        bar_h  = bar.get_height()
        bar_x  = bar.get_x() + bar.get_width() / 2
        offset = y_range * 0.04 if bar_h >= 0 else -y_range * 0.08
        ax_bot.text(bar_x, bar_h + offset, label,
                    ha="center", va="bottom", fontsize=9, fontweight="bold")
        ax_bot.text(bar_x, y_lim[0] + y_range * 0.03,
                    f"vs {etf}", ha="center", fontsize=8, color="gray")

    fig.tight_layout()
    out_path = OUTPUT_DIR / "leadlag_returns_vs_spy.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_path}")


# ---------------------------------------------------------------------------
# Chart 2 — Parameter sweep heatmap
# ---------------------------------------------------------------------------
def plot_heatmap(sweep_df: pd.DataFrame) -> None:
    pivot = sweep_df.pivot(index="beat_threshold", columns="hold_days", values="sharpe")
    pivot = pivot.sort_index(ascending=False)
    pivot = pivot[sorted(pivot.columns)]

    y_labels = [f"{int(t*100)}%" for t in pivot.index]
    x_labels = [str(int(c)) for c in pivot.columns]

    fig, ax = plt.subplots(figsize=(8, 4.5))

    sns.heatmap(
        pivot,
        annot=True,
        fmt=".2f",
        cmap="RdYlGn",
        center=0,
        linewidths=0.5,
        linecolor="white",
        mask=pivot.isna(),
        ax=ax,
        cbar_kws={"label": "Annualised Sharpe Ratio"},
        xticklabels=x_labels,
        yticklabels=y_labels,
    )

    ax.set_title(
        "Lead-Lag Strategy (Phase 2: 4 Sectors) — Parameter Sweep: Sharpe Ratio",
        fontsize=11, fontweight="bold", pad=12,
    )
    ax.set_xlabel("Holding Period (trading days)", fontsize=10)
    ax.set_ylabel("EPS Beat Threshold", fontsize=10)
    ax.tick_params(axis="both", which="both", length=0)

    note = (
        "Phase 1 (Semiconductors only): Sharpe 1.23 at 10%/20d. "
        "Phase 2 adds Energy, Financials, Healthcare to the combined portfolio."
    )
    fig.text(0.5, -0.02, note, ha="center", fontsize=8, color="gray")

    out_path = OUTPUT_DIR / "parameter_sweep_heatmap.png"
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Loading results…")
    portfolio_df = load_primary_results()
    sweep_df     = load_sweep_sharpes()

    print(f"  Portfolio data: {len(portfolio_df)} trading days")
    print(f"  Sweep grid: {len(sweep_df)} parameter combinations")

    # Confirm expected columns are present
    expected_cols = (
        ["combined_return", "spy_return"]
        + [f"{s.lower()}_return" for s in SECTORS]
        + [f"{etf.lower()}_return" for etf in SECTOR_ETFS.values()]
    )
    missing_cols = [c for c in expected_cols if c not in portfolio_df.columns]
    if missing_cols:
        print(f"WARNING: Missing columns in portfolio_df: {missing_cols}")
        print("  Charts may be incomplete. Re-run 04_run_backtest.py.")

    print("\nPlotting two-panel cumulative returns chart…")
    plot_two_panel(portfolio_df)

    print("Plotting parameter sweep heatmap…")
    plot_heatmap(sweep_df)

    print("\nDone. Charts saved to output/")


if __name__ == "__main__":
    main()
