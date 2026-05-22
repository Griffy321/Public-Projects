# Lead-Lag Backtest — Build Specification

**Strategy:** Intra-Industry Lead-Lag Effect (Large-Cap Earnings → Small-Cap Catch-Up)
**Universe:** Currently-trading small-cap stocks across 4 US sectors
**Backtest window:** 5 years (2021-05-20 to 2026-05-20)
**Primary parameters:** BEAT_THRESHOLD=10%, HOLD_DAYS=20 (selected from Phase 1 heatmap)
**Language:** Python
**Output:** Two-panel chart (cumulative returns vs SPY + per-sector excess return bars),
            plus parameter sweep heatmap (re-run for each new sector)

> **Scope note:** This backtest intentionally excludes survivorship bias correction. The universe
> is restricted to stocks currently trading. This is a signal validity test — the goal is to
> establish whether the lead-lag mechanism produces alpha at all before adding complexity.
> Survivorship bias correction is documented as a planned Phase 3 extension.

> **Project separation:** This is an entirely independent project from the PEAD backtest
> (`pead_backtest/`). The two share an FMP API key and the yfinance pattern for price fetching,
> but no code, data files, or assumptions are shared or reused. Do not mix the two.

> **Phase history:**
> - Phase 1 (complete): Single-sector backtest on US Semiconductors vs SOXX benchmark.
>   Result: 20.0% annualised vs 30.2% annualised for SOXX. Strategy tracked benchmark closely
>   until the 2025-2026 AI boom concentrated returns in a handful of mega-cap anchors.
>   Heatmap showed Sharpe peaking at BEAT_THRESHOLD=10%, HOLD_DAYS=20 (Sharpe 1.23) —
>   the opposite of the theoretically predicted short-lag peak, suggesting information
>   diffusion in semiconductors is slower than the academic literature assumes (~3-4 weeks
>   rather than 1-2 weeks). Effect degraded at 60 days, consistent with eventual resolution.
> - Phase 2 (this spec): Expand to 4 sectors, switch primary benchmark to SPY, add
>   per-sector excess return panel. Primary parameters locked to heatmap optimum.

---

## 1. Overview

The strategy is based on the intra-industry lead-lag effect documented in academic literature
(Hou, 2007; Cen et al., 2013). Within an industry, large-cap stock returns lead small-cap
returns due to the slow diffusion of industry-level information. When a large-cap company in
a sector reports a positive earnings surprise, the new information about sector demand, pricing
power, and industry conditions takes days to weeks to propagate into the share prices of
smaller peers.

The backtest tests whether buying a basket of small-cap stocks in the same sector immediately
after a large-cap earnings beat produces excess returns over the subsequent holding period,
across four distinct sectors.

**Trigger:** A large-cap "anchor" ticker in a covered sector reports earnings with an EPS
surprise above BEAT_THRESHOLD (10%).

**Trade:** On the next trading day, buy an equal-weighted basket of all currently-trading
small-cap tickers in the same sector (market cap $100M–$2B, average daily volume ≥ 500k shares).

**Exit:** Close all positions after exactly 20 trading days.

**Primary benchmark:** SPY (S&P 500 ETF) — the market-level baseline. Used on the main
cumulative returns chart for all sectors combined.

**Secondary benchmark (per-sector):** Each sector's representative ETF, used only in the
excess return bar panel. See Section 2.1 for the ETF mapping.

**Core questions:**
1. Does the lead-lag strategy beat the broad market (SPY) when run across multiple sectors?
2. Does the strategy beat its own sector ETF on a per-sector basis?
3. Is the effect consistent across sectors, or concentrated in one?

---

## 2. Sector & Ticker Definitions

### 2.1 Covered Sectors

Four sectors are included in Phase 2. Each has a curated anchor list, a small-cap screener
definition, and a sector ETF benchmark for the excess return panel.

| Sector | Sector ETF | FMP Sector Filter | FMP Industry Filter |
|--------|-----------|-------------------|---------------------|
| Semiconductors | SOXX | `Technology` | `Semiconductors` |
| Energy | XLE | `Energy` | `Oil & Gas E&P` |
| Financials | XLF | `Financial Services` | `Banks—Regional` |
| Healthcare | XLV | `Healthcare` | `Biotechnology` |

