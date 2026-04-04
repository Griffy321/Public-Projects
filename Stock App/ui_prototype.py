"""
UI Prototype — Stock Comparison App
Standalone demo with fake data. No API calls, no imports from the rest of the app.
Run with: streamlit run ui_prototype.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ──────────────────────────────────────────────
# Fake Data
# ──────────────────────────────────────────────

STOCKS = {
    "AAPL": {
        "name": "Apple Inc.",
        "price": 182.63,
        "change_pct": 1.24,
        "market_cap": 2840000000000,
        "pe_ratio": 28.4,
        "eps": 6.43,
        "earnings_yield": 3.52,
        "revenue": 394300000000,
        "net_income": 96995000000,
        "free_cash_flow": 111439000000,
        "total_debt": 111100000000,
        "de_ratio": 1.76,
        "commentary": {
            "profitability": ("Profitable", True),
            "cash_flow": ("Positive free cash flow", True),
            "leverage": ("Moderate leverage", True),
            "valuation": ("Fairly valued", True),
        },
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "price": 415.32,
        "change_pct": 0.87,
        "market_cap": 3090000000000,
        "pe_ratio": 34.1,
        "eps": 12.18,
        "earnings_yield": 2.93,
        "revenue": 211900000000,
        "net_income": 72361000000,
        "free_cash_flow": 59475000000,
        "total_debt": 79200000000,
        "de_ratio": 0.83,
        "commentary": {
            "profitability": ("Profitable", True),
            "cash_flow": ("Positive free cash flow", True),
            "leverage": ("Low leverage", True),
            "valuation": ("Slightly expensive", False),
        },
    },
    "TSLA": {
        "name": "Tesla Inc.",
        "price": 175.21,
        "change_pct": -2.41,
        "market_cap": 558000000000,
        "pe_ratio": 72.0,
        "eps": 2.43,
        "earnings_yield": 1.39,
        "revenue": 97690000000,
        "net_income": 7153000000,
        "free_cash_flow": -2864000000,
        "total_debt": 7680000000,
        "de_ratio": 0.21,
        "commentary": {
            "profitability": ("Profitable", True),
            "cash_flow": ("Negative free cash flow", False),
            "leverage": ("Low leverage", True),
            "valuation": ("Expensive valuation", False),
        },
    },
    "NVDA": {
        "name": "NVIDIA Corporation",
        "price": 875.40,
        "change_pct": 3.12,
        "market_cap": 2160000000000,
        "pe_ratio": 66.3,
        "eps": 13.20,
        "earnings_yield": 1.51,
        "revenue": 60922000000,
        "net_income": 29760000000,
        "free_cash_flow": 27021000000,
        "total_debt": 8460000000,
        "de_ratio": 0.44,
        "commentary": {
            "profitability": ("Profitable", True),
            "cash_flow": ("Positive free cash flow", True),
            "leverage": ("Low leverage", True),
            "valuation": ("Expensive valuation", False),
        },
    },
}

# ── Overlayable metrics ────────────────────────────────────────────────────────
# Each entry: label shown to user, data key, unit label for y-axis, volatility
OVERLAY_METRICS = [
    ("P/E Ratio",      "pe_ratio",       "P/E",    0.012),
    ("Earnings Yield", "earnings_yield", "%",      0.010),
    ("EPS",            "eps",            "$",      0.008),
    ("D/E Ratio",      "de_ratio",       "D/E",    0.005),
]
OVERLAY_LABELS = [m[0] for m in OVERLAY_METRICS]

# ── Fake history generators ────────────────────────────────────────────────────

def fake_price_history(ticker, days=180):
    base = STOCKS[ticker]["price"]
    seed = abs(hash(ticker + "price")) % 2**31
    np.random.seed(seed)
    vol = 0.015
    returns = np.random.normal(0, vol, days)
    prices = base * np.exp(np.cumsum(returns) - np.cumsum(returns)[-1])
    dates = pd.date_range(end=pd.Timestamp("2024-04-04"), periods=days, freq="B")
    return pd.Series(prices, index=dates, name=ticker)


def fake_metric_history(ticker, metric_key, vol, days=180):
    """
    Generates a plausible-looking metric history ending at the stock's current value.
    Uses a mean-reverting random walk so the line looks natural.
    """
    current = STOCKS[ticker][metric_key]
    seed = abs(hash(ticker + metric_key)) % 2**31
    np.random.seed(seed)

    values = np.zeros(days)
    values[-1] = current
    for i in range(days - 2, -1, -1):
        shock = np.random.normal(0, vol * abs(current))
        reversion = 0.03 * (current - values[i + 1])
        values[i] = values[i + 1] - shock - reversion

    dates = pd.date_range(end=pd.Timestamp("2024-04-04"), periods=days, freq="B")
    return pd.Series(values, index=dates, name=ticker)


# ── Helpers ────────────────────────────────────────────────────────────────────

# Distinct colours for up to 6 stocks
STOCK_COLOURS = ["#60a5fa", "#34d399", "#f87171", "#fbbf24", "#a78bfa", "#fb7185"]

def stock_colour(ticker, selected_list):
    idx = selected_list.index(ticker) % len(STOCK_COLOURS)
    return STOCK_COLOURS[idx]


def fmt_currency(val):
    if abs(val) >= 1e12:
        return f"${val/1e12:.2f}T"
    if abs(val) >= 1e9:
        return f"${val/1e9:.2f}B"
    if abs(val) >= 1e6:
        return f"${val/1e6:.2f}M"
    return f"${val:,.2f}"


def make_price_chart(tickers, overlay_metric_label=None, normalise=True):
    """
    Build a Plotly figure with price traces on the primary axis and an optional
    metric overlay on a secondary axis.

    normalise=True  → show % change from first data point (compare tab)
    normalise=False → show raw price (per-stock tab)
    """
    has_overlay = overlay_metric_label is not None
    fig = make_subplots(specs=[[{"secondary_y": has_overlay}]])

    overlay_def = None
    if has_overlay:
        overlay_def = next(m for m in OVERLAY_METRICS if m[0] == overlay_metric_label)

    for ticker in tickers:
        colour = stock_colour(ticker, tickers)
        prices = fake_price_history(ticker)

        if normalise:
            y_vals = (prices / prices.iloc[0] - 1) * 100
            hover = "%{y:.2f}%"
        else:
            y_vals = prices
            hover = "$%{y:.2f}"

        fig.add_trace(
            go.Scatter(
                x=prices.index,
                y=y_vals,
                name=ticker,
                line=dict(color=colour, width=2),
                hovertemplate=f"<b>{ticker}</b> price<br>%{{x|%b %d}}: {hover}<extra></extra>",
            ),
            secondary_y=False,
        )

        if has_overlay:
            _, key, unit, vol = overlay_def
            metric_series = fake_metric_history(ticker, key, vol)

            fig.add_trace(
                go.Scatter(
                    x=metric_series.index,
                    y=metric_series,
                    name=f"{ticker} {overlay_metric_label}",
                    line=dict(color=colour, width=1.5, dash="dot"),
                    hovertemplate=(
                        f"<b>{ticker}</b> {overlay_metric_label}<br>"
                        f"%{{x|%b %d}}: %{{y:.2f}} {unit}<extra></extra>"
                    ),
                ),
                secondary_y=True,
            )

    primary_label = "% Change" if normalise else "Price ($)"
    fig.update_yaxes(title_text=primary_label, secondary_y=False,
                     gridcolor="#2a2a2a", color="#aaa")
    if has_overlay:
        _, _, unit, _ = overlay_def
        fig.update_yaxes(title_text=f"{overlay_metric_label} ({unit})",
                         secondary_y=True, gridcolor="#2a2a2a", color="#aaa",
                         showgrid=False)

    fig.update_xaxes(gridcolor="#2a2a2a", color="#aaa")
    fig.update_layout(
        plot_bgcolor="#0f0f0f",
        paper_bgcolor="#0f0f0f",
        font_color="#ccc",
        legend=dict(bgcolor="#1a1a1a", bordercolor="#333", borderwidth=1),
        margin=dict(l=0, r=0, t=10, b=0),
        hovermode="x unified",
    )
    return fig


# ──────────────────────────────────────────────
# Metric definitions for the comparison table
# ──────────────────────────────────────────────

METRIC_DEFS = [
    ("Price",      "Current Price",   "price",          lambda v: f"${v:,.2f}",   None),
    ("Price",      "Day Change",      "change_pct",     lambda v: f"{v:+.2f}%",   None),
    ("Price",      "Market Cap",      "market_cap",     fmt_currency,              None),
    ("Valuation",  "P/E Ratio",       "pe_ratio",       lambda v: f"{v:.1f}x",    True),
    ("Valuation",  "Earnings Yield",  "earnings_yield", lambda v: f"{v:.2f}%",    False),
    ("Valuation",  "EPS",             "eps",            lambda v: f"${v:.2f}",    False),
    ("Financials", "Revenue",         "revenue",        fmt_currency,              False),
    ("Financials", "Net Income",      "net_income",     fmt_currency,              False),
    ("Financials", "Free Cash Flow",  "free_cash_flow", fmt_currency,              False),
    ("Debt",       "Total Debt",      "total_debt",     fmt_currency,              True),
    ("Debt",       "D/E Ratio",       "de_ratio",       lambda v: f"{v:.2f}",     True),
]

def build_comparison_table(selected_tickers):
    index_tuples = [(group, label) for group, label, *_ in METRIC_DEFS]
    multi_index = pd.MultiIndex.from_tuples(index_tuples, names=["Group", "Metric"])
    display_cols, numeric_cols = {}, {}
    for ticker in selected_tickers:
        stock = STOCKS[ticker]
        display_cols[ticker] = [fmt_fn(stock[key]) for _, _, key, fmt_fn, _ in METRIC_DEFS]
        numeric_cols[ticker] = [stock[key] for _, _, key, *_ in METRIC_DEFS]
    return (
        pd.DataFrame(display_cols, index=multi_index),
        pd.DataFrame(numeric_cols, index=multi_index),
    )

def colour_row(row, numeric_df, defs_map):
    key = row.name
    lower_is_better = defs_map.get(key)
    if lower_is_better is None or len(row) < 2:
        return [""] * len(row)
    nums = numeric_df.loc[key]
    if nums.nunique() == 1:
        return [""] * len(row)
    best  = nums.idxmin() if lower_is_better else nums.idxmax()
    worst = nums.idxmax() if lower_is_better else nums.idxmin()
    return [
        "background-color: #1a4a2e; color: #4ade80" if col == best
        else "background-color: #4a1a1a; color: #f87171" if col == worst
        else ""
        for col in row.index
    ]


# ──────────────────────────────────────────────
# Page Config
# ──────────────────────────────────────────────

st.set_page_config(page_title="Stock Analyser", layout="wide",
                   initial_sidebar_state="collapsed")
st.title("Stock Analyser")

selected = st.multiselect(
    "Select stocks to analyse",
    options=list(STOCKS.keys()),
    default=["AAPL", "MSFT", "TSLA"],
    format_func=lambda t: f"{t} — {STOCKS[t]['name']}",
)

if not selected:
    st.info("Select at least one stock above to get started.")
    st.stop()

st.divider()

tab_labels = ["Compare"] + selected
tabs = st.tabs(tab_labels)


# ── Compare Tab ──────────────────────────────

with tabs[0]:
    st.subheader("Side-by-side Comparison")
    st.caption("Green = best value for that metric   |   Red = worst")

    display_df, numeric_df = build_comparison_table(selected)
    defs_map = {(g, l): lib for g, l, _, _, lib in METRIC_DEFS}
    styled = display_df.style.apply(
        colour_row, axis=1, numeric_df=numeric_df, defs_map=defs_map
    )
    st.dataframe(styled, use_container_width=True)

    st.divider()

    # Chart controls
    col_title, col_toggle = st.columns([2, 3])
    with col_title:
        st.subheader("Price History (180 days, normalised)")
    with col_toggle:
        st.write("")  # vertical align
        overlay = st.selectbox(
            "Overlay metric on chart",
            options=["None"] + OVERLAY_LABELS,
            index=0,
            key="compare_overlay",
            help="Adds the selected metric as a dotted line on a second Y-axis.",
        )

    overlay_arg = None if overlay == "None" else overlay
    fig = make_price_chart(selected, overlay_metric_label=overlay_arg, normalise=True)
    st.plotly_chart(fig, use_container_width=True)

    if overlay_arg:
        st.caption(
            f"Solid lines = normalised price (left axis) · "
            f"Dotted lines = {overlay_arg} (right axis) · "
            f"Same colour = same stock"
        )


# ── Per-Stock Tabs ────────────────────────────

for i, ticker in enumerate(selected):
    stock = STOCKS[ticker]

    with tabs[i + 1]:
        col_name, col_price, col_cap = st.columns([3, 1, 1])
        with col_name:
            st.subheader(f"{stock['name']} ({ticker})")
        with col_price:
            st.metric("Price", f"${stock['price']:.2f}",
                      delta=f"{stock['change_pct']:+.2f}%")
        with col_cap:
            st.metric("Market Cap", fmt_currency(stock["market_cap"]))

        st.divider()

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Valuation**")
            st.metric("P/E Ratio", f"{stock['pe_ratio']:.1f}x")
            st.metric("EPS", f"${stock['eps']:.2f}")
            st.metric("Earnings Yield", f"{stock['earnings_yield']:.2f}%")
        with col2:
            st.markdown("**Financials**")
            st.metric("Revenue", fmt_currency(stock["revenue"]))
            st.metric("Net Income", fmt_currency(stock["net_income"]))
            st.metric("Free Cash Flow", fmt_currency(stock["free_cash_flow"]))
        with col3:
            st.markdown("**Debt**")
            st.metric("Total Debt", fmt_currency(stock["total_debt"]))
            st.metric("D/E Ratio", f"{stock['de_ratio']:.2f}")

        st.divider()

        st.markdown("**Summary**")
        for _, (text, positive) in stock["commentary"].items():
            st.markdown(f"{'✅' if positive else '❌'} {text}")

        st.write("")

        # Per-stock chart with multi-metric overlay
        col_chart_title, col_overlay = st.columns([2, 3])
        with col_chart_title:
            st.markdown("**Price History (180 days)**")
        with col_overlay:
            overlays = st.multiselect(
                "Overlay metrics",
                options=OVERLAY_LABELS,
                default=[],
                key=f"overlay_{ticker}",
                help="Each metric appears as a dotted line on a second Y-axis.",
            )

        # For per-stock we show one metric overlay at a time on secondary axis.
        # If user picks multiple, plot them all on the right axis.
        if len(overlays) == 0:
            fig = make_price_chart([ticker], overlay_metric_label=None, normalise=False)
        else:
            # Build chart manually to support multiple overlays on right axis
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            colour = stock_colour(ticker, [ticker])
            prices = fake_price_history(ticker)

            fig.add_trace(
                go.Scatter(
                    x=prices.index, y=prices,
                    name=f"{ticker} Price",
                    line=dict(color=colour, width=2),
                    hovertemplate="<b>Price</b>: $%{y:.2f}<extra></extra>",
                ),
                secondary_y=False,
            )

            overlay_colours = ["#f472b6", "#fb923c", "#a3e635", "#22d3ee"]
            for j, ov_label in enumerate(overlays):
                _, key, unit, vol = next(m for m in OVERLAY_METRICS if m[0] == ov_label)
                series = fake_metric_history(ticker, key, vol)
                ov_colour = overlay_colours[j % len(overlay_colours)]
                fig.add_trace(
                    go.Scatter(
                        x=series.index, y=series,
                        name=ov_label,
                        line=dict(color=ov_colour, width=1.5, dash="dot"),
                        hovertemplate=f"<b>{ov_label}</b>: %{{y:.2f}} {unit}<extra></extra>",
                    ),
                    secondary_y=True,
                )

            fig.update_yaxes(title_text="Price ($)", secondary_y=False,
                             gridcolor="#2a2a2a", color="#aaa")
            fig.update_yaxes(title_text="Metric value", secondary_y=True,
                             gridcolor="#2a2a2a", color="#aaa", showgrid=False)
            fig.update_xaxes(gridcolor="#2a2a2a", color="#aaa")
            fig.update_layout(
                plot_bgcolor="#0f0f0f", paper_bgcolor="#0f0f0f",
                font_color="#ccc",
                legend=dict(bgcolor="#1a1a1a", bordercolor="#333", borderwidth=1),
                margin=dict(l=0, r=0, t=10, b=0),
                hovermode="x unified",
            )

        st.plotly_chart(fig, use_container_width=True)
