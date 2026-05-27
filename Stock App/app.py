import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import asyncio
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pathlib import Path

from metrics import Metrics
from data_functions import data_fetcher

# ─── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Stock Analyser", layout="wide", initial_sidebar_state="collapsed")

DATA_ROOT = Path(__file__).parent / "data"

# ─── Helpers ───────────────────────────────────────────────────────────────────
STOCK_COLOURS = ["#60a5fa", "#34d399", "#f87171", "#fbbf24", "#a78bfa", "#fb7185"]

def stock_colour(ticker, selected_list):
    return STOCK_COLOURS[selected_list.index(ticker) % len(STOCK_COLOURS)]

def fmt_currency(val):
    if pd.isna(val):
        return "N/A"
    if abs(val) >= 1e12:
        return f"${val/1e12:.2f}T"
    if abs(val) >= 1e9:
        return f"${val/1e9:.2f}B"
    if abs(val) >= 1e6:
        return f"${val/1e6:.2f}M"
    return f"${val:,.2f}"

def has_local_data(ticker):
    required = ["price_data", "cash_flow_data", "balance_sheet_data", "mkt_cap_data"]
    return all((DATA_ROOT / folder / f"{ticker}.parquet").exists() for folder in required)

@st.cache_data(show_spinner=False)
def load_profile(ticker, _v=0):
    path = DATA_ROOT / "profile_data" / f"{ticker}.parquet"
    if not path.exists():
        return {}
    df = pd.read_parquet(path)
    return df.iloc[0].to_dict() if not df.empty else {}

@st.cache_data(show_spinner=False)
def load_metrics_df(ticker, _v=0):
    return Metrics(ticker).calculate_all()

def latest_values(df):
    """Return a dict of the last non-null value for every column."""
    if df is None or df.empty:
        return {}
    return {col: df[col].dropna().iloc[-1] if not df[col].dropna().empty else float("nan")
            for col in df.columns}

def price_series(df, start=None, end=None):
    """Resample 30-min OHLCV to daily close, optionally filtered by date range."""
    if df is None or df.empty or "close" not in df.columns:
        return pd.Series(dtype=float)
    s = df[["date", "close"]].copy()
    s["date"] = pd.to_datetime(s["date"]).dt.tz_localize(None)
    s = s.set_index("date")["close"].resample("D").last().dropna()
    if start:
        s = s[s.index >= pd.to_datetime(start)]
    if end:
        s = s[s.index <= pd.to_datetime(end)]
    return s

def metric_series(df, key, start=None, end=None, as_pct=False):
    """Resample a computed metric column to daily, optionally filtered."""
    if df is None or key not in df.columns:
        return pd.Series(dtype=float)
    s = df[["date", key]].copy()
    s["date"] = pd.to_datetime(s["date"]).dt.tz_localize(None)
    s = s.set_index("date")[key].resample("D").last().dropna()
    if start:
        s = s[s.index >= pd.to_datetime(start)]
    if end:
        s = s[s.index <= pd.to_datetime(end)]
    if as_pct:
        s = s * 100
    return s

# ─── Metric table definitions ──────────────────────────────────────────────────
# (group, label, df_column, format_fn, lower_is_better)
METRIC_DEFS = [
    ("Price",      "Current Price",    "close",               lambda v: f"${v:,.2f}" if not pd.isna(v) else "N/A",          None),
    ("Price",      "Market Cap",       "marketCap",           fmt_currency,                                                   None),
    ("Valuation",  "P/E Ratio",        "peRatio",             lambda v: f"{v:.1f}x" if not pd.isna(v) else "N/A",           True),
    ("Valuation",  "P/B Ratio",        "priceToBook",         lambda v: f"{v:.2f}x" if not pd.isna(v) else "N/A",           True),
    ("Valuation",  "FCF Yield",        "fcfYield",            lambda v: f"{v*100:.2f}%" if not pd.isna(v) else "N/A",       False),
    ("Financials", "Net Income",       "netIncome",           fmt_currency,                                                   False),
    ("Financials", "Free Cash Flow",   "freeCashFlow",        fmt_currency,                                                   False),
    ("Financials", "Earnings Quality", "earningsQuality",     lambda v: f"{v:.2f}" if not pd.isna(v) else "N/A",            False),
    ("Balance",    "Current Ratio",    "currentRatio",        lambda v: f"{v:.2f}" if not pd.isna(v) else "N/A",            False),
    ("Balance",    "D/E Ratio",        "debtToEquity",        lambda v: f"{v:.2f}" if not pd.isna(v) else "N/A",            True),
    ("Balance",    "Net Cash % Cap",   "netCashPctMarketCap", lambda v: f"{v*100:.2f}%" if not pd.isna(v) else "N/A",       False),
    ("Returns",    "ROE",              "returnOnEquity",      lambda v: f"{v*100:.2f}%" if not pd.isna(v) else "N/A",       False),
    ("Returns",    "ROA",              "returnOnAssets",      lambda v: f"{v*100:.2f}%" if not pd.isna(v) else "N/A",       False),
]