**Note on FMP industry filters:** FMP's industry taxonomy can be inconsistent. If the industry
filter returns fewer than 10 small-cap candidates after the liquidity filter, broaden to the
sector-level filter only (drop the industry parameter) and re-run. Log which sectors required
broadening in Section 12 (Implementation Discoveries).

### 2.2 Large-Cap Anchor Tickers (Hardcoded per Sector)

#### Semiconductors (carried forward from Phase 1)

| Ticker | Company | Why Included |
|--------|---------|--------------|
| `MU`   | Micron Technology | Memory/NAND — direct read-across to small-cap peers |
| `WDC`  | Western Digital | NAND/HDD — sector bellwether |
| `NVDA` | Nvidia | GPU/AI accelerator demand — drives entire semi capex cycle |
| `AMAT` | Applied Materials | Equipment — leading indicator for fab investment |
| `LRCX` | Lam Research | Equipment — different customer mix from AMAT |
| `MRVL` | Marvell Technology | Data centre semiconductors — AI networking |
| `AMD`  | Advanced Micro Devices | CPU/GPU — signals demand alongside Nvidia |
| `INTC` | Intel | CPU/foundry — legacy bellwether |
| `QCOM` | Qualcomm | Mobile/IoT semiconductors |
| `TXN`  | Texas Instruments | Analog/embedded — industrial demand signal |

#### Energy

| Ticker | Company | Why Included |
|--------|---------|--------------|
| `XOM`  | ExxonMobil | Largest US integrated oil — E&P results set sector tone |
| `CVX`  | Chevron | Second largest integrated — corroborates XOM signal |
| `COP`  | ConocoPhillips | Pure-play E&P — most direct read-across to small E&P peers |
| `EOG`  | EOG Resources | Large independent E&P — Permian/shale bellwether |
| `PXD`  | Pioneer Natural Resources | Major Permian operator (acquired by XOM 2024 — include through acquisition date, then drop) |
| `DVN`  | Devon Energy | Large independent E&P — meaningful production reporter |
| `HAL`  | Halliburton | Oilfield services — capex cycle signal for drillers |
| `SLB`  | SLB (Schlumberger) | Largest oilfield services — global activity signal |

#### Financials

| Ticker | Company | Why Included |
|--------|---------|--------------|
| `JPM`  | JPMorgan Chase | Largest US bank — most-watched earnings in financials |
| `BAC`  | Bank of America | Second largest — net interest margin signal for regionals |
| `WFC`  | Wells Fargo | Large retail bank — most comparable to regional peers |
| `USB`  | U.S. Bancorp | Large regional — bridge between mega-cap and small regionals |
| `PNC`  | PNC Financial | Large regional — midwest/mid-Atlantic footprint |
| `GS`   | Goldman Sachs | Investment banking signal — different from regionals but included for breadth |
| `MS`   | Morgan Stanley | Wealth management / IB — complements GS |

#### Healthcare

| Ticker | Company | Why Included |
|--------|---------|--------------|
| `LLY`  | Eli Lilly | Largest pharma by market cap — GLP-1/obesity drug signal |
| `JNJ`  | Johnson & Johnson | Diversified healthcare — broad sector signal |
| `UNH`  | UnitedHealth Group | Largest health insurer — managed care signal |
| `MRK`  | Merck | Large pharma — oncology/vaccine pipeline signal |
| `ABBV` | AbbVie | Large biotech/pharma — immunology signal |
| `BMY`  | Bristol-Myers Squibb | Large pharma — oncology pipeline |
| `AMGN` | Amgen | Large biotech — biologics manufacturing signal |
| `GILD` | Gilead Sciences | Large biotech — antiviral/oncology signal |

**Rationale for fixed lists:** Consistent with Phase 1. Dynamic screening would require
historical market cap data per quarter, adding significant complexity. The lists are reviewed
and fixed at spec time. They can be revised between phases.

### 2.3 Small-Cap Universe (Currently Trading Only, Per Sector)

One universe is built per sector. Each is constructed and filtered independently. The same
market cap bounds and liquidity filters apply across all sectors.

