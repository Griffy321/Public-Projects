# PEAD Backtest — Build Specification

**Strategy:** Post-Earnings Announcement Drift (PEAD)
**Universe:** S&P 500 constituents (point-in-time, survivorship-bias-free)
**Backtest window:** 15 years (2011-05-19 to 2026-05-19)
**Holding period:** 10 trading days
**Language:** Python
**Output:** Cumulative returns chart vs S&P 500 benchmark

---

## 1. Overview

The strategy enters a long position in every S&P 500 constituent the day after it reports earnings, holds for exactly 10 trading days, and then exits. No filtering on surprise direction or magnitude — all earnings events are traded. Positions are sized equally across all concurrent holdings.

The core hypothesis being tested: does the market systematically underreact to earnings announcements in S&P 500 stocks, producing a drift that can be captured over a 10-day holding window?

---

## 2. Data Sources

### 2.1 Source A — Financial Modeling Prep (FMP)

**Plan required:** Premium
**API key:** stored in `config.env` as `FMP_API_KEY`
**Base URL:** `https://financialmodelingprep.com/stable`
**Auth:** append `?apikey={key}` to every request (or `&apikey={key}` when other params exist)

#### Endpoint 1 — Historical S&P 500 Constituent Changes

```
GET https://financialmodelingprep.com/stable/historical-sp500-constituent?apikey={key}
```

**Purpose:** Reconstruct point-in-time index membership. This is the primary defence against survivorship bias.

**Returns:** 1,519 records from 1957 to present.

**Key fields:**

| Field | Description |
|---|---|
| `date` | Effective date of the change (use this as the event date) |
| `symbol` | Ticker of the company *added* to the index |
| `addedSecurity` | Name of the company added |
| `removedTicker` | Ticker of the company *removed* (may be null) |
| `removedSecurity` | Name of the company removed (may be null or empty string) |
| `reason` | Plain-English reason for the change |

**Usage in backtest:**
- Parse all records into a `changes` DataFrame
- Reconstruct the full constituent list on any given date:
  - Start from the current S&P 500 list
  - Walk changes backwards in time, reversing additions and removals
  - For each earnings event, confirm the ticker was in the index on that date before including it

**Edge case:** Some records have `null` or `""` for `removedTicker` / `removedSecurity` — handle with `.fillna("")` or `or ""`.

---

#### Endpoint 2 — Earnings Calendar (date-range query)

```
GET https://financialmodelingprep.com/stable/earnings-calendar?from={YYYY-MM-DD}&to={YYYY-MM-DD}&apikey={key}
```

**Purpose:** Get all earnings announcement dates with EPS estimates and actuals across the full 15-year window.

**Parameters:**

| Param | Value | Notes |
|---|---|---|
| `from` | `YYYY-MM-DD` | Start of date range |
| `to` | `YYYY-MM-DD` | End of date range |

**Important pagination note:** The legacy v3 endpoint enforced a 3-month maximum window per call. Treat the stable endpoint the same way and loop in 3-month chunks across 15 years (~60 iterations) to be safe.

**Key fields:**

| Field | Description |
|---|---|
| `symbol` | Ticker |
| `date` | Earnings announcement date |
| `epsEstimated` | Analyst consensus EPS estimate |
| `eps` | Actual reported EPS |
| `time` | `amc` (after market close) or `bmo` (before market open) |
| `revenue` | Actual reported revenue (if available) |
| `revenueEstimated` | Revenue estimate (if available) |

**Usage in backtest:**
- Filter to only tickers confirmed as S&P 500 constituents on the announcement date
- Calculate surprise score: `(eps - epsEstimated) / abs(epsEstimated)`
- Handle `epsEstimated == 0` to avoid division by zero — drop these rows
- Entry timing: if `time == bmo`, market has already reacted at open so enter at close that same day. If `time == amc`, enter at open the *next* trading day. See Section 4.2 for full entry logic.

---

#### Endpoint 3 — Earnings Report (per-ticker)

```
GET https://financialmodelingprep.com/stable/earnings?symbol={TICKER}&apikey={key}
```

**Purpose:** Per-ticker earnings history, used to fill gaps or verify dates where the calendar endpoint returns incomplete data.

**Usage:** Secondary / validation only. If a ticker appears in the constituent list but has no entries in the calendar sweep, query this endpoint directly to check whether earnings data exists.

---

#### Endpoint 4 — S&P 500 Index Price History (benchmark)