# (label, df_column, y-axis unit, multiply by 100 before plotting)
OVERLAY_DEFS = [
    ("P/E Ratio",     "peRatio",             "P/E",  False),
    ("P/B Ratio",     "priceToBook",         "P/B",  False),
    ("FCF Yield %",   "fcfYield",            "%",    True),
    ("D/E Ratio",     "debtToEquity",        "D/E",  False),
    ("Current Ratio", "currentRatio",        "x",    False),
    ("ROE %",         "returnOnEquity",      "%",    True),
    ("ROA %",         "returnOnAssets",      "%",    True),
]
OVERLAY_LABELS = [o[0] for o in OVERLAY_DEFS]

# ─── Comparison table ──────────────────────────────────────────────────────────
def build_comparison_table(tickers, snap_dict):
    idx = pd.MultiIndex.from_tuples([(g, l) for g, l, *_ in METRIC_DEFS], names=["Group", "Metric"])
    display, numeric = {}, {}
    for t in tickers:
        snap = snap_dict.get(t, {})
        disp_vals, num_vals = [], []
        for _, _, key, fmt_fn, _ in METRIC_DEFS:
            val = snap.get(key, float("nan"))
            try:
                disp_vals.append(fmt_fn(val))
            except Exception:
                disp_vals.append("N/A")
            try:
                num_vals.append(float(val))
            except Exception:
                num_vals.append(float("nan"))
        display[t] = disp_vals
        numeric[t] = num_vals
    return pd.DataFrame(display, index=idx), pd.DataFrame(numeric, index=idx)

def _colour_row(row, numeric_df, defs_map):
    lower_is_better = defs_map.get(row.name)
    if lower_is_better is None or len(row) < 2:
        return [""] * len(row)
    nums = numeric_df.loc[row.name].dropna()
    if nums.nunique() <= 1:
        return [""] * len(row)
    best  = nums.idxmin() if lower_is_better else nums.idxmax()
    worst = nums.idxmax() if lower_is_better else nums.idxmin()
    return [
        "background-color: #1a4a2e; color: #4ade80" if c == best
        else "background-color: #4a1a1a; color: #f87171" if c == worst
        else ""
        for c in row.index
    ]

# ─── Chart builders ────────────────────────────────────────────────────────────
def _chart_style(fig):
    fig.update_yaxes(gridcolor="#2a2a2a", color="#aaa")
    fig.update_xaxes(gridcolor="#2a2a2a", color="#aaa")
    fig.update_layout(
        plot_bgcolor="#0f0f0f", paper_bgcolor="#0f0f0f", font_color="#ccc",
        legend=dict(bgcolor="#1a1a1a", bordercolor="#333", borderwidth=1),
        margin=dict(l=0, r=0, t=10, b=0),
        hovermode="x unified",
    )