**Screening criteria (FMP Stock Screener):**

| Filter | Value |
|--------|-------|
| Market cap min | $100,000,000 |
| Market cap max | $2,000,000,000 |
| Exchange | `NASDAQ,NYSE` |
| Country | `US` |
| Sector + Industry | See Section 2.1 per sector |

**Post-screen liquidity filter (applied after yfinance price fetch):**
- Average daily volume ≥ 500,000 shares over the 504 trading days prior to 2021-05-20
- Minimum 504 trading days of price history in yfinance
- Anchor tickers excluded from each sector's small-cap universe

**Expected universe sizes:**
- Semiconductors: 20–50 tickers (carried from Phase 1)
- Energy: 30–70 tickers (E&P space is populous)
- Financials: 50–100 tickers (regional banks are numerous)
- Healthcare/Biotech: 20–60 tickers (many small biotechs are illiquid — expect significant
  drop-off at the volume filter)

If any sector produces fewer than 10 tickers after filtering, log a warning and note that
results for that sector should be treated with caution due to low sample size.

---

## 3. Data Sources

### 3.1 Source A — Financial Modeling Prep (FMP)

**Plan required:** Premium
**API key:** Stored in `config.env` as `FMP_API_KEY`
**Base URL:** `https://financialmodelingprep.com/stable`
**Auth:** Append `?apikey={key}` or `&apikey={key}` to every request

#### Endpoint 1 — Earnings History (per anchor ticker)

```
GET https://financialmodelingprep.com/stable/earnings?symbol={TICKER}&apikey={key}
```

**Purpose:** Full earnings history for each anchor ticker. Source of all trigger events.

**Known behaviour (from PEAD discovery 10.3):**
- Do NOT use `/stable/earnings-calendar` — returns 402 for dates before ~August 2021.
- Per-ticker endpoint has no historical depth restriction. Use for all anchors.

**Known field names (from PEAD discovery 10.4) — normalise on ingest:**

| API field | Normalised column |
|-----------|------------------|
| `epsActual` | `eps` |
| `epsEstimated` | `epsestimated` |
| `revenueActual` | `revenue` |
| `revenueEstimated` | `revenueestimated` |
| `date` | `date` |
| `symbol` | `symbol` |

**Known gap (from PEAD discovery 10.5):**
No `time` (bmo/amc) field returned. Treat all events as `amc` — enter at close of D+1.

**Usage:**
- Fetch for all anchors across all 4 sectors (~33 tickers total)
- Concatenate into a single DataFrame with a `sector` column added
- Filter to backtest window: 2021-05-20 to 2026-05-20
- Drop records where `epsestimated` is null, zero, or `eps` is null
- Calculate surprise score (see Section 5.2)
- Save full unfiltered earnings history as `data/earnings_all.parquet`
- Save filtered trigger events (surprise ≥ BEAT_THRESHOLD) as `data/earnings_triggers.parquet`
- The threshold filter is also re-applied at runtime in the backtest loop to allow parameter
  sweeps without re-fetching

---

#### Endpoint 2 — Stock Screener (per-sector universe construction)

```
GET https://financialmodelingprep.com/stable/company-screener?sector={SECTOR}&industry={INDUSTRY}&marketCapMoreThan=100000000&marketCapLessThan=2000000000&exchange=NASDAQ,NYSE&country=US&apikey={key}
```

Called once per sector (4 calls total). Results saved per sector:
- `data/candidates_semiconductors.parquet`
- `data/candidates_energy.parquet`
- `data/candidates_financials.parquet`
- `data/candidates_healthcare.parquet`

---

#### Endpoint 3 — Stock Peers (supplementary, per anchor)

```
GET https://financialmodelingprep.com/stable/stock-peers?symbol={TICKER}&apikey={key}
```

Called for each anchor. Used to catch small-cap peers that may have slightly off industry
classifications in FMP. Cross-check market cap via the profile endpoint before adding.
Best-effort — skip if it adds no qualifying tickers.

---

#### Endpoint 4 — Company Profile (market cap validation for peer additions)

```
GET https://financialmodelingprep.com/stable/profile?symbol={TICKER}&apikey={key}
```

Spot-check only. Called for tickers sourced from peers step, not from screener.