```
GET https://financialmodelingprep.com/stable/historical-price-eod/full?symbol=%5EGSPC&from={YYYY-MM-DD}&to={YYYY-MM-DD}&apikey={key}
```

**Note:** `^GSPC` must be URL-encoded as `%5EGSPC`.

**Purpose:** Daily close prices for the S&P 500 index across the 15-year backtest window, used as the benchmark series for the final returns chart.

**Important — 5-year fetch limit:** FMP restricts EOD calls to a 5-year window per request. Loop in 5-year chunks (3 iterations for 15 years).

**Key fields:** `date`, `close`

---

### 2.2 Source B — yfinance (Yahoo Finance)

**Plan required:** None (free)
**Install:** `pip install "yfinance>=1.0"`
**No API key required**

```python
import yfinance as yf
df = yf.download(ticker, start="YYYY-MM-DD", end="YYYY-MM-DD",
                 progress=False, auto_adjust=True)
```

**Purpose:** Daily EOD price data for all tickers — both current S&P 500 members and the 184 confirmed usable historical removals.

**Why yfinance over FMP for prices:**
FMP's EOD price endpoint returns empty arrays for most pre-2015 delisted companies. yfinance provides confirmed coverage for 184 historical removal tickers going back to 2000. FMP is not used for individual stock price data in this backtest.

**Coverage confirmed:**

| Era | Confirmed tickers |
|---|---|
| 2024–2026 | ~30 |
| 2015–2023 | ~80 |
| 2008–2014 | ~50 |
| 2000–2007 | ~24 |

**Version note:** yfinance `0.2.x` is broken against the current Yahoo Finance API. Must use `>=1.0`. Verified working on `1.3.0`.

**Usage in backtest:**
- Fetch price history per ticker over the 15-year window
- Use `auto_adjust=True` so prices are split- and dividend-adjusted — essential for computing accurate returns
- Drop tickers with fewer than 200 bars or average daily volume under 100k (illiquidity filter)
- Look up the entry price (close on entry day) and exit price (close 10 trading days later) from the fetched DataFrame

**Known gaps:**
Pre-2010 famous bankruptcies (Lehman, Enron, WorldCom, Bear Stearns, Circuit City) have no price data in yfinance. These will be excluded from the backtest. This is an accepted limitation documented in the data investigation — 184 confirmed tickers provide sufficient sample size, and the spec notes this caveat in the results output.

---

## 3. Project Structure

```
pead_backtest/
├── config.env                  # FMP_API_KEY (not committed to git)
├── requirements.txt
├── data/
│   ├── constituents.parquet    # Cached constituent change history
│   ├── earnings.parquet        # Cached earnings calendar (all tickers, 15yr)
│   └── prices/
│       └── {TICKER}.parquet    # One file per ticker, cached price history
├── src/
│   ├── 01_fetch_constituents.py
│   ├── 02_fetch_earnings.py
│   ├── 03_build_universe.py
│   ├── 04_fetch_prices.py
│   ├── 05_run_backtest.py
│   └── 06_plot_results.py
└── output/
    └── pead_returns_vs_sp500.png
```

**Design principle:** Each script writes its output to `data/` as a parquet file. Scripts are idempotent — re-running them checks for existing cached files and skips fetching if already present. This is important because fetching earnings data for 600+ tickers over 15 years will take time and burns API rate limit.

---

## 4. Backtest Logic

### 4.1 Build the Point-in-Time Universe

For every earnings event in the calendar:

1. Get the earnings date `D`
2. Look up which tickers were in the S&P 500 on date `D` using the constituent change history
3. Only include the earnings event if the ticker was a confirmed constituent on `D`

This reconstructs index membership as it actually was on each date, not as it is today.

### 4.2 Entry and Exit

**Entry:**
- If `time == bmo` (before market open): the announcement was already known at market open, so the drift starts that day. Enter at the **close of day D**.
- If `time == amc` (after market close): the announcement came out after close. Enter at the **close of day D+1** (next trading day).
- If `time` is null or unknown: default to treating as `amc` — enter at close of D+1.

**Exit:**
- Exit at the **close of the 10th trading day** after entry.
- Trading days are counted using the actual price calendar (yfinance dates), not calendar days.
- If the stock is delisted before the 10th day (i.e., the price series ends), exit at the last available close price.

### 4.3 Position Sizing

Equal weight across all positions open on any given day. If 50 stocks are in an active holding window simultaneously, each gets 1/50th of capital. This mirrors the approach used in the academic literature and the Decoding Markets backtest.

No leverage. No shorting.