def compare_chart(tickers, df_dict, overlay_label, start, end):
    overlay_def = next((o for o in OVERLAY_DEFS if o[0] == overlay_label), None)
    has_overlay = overlay_def is not None
    fig = make_subplots(specs=[[{"secondary_y": has_overlay}]])

    for ticker in tickers:
        colour = stock_colour(ticker, tickers)
        prices = price_series(df_dict.get(ticker), start, end)
        if prices.empty:
            continue
        pct = (prices / prices.iloc[0] - 1) * 100
        fig.add_trace(go.Scatter(
            x=prices.index, y=pct, name=ticker,
            line=dict(color=colour, width=2),
            hovertemplate=f"<b>{ticker}</b><br>%{{x|%b %d}}: %{{y:.2f}}%<extra></extra>",
        ), secondary_y=False)

        if has_overlay:
            _, key, unit, as_pct = overlay_def
            ms = metric_series(df_dict.get(ticker), key, start, end, as_pct=as_pct)
            if not ms.empty:
                fig.add_trace(go.Scatter(
                    x=ms.index, y=ms, name=f"{ticker} {overlay_label}",
                    line=dict(color=colour, width=1.5, dash="dot"),
                    hovertemplate=f"<b>{ticker}</b> {overlay_label}<br>%{{x|%b %d}}: %{{y:.2f}} {unit}<extra></extra>",
                ), secondary_y=True)

    fig.update_yaxes(title_text="% Change", secondary_y=False, gridcolor="#2a2a2a", color="#aaa")
    if has_overlay:
        _, _, unit, _ = overlay_def
        fig.update_yaxes(title_text=f"{overlay_label} ({unit})", secondary_y=True,
                        gridcolor="#2a2a2a", color="#aaa", showgrid=False)
    fig.update_xaxes(gridcolor="#2a2a2a", color="#aaa")
    _chart_style(fig)
    return fig

def single_chart(ticker, df, overlays, start, end):
    overlay_colours = ["#f472b6", "#fb923c", "#a3e635", "#22d3ee"]
    has_overlay = len(overlays) > 0
    fig = make_subplots(specs=[[{"secondary_y": has_overlay}]])
    colour = stock_colour(ticker, [ticker])

    prices = price_series(df, start, end)
    if not prices.empty:
        fig.add_trace(go.Scatter(
            x=prices.index, y=prices, name=f"{ticker} Price",
            line=dict(color=colour, width=2),
            hovertemplate="<b>Price</b>: $%{y:.2f}<extra></extra>",
        ), secondary_y=False)

    fig.update_yaxes(title_text="Price ($)", secondary_y=False, gridcolor="#2a2a2a", color="#aaa")

    for j, label in enumerate(overlays):
        ov_def = next((o for o in OVERLAY_DEFS if o[0] == label), None)
        if ov_def is None:
            continue
        _, key, unit, as_pct = ov_def
        ms = metric_series(df, key, start, end, as_pct=as_pct)
        if ms.empty:
            continue
        ov_colour = overlay_colours[j % len(overlay_colours)]
        fig.add_trace(go.Scatter(
            x=ms.index, y=ms, name=label,
            line=dict(color=ov_colour, width=1.5, dash="dot"),
            hovertemplate=f"<b>{label}</b>: %{{y:.2f}} {unit}<extra></extra>",
        ), secondary_y=True)

    if has_overlay:
        fig.update_yaxes(title_text="Metric value", secondary_y=True,
                        gridcolor="#2a2a2a", color="#aaa", showgrid=False)
    fig.update_xaxes(gridcolor="#2a2a2a", color="#aaa")
    _chart_style(fig)
    return fig

# ─── Commentary ────────────────────────────────────────────────────────────────
def commentary(snap):
    items = []
    ni  = snap.get("netIncome", float("nan"))
    fcf = snap.get("freeCashFlow", float("nan"))
    de  = snap.get("debtToEquity", float("nan"))
    fy  = snap.get("fcfYield", float("nan"))
    eq  = snap.get("earningsQuality", float("nan"))
    cr  = snap.get("currentRatio", float("nan"))

    if not pd.isna(ni):
        items.append(("Profitable" if ni > 0 else "Unprofitable", ni > 0))
    if not pd.isna(fcf):
        items.append(("Positive free cash flow" if fcf > 0 else "Negative free cash flow", fcf > 0))
    if not pd.isna(de):
        if de < 0.5:
            items.append(("Low leverage (D/E < 0.5)", True))
        elif de < 1.5:
            items.append(("Moderate leverage (D/E 0.5–1.5)", True))
        else:
            items.append(("High leverage (D/E > 1.5)", False))
    if not pd.isna(cr):
        items.append(("Healthy liquidity (current ratio > 1)" if cr > 1 else "Liquidity concern (current ratio < 1)", cr > 1))
    if not pd.isna(fy):
        if fy * 100 > 5:
            items.append(("Attractive FCF yield (>5%)", True))
        elif fy * 100 > 2:
            items.append(("Fair FCF yield (2–5%)", True))
        else:
            items.append(("Low FCF yield (<2%)", False))
    if not pd.isna(eq):
        items.append(("Good earnings quality (OCF/NI > 1)" if eq > 1 else "Weak earnings quality (OCF/NI < 1)", eq > 1))
    return items