---

### 3.2 Source B — yfinance (Yahoo Finance)

**Install:** `pip install "yfinance>=1.0"`
**Version requirement:** Must be ≥1.0. Version 0.2.x is broken. Confirmed on 1.0.x+.
**No API key required.**

```python
import yfinance as yf
df = yf.download(ticker, start="2019-01-01", end="2026-05-20",
                 progress=False, auto_adjust=True)
```

**Purpose:** Daily EOD price data for all tickers — all small-cap universe candidates across
all sectors, all anchor tickers (reference), and all benchmark ETFs (SPY, SOXX, XLE, XLF, XLV).

**Fetch window:** 2019-01-01 to 2026-05-20. The two-year pre-backtest window (2019–2021) is
used solely for the liquidity filter calculation. It is not used in the backtest itself.

**`auto_adjust=True`:** Required. Split- and dividend-adjusted prices for accurate returns.

**Liquidity filter:**
- Compute average daily volume over 2019-01-01 to 2021-05-20 (pre-backtest window)
- Drop tickers with average daily volume < 500,000 shares
- Drop tickers with fewer than 504 total bars in yfinance
- Log all dropped tickers to `data/excluded_tickers.txt` with reason and sector

**Price lookup during backtest:**
- Entry price = close on D+1 (next trading day after anchor earnings date)
- Exit price = close on D+1+20 trading days
- Days counted using the yfinance date index of each ticker
- If price unavailable on exact entry/exit date, advance up to 3 days. If still unavailable,
  skip trade for that ticker and log to `data/skipped_trades.txt`

---

## 4. Project Structure

```
leadlag_backtest/
├── config.env                              # FMP_API_KEY
├── requirements.txt
├── data/
│   ├── earnings_all.parquet                # Full earnings history, all anchors, all sectors
│   ├── earnings_triggers.parquet           # Filtered: beats only, within backtest window
│   ├── candidates_semiconductors.parquet   # Screener output, pre-liquidity filter
│   ├── candidates_energy.parquet
│   ├── candidates_financials.parquet
│   ├── candidates_healthcare.parquet
│   ├── universe_semiconductors.parquet     # Post-liquidity-filter universe per sector
│   ├── universe_energy.parquet
│   ├── universe_financials.parquet
│   ├── universe_healthcare.parquet
│   ├── excluded_tickers.txt                # Tickers dropped at liquidity filter
│   ├── skipped_trades.txt                  # Trades skipped due to missing prices
│   └── prices/
│       └── {TICKER}.parquet                # Per-ticker price history (all tickers)
├── src/
│   ├── 01_fetch_earnings_triggers.py       # Earnings for all anchors → trigger events
│   ├── 02_build_universes.py               # Screener + peers → candidate lists (all sectors)
│   ├── 03_fetch_prices.py                  # yfinance for all tickers + benchmarks
│   ├── 04_run_backtest.py                  # Core loop across all sectors + parameter sweep
│   └── 05_plot_results.py                  # Two-panel chart + heatmap
└── output/
    ├── leadlag_returns_vs_spy.png           # Primary two-panel chart
    └── parameter_sweep_heatmap.png          # Sharpe heatmap (all sectors combined)
```

**Design principle:** Each script is idempotent — checks for existing cached parquet files
and skips fetching if already present. Critical for the price fetch step which may touch
150+ tickers across four sectors.

---

## 5. Parameters

### 5.1 Primary Run Parameters (locked from Phase 1 heatmap)

| Parameter | Value | Basis |
|-----------|-------|-------|
| `BEAT_THRESHOLD` | 0.10 (10%) | Highest Sharpe cell in Phase 1 heatmap |
| `HOLD_DAYS` | 20 | Highest Sharpe cell in Phase 1 heatmap (Sharpe 1.23) |
| `ENTRY_LAG` | 1 | Fixed — enter at close of D+1 (amc treatment) |
| `MARKET_CAP_MIN` | $100,000,000 | Fixed |
| `MARKET_CAP_MAX` | $2,000,000,000 | Fixed |
| `MIN_AVG_VOLUME` | 500,000 | Fixed |

### 5.2 Parameter Sweep (re-run for completeness across new sectors)