### 4.4 Surprise Score (recorded but not used for filtering)

Calculate for every event:

```python
surprise = (eps - eps_estimated) / abs(eps_estimated)
```

Record this alongside each trade's return. In Phase 1 we trade all events. This data allows a Phase 2 analysis where we filter by surprise magnitude (e.g. top decile only) to see if the PEAD effect is stronger for larger surprises — consistent with academic findings.

### 4.5 Returns Calculation

For each trade:

```python
trade_return = (exit_price - entry_price) / entry_price
```

Portfolio return for each day = weighted average of all active trade returns (equal weight).

Cumulative portfolio return = compounded daily portfolio returns across the full 15-year window.

Benchmark return = compounded daily returns of `^GSPC` over the same window.

---

## 5. Data Quality & Edge Case Handling

| Scenario | Handling |
|---|---|
| `epsEstimated == 0` or null | Drop event — surprise score undefined |
| `eps` (actual) is null | Drop event — report may not have been filed yet |
| Ticker in earnings calendar but not a constituent on that date | Drop event |
| Ticker not found in yfinance | Drop event, log to missing_tickers.txt |
| yfinance returns fewer than 200 bars | Drop ticker entirely |
| Avg daily volume < 100k | Drop ticker entirely |
| Price data ends before 10-day exit | Exit at last available close |
| Earnings date falls on a weekend or market holiday | Advance to next trading day |
| Same ticker has multiple events within 10 days | Allow overlapping positions (two separate trades) |
| Ticker reuse (e.g. KODK, CC) | Validate using IPO date from FMP delisted endpoint before including historical data |

---

## 6. Output

### 6.1 Primary Chart

A single plot with two lines:

- **Strategy:** Cumulative compounded returns of the PEAD portfolio (2011–2026)
- **Benchmark:** Cumulative compounded returns of the S&P 500 index (^GSPC)

Both lines indexed to 1.0 at the start date.

Annotations:
- Final cumulative return for each series
- Shaded recession bands (2020 COVID drawdown at minimum)

### 6.2 Summary Statistics (printed to console)

```
Backtest period:         2011-05-19 to 2026-05-19
Total earnings events:   ~8,000 (estimated)
Events traded:           ~X (after all filters)
Tickers excluded:        X (logged to missing_tickers.txt)

Strategy annualised return:   X.X%
Benchmark annualised return:  X.X%
Excess return (annualised):   X.X%

Strategy Sharpe ratio:   X.XX
Benchmark Sharpe ratio:  X.XX

Strategy max drawdown:   -X.X%
Benchmark max drawdown:  -X.X%

Win rate (trades):       X.X%
```

### 6.3 Caveat note (printed to console)

```
NOTE: 184 of ~600 historical constituent tickers have confirmed price data.
Pre-2010 bankruptcies (Lehman, Enron, WorldCom, Bear Stearns, Circuit City)
are excluded due to unavailable price data. Results may overstate returns
slightly due to this partial survivorship bias for the earliest period.
```

---

## 7. Requirements

```
yfinance>=1.0
pandas
numpy
matplotlib
requests
python-dotenv
pyarrow        # for parquet caching
tqdm           # progress bars during long fetches
```

---

## 8. Implementation Order

1. `01_fetch_constituents.py` — pull and cache FMP constituent history
2. `02_fetch_earnings.py` — loop in 3-month windows across 15 years, cache all earnings events
3. `03_build_universe.py` — join constituent history to earnings events, produce a filtered events DataFrame (one row per tradeable event, with date, ticker, surprise score, entry timing flag)
4. `04_fetch_prices.py` — loop through all unique tickers in the events DataFrame, download yfinance history, cache per-ticker parquets, apply volume/bar filters
5. `05_run_backtest.py` — for each event, look up entry and exit prices, compute trade returns, aggregate to daily portfolio returns
6. `06_plot_results.py` — load portfolio returns and ^GSPC benchmark, plot cumulative returns chart, print summary stats

---

## 9. Known Limitations

- **Partial survivorship bias (pre-2010):** Price data unavailable for pre-2010 bankruptcies. Effect is bounded — these companies represent a small fraction of all earnings events across 15 years, and their exclusion likely causes a modest upward bias in early-period returns.
- **No transaction costs:** The backtest does not model bid-ask spreads or commissions. In practice, trading ~500 stocks quarterly would incur real costs that would reduce returns.
- **EPS estimate quality:** FMP's consensus estimates may differ from what was actually available to market participants at the time (some estimate providers revise historical consensus figures). This is a standard limitation of retail-grade backtests.
- **Equal weighting:** Real-world execution at equal weight across 500 stocks requires significant capital and rebalancing. The backtest is a signal test, not an execution model.