# ─── Session state ─────────────────────────────────────────────────────────────
if "tickers" not in st.session_state:
    st.session_state.tickers = []
if "cache_v" not in st.session_state:
    st.session_state.cache_v = 0
if "pie_edit" not in st.session_state:
    st.session_state.pie_edit = {}
if "pie_edit_id" not in st.session_state:
    st.session_state.pie_edit_id = None
if "pie_search_results" not in st.session_state:
    st.session_state.pie_search_results = []
if "pie_loaded_candidates" not in st.session_state:
    st.session_state.pie_loaded_candidates = []

# ─── Header ────────────────────────────────────────────────────────────────────
st.title("Stock Analyser")

col_ticker, col_from, col_to, col_add, col_clear = st.columns([2, 1.4, 1.4, 1, 1])
with col_ticker:
    new_ticker = st.text_input("Add stock", placeholder="Ticker e.g. AAPL",
                            label_visibility="collapsed").upper().strip()
with col_from:
    start_date = st.date_input("From", value=(datetime.today() - relativedelta(months=6)).date(),
                            format="YYYY-MM-DD", label_visibility="collapsed")
with col_to:
    end_date = st.date_input("To", value=datetime.today().date(),
                            format="YYYY-MM-DD", label_visibility="collapsed")
with col_add:
    add_clicked = st.button("Add Stock", use_container_width=True, type="primary")
with col_clear:
    if st.button("Clear All", use_container_width=True):
        st.session_state.tickers = []
        st.rerun()

if add_clicked and new_ticker:
    if new_ticker in st.session_state.tickers:
        st.info(f"{new_ticker} is already loaded.")
    else:
        with st.spinner(f"Fetching data for {new_ticker}…"):
            try:
                if not has_local_data(new_ticker):
                    df_dict_raw = asyncio.run(data_fetcher.get_company_data(
                        new_ticker, start_date=str(start_date), end_date=str(end_date)
                    ))
                    data_fetcher.update_save_files(new_ticker, df_dict=df_dict_raw)
                st.session_state.tickers.append(new_ticker)
                st.session_state.cache_v += 1
                st.rerun()
            except Exception as exc:
                st.error(f"Could not load {new_ticker}: {exc}")

selected = st.session_state.tickers

if not selected:
    st.info("Add a stock ticker above to get started.")
    st.stop()

# ─── Load all data ─────────────────────────────────────────────────────────────
v = st.session_state.cache_v
df_map, snap_map, profile_map = {}, {}, {}

for ticker in selected:
    try:
        df = load_metrics_df(ticker, _v=v)
        df_map[ticker]      = df
        snap_map[ticker]    = latest_values(df)
        profile_map[ticker] = load_profile(ticker, _v=v)
    except Exception as exc:
        st.warning(f"Could not compute metrics for {ticker}: {exc}")

live = list(df_map.keys())
if not live:
    st.error("No metric data available for any loaded stock.")
    st.stop()

# ─── Tabs ──────────────────────────────────────────────────────────────────────
st.divider()
tabs = st.tabs(["Compare"] + live + ["T212 Pies"])

# ── Compare ──────────────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("Side-by-side Comparison")
    st.caption("Green = best value for that metric   |   Red = worst   |   Requires ≥ 2 stocks")

    rm_cols = st.columns(len(live))
    for ci, t in enumerate(live):
        with rm_cols[ci]:
            if st.button(f"✕ {t}", key=f"rm_compare_{t}", use_container_width=True):
                st.session_state.tickers.remove(t)
                st.rerun()

    display_df, numeric_df = build_comparison_table(live, snap_map)
    defs_map = {(g, l): lib for g, l, _, _, lib in METRIC_DEFS}

    if len(live) >= 2:
        styled = display_df.style.apply(
            _colour_row, axis=1, numeric_df=numeric_df, defs_map=defs_map
        )
        st.dataframe(styled, use_container_width=True)
    else:
        st.dataframe(display_df, use_container_width=True)

    st.divider()

    col_l, col_r = st.columns([2, 3])
    with col_l:
        st.subheader("Price History (normalised)")
    with col_r:
        st.write("")
        overlay_sel = st.selectbox("Overlay metric on chart",
                                    options=["None"] + OVERLAY_LABELS,
                                    index=0, key="compare_overlay")

    overlay_arg = None if overlay_sel == "None" else overlay_sel
    st.plotly_chart(compare_chart(live, df_map, overlay_arg, start_date, end_date),
                    use_container_width=True)

    if overlay_arg:
        st.caption(
            f"Solid lines = normalised price (left axis)  ·  "
            f"Dotted lines = {overlay_arg} (right axis)  ·  Same colour = same stock"
        )