The full 3×4 sweep is re-run with the combined multi-sector portfolio to confirm the
Phase 1 heatmap finding generalises. Same grid as Phase 1:

| Parameter | Values |
|-----------|--------|
| `BEAT_THRESHOLD` | 0.03, 0.05, 0.10 |
| `HOLD_DAYS` | 5, 10, 20, 60 |

12 combinations total. The heatmap shows combined Sharpe across all sectors. If a sector
shows a materially different optimal combination, note it in the console output.

---

## 6. Backtest Logic

### 6.1 Trigger Event Construction

For each anchor ticker, after normalising earnings data:

```python
surprise = (eps - epsestimated) / abs(epsestimated)
```

A trigger event fires when:
- `surprise >= BEAT_THRESHOLD`
- Both `eps` and `epsestimated` are non-null and non-zero
- Event date falls within 2021-05-20 to 2026-05-20

Each trigger event record: `{date, anchor_symbol, sector, eps, epsestimated, surprise, entry_date}`

`entry_date` = next available trading day after `date`, resolved from the anchor's yfinance
price calendar.

**Deduplication within a sector:** If two anchors in the same sector report on the same day
and both beat, two separate trigger events are recorded. Small caps are entered twice
(overlapping positions). This is intentional — each anchor is an independent signal.
Log the overlap count in summary statistics.

**Cross-sector independence:** Trigger events in different sectors are fully independent.
No cross-sector positions are taken. Energy triggers only buy energy small caps.

### 6.2 Entry and Exit

- **Entry price:** Close of small-cap ticker on `entry_date` (D+1)
- **Exit price:** Close on `entry_date + 20` trading days
- If close unavailable on exact date, advance up to 3 trading days. If still unavailable,
  skip and log.
- If price series ends before exit (ticker halted mid-hold), exit at last available close
  and flag `early_exit = True`

No stop-loss. No take-profit. Pure signal test.

### 6.3 Position Sizing

Equal weight across all small-cap tickers in a sector's universe on each trigger event.
Equal weight across concurrent trigger events within a sector.
Sectors are treated as independent sub-portfolios — each receives an equal share of total
capital. Combined portfolio = average of four sector sub-portfolios, rebalanced daily.

No leverage. No shorting.

### 6.4 Returns Calculation

**Individual trade:**
```python
trade_return = (exit_price - entry_price) / entry_price
```

**Sector sub-portfolio daily return:**
Equal-weighted average of all active trade daily returns within that sector on that day.

**Combined portfolio daily return:**
Equal-weighted average of the four sector sub-portfolio daily returns.

**Cumulative return:** Compounded daily combined portfolio returns across the full window.

**Benchmark returns:**
- SPY: compounded daily returns over same window (primary chart)
- SOXX, XLE, XLF, XLV: compounded daily returns over same window (excess return panel)

---

## 7. Data Quality & Edge Case Handling

| Scenario | Handling |
|----------|----------|
| `epsestimated` null, zero, or missing | Drop trigger event |
| `eps` null or missing | Drop trigger event |
| Surprise below BEAT_THRESHOLD | No trigger fires |
| Small-cap ticker has no price on entry date (±3 days) | Skip ticker for that trade, log |
| Small-cap price series ends before exit date | Exit at last available close, flag `early_exit` |
| Anchor ticker appears in screener output | Exclude from that sector's small-cap universe |
| Trigger fires with zero qualifying small caps after filters | Log event, skip |
| Two anchors in same sector report same day, both beat | Two overlapping trigger events — allowed |
| PXD acquired by XOM (October 2023) | Include PXD earnings through last available date; drop from anchor list after acquisition |
| Sector produces fewer than 10 small caps after liquidity filter | Log warning; include in backtest but flag low-sample caution in output |
| Benchmark ETF price unavailable on a date | Forward-fill from previous close (max 1 day) |
| yfinance returns fewer than 504 bars | Exclude from universe, log |
| Average daily volume < 500k | Exclude from universe, log |
| Earnings date on weekend or market holiday | Advance entry date to next trading day |

---

## 8. Output

### 8.1 Primary Chart — Two-Panel Layout

Saved to `output/leadlag_returns_vs_spy.png`.