---

## 10. Implementation Discoveries

Findings from actual API responses that correct or extend the spec. Follow these over any conflicting detail above.

### 10.1 FMP Constituent Endpoint — Column Names

The spec documents field names in camelCase (`removedTicker`, `addedSecurity`, etc.) but the API returns them all **lowercase** (`removedticker`, `addedsecurity`). `01_fetch_constituents.py` lowercases all columns before writing the parquet, so downstream scripts must reference the lowercase names.

| Spec name | Actual parquet column |
|---|---|
| `symbol` | `symbol` |
| `addedSecurity` | `addedsecurity` |
| `removedTicker` | `removedticker` |
| `removedSecurity` | `removedsecurity` |
| `date` | `date` |
| `reason` | `reason` |

### 10.2 FMP Constituent Endpoint — Extra `dateadded` Column

The API returns an undocumented `dateadded` column (raw string, e.g. `"March 04, 1957"`) alongside `date`. The two are sometimes one day apart. **Always use `date`** (parsed to datetime by `01_fetch_constituents.py`) for point-in-time membership lookups in `03_build_universe.py`. Ignore `dateadded`.

---

### 10.3 Earnings Data — `stable/earnings-calendar` Has a ~5-Year Lookback Gate

The `stable/earnings-calendar` date-range endpoint returns **402 Payment Required** for any date range starting before approximately August 2021, even on a Premium plan. The v3 equivalent (`/api/v3/earning_calendar`) is blocked entirely (403) for accounts created after August 2025. Neither endpoint can deliver the full 15-year history.

**Resolution:** `02_fetch_earnings.py` was rewritten to use the per-ticker endpoint (`GET /stable/earnings?symbol={TICKER}`) which has no historical depth restriction — confirmed returning data back to 1985 for AAPL. All 1,381 unique constituent tickers are fetched individually.

### 10.4 Earnings Data — Per-Ticker Endpoint Field Name Differences

The per-ticker endpoint returns different field names from those documented in the spec for the calendar endpoint. `02_fetch_earnings.py` normalises these before saving:

| Per-ticker API field | Parquet column saved |
|---|---|
| `epsActual` | `eps` |
| `epsEstimated` | `epsestimated` |
| `revenueActual` | `revenue` |
| `revenueEstimated` | `revenueestimated` |

The API also returns an undocumented `lastupdated` field (date the record was last revised). It is preserved in the parquet but not used in the backtest.

### 10.5 Earnings Data — No `time` (bmo/amc) Field

The per-ticker endpoint does not return a `time` field. The `time` column in `earnings.parquet` and `universe.parquet` is entirely null. Per the spec's fallback rule (Section 4.2): all events are treated as `amc` — entry at **close of D+1**. This applies uniformly across the full 15-year window. The bmo/amc distinction is lost.

### 10.6 Earnings Data — Actual Record Counts

| Stage | Count |
|---|---|
| Raw records fetched (2011–2026 window) | 47,686 |
| Unique tickers with any earnings data | 912 |
| After EPS quality filter (null/zero epsestimated, null eps) | 44,199 |
| After point-in-time constituent filter | 27,939 |
| Unique tickers in final universe | 678 |

The constituent filter removes ~34% of events — this is expected and confirms the point-in-time logic is working. Many tickers in the earnings data reported during the 15-year window but were not S&P 500 members at the time.

### 10.7 Constituent Reconstruction — Actual Structure

The backward reconstruction in `03_build_universe.py` produced:
- **936 unique change dates** (not 1,519 — multiple additions/removals share a date)
- **291-ticker genesis set** (S&P 500 members before the first recorded change in 1957)

The reconstruction is correct: binary-searching to the nearest change date ≤ the earnings date returns the right constituent snapshot.

### 10.8 Surprise Score — Extreme Outliers Expected

The surprise score formula `(eps - epsestimated) / abs(epsestimated)` produces extreme values when `epsestimated` is very small but non-zero (e.g. 0.001). The universe.parquet range is **−694 to +1,358** with a median of **+0.04**. This is expected and correct — the filter only excludes `epsestimated == 0`, not near-zero values. The slight positive median reflects the well-known phenomenon of companies systematically beating consensus estimates. If Phase 2 analysis filters by surprise, **winsorise at ±10 or ±20** before ranking to avoid these outliers dominating.