# ── Per-stock tabs ────────────────────────────────────────────────────────────
for i, ticker in enumerate(live):
    snap    = snap_map[ticker]
    profile = profile_map[ticker]
    df      = df_map[ticker]

    company_name = profile.get("companyName", ticker)
    sector       = profile.get("sector", "")
    description  = profile.get("description", "")

    price_val = snap.get("close", float("nan"))
    mkt_cap   = snap.get("marketCap", float("nan"))

    ps = price_series(df)
    day_chg = ((ps.iloc[-1] / ps.iloc[-2] - 1) * 100) if len(ps) >= 2 else float("nan")

    with tabs[i + 1]:
        col_name, col_price, col_cap, col_rm = st.columns([3, 1, 1, 0.6])
        with col_name:
            st.subheader(f"{company_name} ({ticker})")
            if sector:
                st.caption(sector)
        with col_price:
            st.metric("Price",
                        f"${price_val:,.2f}" if not pd.isna(price_val) else "N/A",
                        delta=f"{day_chg:+.2f}%" if not pd.isna(day_chg) else None)
        with col_cap:
            st.metric("Market Cap", fmt_currency(mkt_cap))
        with col_rm:
            st.write("")
            if st.button("Remove", key=f"rm_{ticker}", use_container_width=True):
                st.session_state.tickers.remove(ticker)
                st.rerun()

        st.divider()

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Valuation**")
            pe  = snap.get("peRatio",     float("nan"))
            pb  = snap.get("priceToBook", float("nan"))
            fy  = snap.get("fcfYield",    float("nan"))
            st.metric("P/E Ratio",  f"{pe:.1f}x"     if not pd.isna(pe)  else "N/A")
            st.metric("P/B Ratio",  f"{pb:.2f}x"     if not pd.isna(pb)  else "N/A")
            st.metric("FCF Yield",  f"{fy*100:.2f}%" if not pd.isna(fy)  else "N/A")
        with c2:
            st.markdown("**Financials**")
            ni  = snap.get("netIncome",      float("nan"))
            fcf = snap.get("freeCashFlow",   float("nan"))
            eq  = snap.get("earningsQuality",float("nan"))
            st.metric("Net Income",       fmt_currency(ni))
            st.metric("Free Cash Flow",   fmt_currency(fcf))
            st.metric("Earnings Quality", f"{eq:.2f}" if not pd.isna(eq) else "N/A")
        with c3:
            st.markdown("**Balance Sheet & Returns**")
            cr  = snap.get("currentRatio",      float("nan"))
            de  = snap.get("debtToEquity",      float("nan"))
            nc  = snap.get("netCashPctMarketCap",float("nan"))
            roe = snap.get("returnOnEquity",    float("nan"))
            roa = snap.get("returnOnAssets",    float("nan"))
            st.metric("Current Ratio",  f"{cr:.2f}"      if not pd.isna(cr)  else "N/A")
            st.metric("D/E Ratio",      f"{de:.2f}"      if not pd.isna(de)  else "N/A")
            st.metric("Net Cash % Cap", f"{nc*100:.2f}%" if not pd.isna(nc)  else "N/A")
            st.metric("ROE",            f"{roe*100:.2f}%" if not pd.isna(roe) else "N/A")
            st.metric("ROA",            f"{roa*100:.2f}%" if not pd.isna(roa) else "N/A")

        st.divider()

        col_l2, col_r2 = st.columns([2, 3])
        with col_l2:
            st.markdown("**Summary**")
            items = commentary(snap)
            if items:
                for text, good in items:
                    st.markdown(f"{'✅' if good else '❌'} {text}")
            else:
                st.caption("No commentary available — data may be incomplete.")
        with col_r2:
            if description:
                with st.expander("Company Description"):
                    st.write(description)

        st.write("")

        col_ct, col_ov = st.columns([2, 3])
        with col_ct:
            st.markdown("**Price History**")
        with col_ov:
            overlays = st.multiselect("Overlay metrics", options=OVERLAY_LABELS,
                                        default=[], key=f"ov_{ticker}")

        st.plotly_chart(single_chart(ticker, df, overlays, start_date, end_date),
                        use_container_width=True)