**Top panel — Cumulative Returns vs SPY:**

Lines plotted (all indexed to 1.0 at 2021-05-20):
- **Combined strategy** (all 4 sectors, equal weight) — solid blue, labelled with final
  cumulative return and annualised return
- **SPY benchmark** — dashed red, labelled with final cumulative return and annualised return
- **Semiconductors sub-portfolio** — thin solid line, muted colour
- **Energy sub-portfolio** — thin solid line, muted colour
- **Financials sub-portfolio** — thin solid line, muted colour
- **Healthcare sub-portfolio** — thin solid line, muted colour

The four sector sub-portfolio lines are plotted thin and semi-transparent so the combined
strategy and SPY remain the visual focus. They give texture without cluttering.

Chart subtitle: `Parameters: BEAT_THRESHOLD=10%, HOLD_DAYS=20d | Total trigger events: X`

**Bottom panel — Excess Return vs Sector ETF (annualised, bar chart):**

Four bars, one per sector:
- Each bar = annualised return of that sector's sub-portfolio minus annualised return of its
  sector ETF (SOXX, XLE, XLF, XLV) over the same window
- Positive bar = strategy beat its own sector ETF
- Negative bar = strategy underperformed its sector ETF
- Bars coloured green (positive) or red (negative)
- Y-axis label: `Excess Return vs Sector ETF (annualised, pp)`
- Horizontal line at 0 for reference
- Each bar annotated with its value (e.g. "+3.2pp" or "-8.1pp")

**Why two panels:** The top panel answers "did this beat the market?" The bottom panel answers
"did this beat just being in the sector?" They are different questions and both matter.

### 8.2 Parameter Sweep Heatmap

Saved to `output/parameter_sweep_heatmap.png`.

Same 3×4 layout as Phase 1. Shows annualised Sharpe for the combined multi-sector portfolio.
Subtitle notes the Phase 1 result (semi-only, Sharpe 1.23 at 10%/20d) for comparison.

### 8.3 Summary Statistics (printed to console, primary parameters)

```
Backtest period:              2021-05-20 to 2026-05-20
Parameters:                   BEAT_THRESHOLD=10%, HOLD_DAYS=20d

--- COMBINED PORTFOLIO ---
Total trigger events fired:   X  (across all sectors)
Total individual trades:      X
Trades with early exit:       X
Trades skipped (no price):    X

Combined annualised return:   X.X%
SPY benchmark return:         X.X%
Excess return vs SPY:         X.Xpp

Combined Sharpe ratio:        X.XX
SPY Sharpe ratio:             X.XX
Combined max drawdown:        -X.X%

Win rate (baskets):           X.X%
Win rate (individual trades): X.X%

--- PER SECTOR ---
Sector          | Universe | Triggers | Ann. Return | Sector ETF | Excess  | Sharpe
Semiconductors  |    X     |    X     |    X.X%     |   X.X%     | X.Xpp   | X.XX
Energy          |    X     |    X     |    X.X%     |   X.X%     | X.Xpp   | X.XX
Financials      |    X     |    X     |    X.X%     |   X.X%     | X.Xpp   | X.XX
Healthcare      |    X     |    X     |    X.X%     |   X.X%     | X.Xpp   | X.XX
```

### 8.4 Caveats (printed to console)

```
NOTE: Survivor-only universe. Small-cap stocks that were delisted, acquired, or went bankrupt
during 2021-2026 are excluded. Returns are biased upward by an unknown amount. Phase 3 will
add survivorship bias correction.

NOTE: Fixed universe. IPOs after 2021-05-20 and stocks that moved into/out of the small-cap
range during the backtest window are not captured.

NOTE: No transaction costs modelled. Small-cap bid-ask spreads would reduce live returns,
particularly in Healthcare/Biotech where spreads are widest.

NOTE: Healthcare/Biotech small-cap universe may be small (<10 tickers after liquidity filter).
Results for this sector should be treated with caution.
```

---

## 9. Implementation Order

The existing Phase 1 scripts (`01` through `05`) are **not modified**. Phase 2 is implemented
as a new set of scripts in the same project directory, operating on new data files.

1. `01_fetch_earnings_triggers.py` *(extend, do not rewrite)*
   — Add the 23 new anchor tickers across Energy, Financials, Healthcare
   — Re-fetch earnings for all anchors (idempotent — will skip cached data if present)
   — Add `sector` column to output
   — Overwrite `data/earnings_all.parquet` and `data/earnings_triggers.parquet`

2. `02_build_universes.py` *(extend)*
   — Add screener calls for Energy, Financials, Healthcare
   — Save per-sector candidate parquets
   — Semiconductor candidates already cached — skip if file exists

3. `03_fetch_prices.py` *(extend)*
   — Add all new universe tickers to the download list
   — Add XLE, XLF, XLV to benchmark downloads (SPY already fetched)
   — Idempotent — skip tickers already cached in `data/prices/`

4. `04_run_backtest.py` *(rewrite)*
   — Run backtest loop for all 4 sectors
   — Aggregate to combined portfolio
   — Run 12-combination parameter sweep for combined portfolio
   — Save per-sector and combined trade results
   — Print full summary statistics table

5. `05_plot_results.py` *(rewrite)*
   — Generate two-panel primary chart
   — Generate updated parameter sweep heatmap
   — Save both to `output/`

---

## 10. Requirements

```
yfinance>=1.0
pandas
numpy
matplotlib
seaborn
requests
python-dotenv
pyarrow
tqdm
```

No new dependencies required vs Phase 1.

---

## 11. Known Limitations

- **Survivor-only universe:** Most significant limitation. Stocks delisted or acquired during
  2021–2026 are excluded. Upward bias of unknown magnitude. Phase 3 extension planned.

- **Fixed universe:** Built once at construction time. IPOs and market-cap crossings during
  the backtest window are not captured.

- **PXD acquisition:** Pioneer Natural Resources was acquired by ExxonMobil in October 2023.
  It is included as an anchor through its last available earnings date and then dropped.
  This is handled explicitly in the edge case table.

- **Healthcare universe concentration risk:** Many biotech small-caps fail the 500k volume
  filter. The healthcare sub-portfolio may rest on a very small number of tickers, making
  its results high-variance and less reliable than the other sectors.

- **No transaction costs:** Bid-ask spreads and commissions not modelled. Material for
  small-caps, especially in biotech.

- **EPS estimate quality:** FMP consensus estimates may differ from what was available at
  announcement time. Standard limitation for retail-grade backtests.

- **Period specificity:** 2021–2026 includes the COVID recovery, the rate hike cycle, and the
  AI boom. Results may not generalise to other macro regimes.

- **Equal sector weighting:** The combined portfolio weights all four sectors equally regardless
  of the number of trigger events or universe size. A sector with 5 triggers and 10 small caps
  gets the same weight as one with 50 triggers and 80 small caps. This is a deliberate
  simplification — it keeps the cross-sector comparison clean.

---

## 12. Implementation Discoveries

*Carry forward all entries from Phase 1 (Section 10 of the original spec). New discoveries
from Phase 2 implementation are appended below. Entries here take precedence over the spec.*

### Carried from Phase 1

**12.1** FMP column names are returned lowercase. All columns lowercased on ingest before
saving to parquet.

**12.2** FMP constituent endpoint returns an undocumented `dateadded` column. Always use
`date` for point-in-time lookups. (Context: PEAD project. Not directly relevant here but
retained for reference.)

**12.3** `/stable/earnings-calendar` returns 402 for dates before ~August 2021 even on
Premium. Use per-ticker `/stable/earnings?symbol=` for all earnings fetching.

**12.4** Per-ticker earnings endpoint returns `epsActual` / `epsEstimated` / `revenueActual`
/ `revenueEstimated`. Normalise to lowercase on ingest.

**12.5** Per-ticker earnings endpoint returns no `time` (bmo/amc) field. All events treated
as `amc` — enter at close of D+1.

**12.6** Surprise scores from `(eps - epsestimated) / abs(epsestimated)` produce extreme
outliers when `epsestimated` is near-zero but non-zero. Range observed: −694 to +1,358 in
PEAD dataset. Apply winsorisation at ±20 before ranking or filtering if outliers cause issues.

*Phase 2 discoveries — append here as implementation proceeds.*