# ── T212 Pies ─────────────────────────────────────────────────────────────────
with tabs[-1]:
    st.subheader("Trading 212 Pies")

    # ── Pie selector ──────────────────────────────────────────────────────────
    if "pie_map_cache" not in st.session_state:
        try:
            from data_functions.ticker_db import TickerDB as _TickerDB
            st.session_state.pie_map_cache = {p["name"]: p["id"] for p in _TickerDB().get_pie_list()}
        except Exception:
            st.session_state.pie_map_cache = {}
    pie_map = st.session_state.pie_map_cache

    sel_col, reload_col = st.columns([3, 1], vertical_alignment="bottom")
    with sel_col:
        if pie_map:
            selected_pie_name = st.selectbox("Pie", options=list(pie_map),
                                             label_visibility="collapsed")
            selected_pie_id = pie_map[selected_pie_name]
        else:
            st.selectbox("Pie", options=["— no pies found —"],
                         disabled=True, label_visibility="collapsed")
            selected_pie_id = None
    with reload_col:
        if st.button("Reload from T212", key="pie_reload", use_container_width=True):
            st.session_state.pie_edit_id = None

    # ── Auto-load holdings into editable state when pie changes ───────────────
    if selected_pie_id and selected_pie_id != st.session_state.pie_edit_id:
        try:
            from data_functions.ticker_db import TickerDB as _TickerDB
            pie_data = _TickerDB().get_one_pie(selected_pie_id)
            instruments = pie_data.get("instruments", [])
            for k in [k for k in st.session_state if k.startswith("pie_w_")]:
                del st.session_state[k]
            st.session_state.pie_edit = {
                item["ticker"]: round(item["expectedShare"] * 100, 2)
                for item in sorted(instruments, key=lambda x: x["expectedShare"], reverse=True)
            }
            st.session_state.pie_edit_id = selected_pie_id
        except Exception as exc:
            st.error(f"Could not load holdings: {exc}")

    st.divider()

    # ── Add stocks ────────────────────────────────────────────────────────────
    col_qs, col_srch = st.columns(2)

    with col_qs:
        st.markdown("**From loaded stocks**")
        qs_col, qadd_col = st.columns([3, 1], vertical_alignment="bottom")
        with qs_col:
            loaded_pick = st.selectbox(
                "stock", options=[""] + list(live),
                key="pie_loaded_sel", label_visibility="collapsed"
            )
        with qadd_col:
            loaded_add = st.button("+ Add", key="pie_loaded_add",
                                   type="primary", use_container_width=True)

    with col_srch:
        st.markdown("**Search ticker**")
        s_col, b_col = st.columns([3, 1], vertical_alignment="bottom")
        with s_col:
            search_q = st.text_input(
                "search", placeholder="e.g. NVDA",
                key="pie_search_input", label_visibility="collapsed"
            ).upper().strip()
        with b_col:
            search_hit = st.button("Search", key="pie_srch_btn", use_container_width=True)

    # Resolve loaded stock to T212 ticker via DB lookup
    if loaded_add and loaded_pick:
        try:
            from data_functions.ticker_db import TickerDB as _TickerDB
            candidates = _TickerDB().get_candidates(loaded_pick)
            if len(candidates) == 1:
                t212_ticker = candidates[0]["ticker"]
                if t212_ticker not in st.session_state.pie_edit:
                    st.session_state.pie_edit[t212_ticker] = 0.0
                st.session_state.pie_loaded_candidates = []
                st.rerun()
            elif len(candidates) > 1:
                st.session_state.pie_loaded_candidates = candidates
            else:
                st.warning(f"{loaded_pick} not found in the ticker database.")
        except Exception as exc:
            st.error(f"Lookup failed: {exc}")

    # Disambiguation picker when a loaded stock matches multiple exchange listings
    if st.session_state.pie_loaded_candidates:
        candidates = st.session_state.pie_loaded_candidates
        dis_options = {f"{r['ticker']}  —  {r['name']}": r["ticker"] for r in candidates}
        dis_col, dis_add_col = st.columns([4, 1], vertical_alignment="bottom")
        with dis_col:
            dis_label = st.selectbox("Pick listing", options=list(dis_options),
                                     key="pie_dis_sel", label_visibility="collapsed")
        with dis_add_col:
            if st.button("Confirm", key="pie_dis_confirm",
                         type="primary", use_container_width=True):
                t212_ticker = dis_options[dis_label]
                if t212_ticker not in st.session_state.pie_edit:
                    st.session_state.pie_edit[t212_ticker] = 0.0
                st.session_state.pie_loaded_candidates = []
                st.rerun()

    # Search results picker
    if search_hit and search_q:
        try:
            from data_functions.ticker_db import TickerDB as _TickerDB
            st.session_state.pie_search_results = _TickerDB().get_candidates(search_q)
        except Exception as exc:
            st.error(f"Search failed: {exc}")
            st.session_state.pie_search_results = []

    if st.session_state.pie_search_results:
        results = st.session_state.pie_search_results
        srch_options = {f"{r['ticker']}  —  {r['name']}": r["ticker"] for r in results}
        pick_col, add_col = st.columns([4, 1], vertical_alignment="bottom")
        with pick_col:
            chosen_label = st.selectbox("result", options=list(srch_options),
                                        key="pie_result_sel", label_visibility="collapsed")
        with add_col:
            if st.button("+ Add", key="pie_add_extra",
                         type="primary", use_container_width=True):
                t212_ticker = srch_options[chosen_label]
                if t212_ticker not in st.session_state.pie_edit:
                    st.session_state.pie_edit[t212_ticker] = 0.0
                st.session_state.pie_search_results = []
                st.rerun()

    # ── Holdings editor ───────────────────────────────────────────────────────
    if st.session_state.pie_edit:
        st.divider()
        st.markdown(f"**Holdings  ({len(st.session_state.pie_edit)} stocks)**")

        for t, w in st.session_state.pie_edit.items():
            if f"pie_w_{t}" not in st.session_state:
                st.session_state[f"pie_w_{t}"] = w

        h1, h2, h3 = st.columns([2, 2, 1])
        h1.markdown("**Ticker**")
        h2.markdown("**Weight (%)**")

        total_w = 0.0
        for ticker in list(st.session_state.pie_edit):
            r1, r2, r3 = st.columns([2, 2, 1], vertical_alignment="center")
            r1.write(ticker)
            r2.number_input(
                "w", min_value=0.0, max_value=100.0, step=1.0,
                key=f"pie_w_{ticker}", label_visibility="collapsed"
            )
            total_w += st.session_state.get(f"pie_w_{ticker}", 0.0)
            if r3.button("✕", key=f"pie_rm_{ticker}"):
                del st.session_state.pie_edit[ticker]
                st.session_state.pop(f"pie_w_{ticker}", None)
                st.rerun()

        weight_ok = abs(total_w - 100.0) < 0.5
        if weight_ok:
            st.success(f"Total: {total_w:.1f}%  ✓")
        else:
            st.warning(f"Total: {total_w:.1f}%  —  must equal 100%")

        st.write("")

        if st.button("Update Pie", type="primary", disabled=not (weight_ok and selected_pie_id),
                     key="pie_submit"):
            holdings = {
                t: round(st.session_state.get(f"pie_w_{t}", 0.0) / 100, 6)
                for t in st.session_state.pie_edit
            }
            try:
                from data_functions.ticker_db import TickerDB as _TickerDB
                _TickerDB().set_pie_holdings(selected_pie_id, holdings)
                st.success("Pie updated!")
                st.session_state.pie_edit_id = None
                st.rerun()
            except Exception as exc:
                st.error(f"Failed: {exc}")
    else:
        st.caption("Select a pie above to load and edit its holdings.")
