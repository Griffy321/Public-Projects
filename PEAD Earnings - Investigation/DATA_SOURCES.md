# S&P 500 Removal Backtest — Data Source Findings

**Investigation date:** 2026-05-19  
**Goal:** Identify reliable sources for historical S&P 500 constituent dates and price history for removed companies.

---

## Summary

| Data Need | Source | Status | Notes |
|---|---|---|---|
| S&P 500 add/remove dates | FMP Premium | ✅ Confirmed | 1,519 records back to 1957 |
| Price history (post-2000 removals) | yfinance | ✅ Confirmed | 184 usable tickers found |
| Price history (pre-2010 famous bankruptcies) | All sources | ❌ Unavailable | Lehman, Enron, WorldCom, etc. — see below |
| Delisted companies list | FMP Premium | ⚠️ Partial | Only ~9,000 records back to 2002; does not include famous bankruptcies |

---

## Source 1 — Financial Modeling Prep (FMP)

**Plan required:** Premium (free and basic tiers return 402 for constituent history)  
**API key location:** `config.env`  
**Base URL:** `https://financialmodelingprep.com/stable`

### S&P 500 Constituent History ✅

**Endpoint:** `GET /stable/historical-sp500-constituent`  
**No parameters needed beyond `apikey`.**

```
Returns: 1,519 records from 1957-03-03 to present
Fields:  dateAdded, addedSecurity, removedTicker, removedSecurity, date, symbol, reason
```

**Important field notes:**
- `date` — the effective removal date (use this for backtesting)
- `removedTicker` — the ticker of the company that was *removed*
- `symbol` — the ticker of the company that was *added* (replacement)
- `reason` — plain-English reason (acquisition, market cap change, re-ranking, etc.)
- Some records have null `removedSecurity` or `removedTicker` — handle with `or ""`

**Sample record:**
```json
{
  "dateAdded": "September 16, 2008",
  "addedSecurity": "",
  "removedTicker": "LEHMQ",
  "removedSecurity": "Lehman Brothers Holding",
  "date": "2008-09-16",
  "symbol": "LEHMQ",
  "reason": "Annual Re-ranking"
}
```

**Confirmed removal records for well-known companies:**

| Ticker | Company | Removed |
|---|---|---|
| LEHMQ | Lehman Brothers | 2008-09-16 |
| RSH | RadioShack | 2011-06-30 |
| SHLD | Sears Holdings | 2012-09-04 |
| BBBY | Bed Bath & Beyond | 2017-07-25 |
| ENRNQ | Enron | 2001-11-29 |
| WCOM | WorldCom | 2002-05-14 |
| KODK | Eastman Kodak | 2010-12-17 |
| CC | Circuit City | 2008-03-28 |
| BSC | Bear Stearns | 2008-06-02 |
| FNMA | Fannie Mae | 2008-09-10 |
| FMCC | Freddie Mac | 2008-09-10 |

---

### Price History — EOD ⚠️

**Endpoint:** `GET /stable/historical-price-eod/full?symbol={ticker}&from={YYYY-MM-DD}&to={YYYY-MM-DD}`

**Coverage is limited for delisted companies.** FMP primarily holds price data for currently or recently active tickers. Famous pre-2015 bankruptcies return empty arrays even on Premium.

**Confirmed to have data:**
- `BBBY` — 4,276 bars (1998–2014) + 1,006 bars (2020–2023)

**Returns empty array for:** `LEH`, `RSH`, `SHLD`, `ENE`, `WCOM`, `KODK`, `CC`, `BSC`

> **Caution:** Tickers like `SHLD` and `CC` do return data on FMP, but it belongs to *modern companies that reused those ticker symbols* — not Sears or Circuit City.

---

### Delisted Companies List ⚠️

**Endpoint:** `GET /stable/delisted-companies?page={n}&limit=100`

- Free tier: page 0 only (~100 records)
- Premium: pages 0–90, ~9,000 records, back to 2002
- Sorted by `delistedDate` descending
- Does **not** include Lehman, Enron, WorldCom, etc. — FMP apparently never ingested exchange delistings from that era

---

## Source 2 — yfinance (Yahoo Finance)

**Plan required:** None — completely free Python library  
**Install:** `pip install yfinance`  
**No API key needed.**

```python
import yfinance as yf
df = yf.download("BBBY", start="2012-01-01", end="2023-08-01",
                 progress=False, auto_adjust=True)
```

### Coverage for S&P 500 Removals ✅

Tested against all 300+ removal events from the FMP constituent history since 2000. **184 tickers confirmed with usable price data** (≥200 bars, avg volume ≥100k).

**Coverage goes back to at least 2000** for tickers that continued trading after removal.

**Why many removed tickers fail in yfinance:**
- Companies acquired/merged (e.g., TWTR, CELG, ATVI) — Yahoo deletes historical price data when a ticker is fully retired
- Pre-2010 bankruptcies (Lehman, Enron, etc.) — never in Yahoo's dataset or data was purged
- Ticker reuse — a new company may have claimed the same symbol

**Version note:** yfinance `0.2.x` is broken against the current Yahoo Finance API. Must use `≥1.0`. Verified working on `1.3.0`.

### 184 Confirmed Usable Removals — Date Range

| Era | Count | Notes |
|---|---|---|
| 2024–2026 | ~30 | Very recent; full 2-year pre-removal history available |
| 2015–2023 | ~80 | Strong coverage; most market-cap demotions and acquisitions |
| 2008–2014 | ~50 | Good coverage; financial crisis removals included |
| 2000–2007 | ~24 | Older but confirmed working (e.g., AT&T 2005, HealthSouth 2003) |

### Recommended Picks (varied era, varied removal reason)

| Ticker | Company | Removed | Reason | Bars |
|---|---|---|---|---|
| CTRA | Coterra Energy | 2026-05-07 | Acquired by Devon | 502 |
| MHK | Mohawk Industries | 2025-12-22 | Market cap | 518 |
| QRVO | Qorvo | 2024-12-22 | Market cap | 518 |
| ALK | Alaska Air | 2023-12-15 | Market cap | 522 |
| FNMA | Fannie Mae | 2008-09-10 | Annual re-ranking | 525 |
| JCI | Johnson Controls | 2009-03-16 | Annual re-ranking | 523 |
| T | AT&T Corp. (old) | 2005-11-18 | Acquired by SBC | 524 |
| EHC | HealthSouth | 2003-03-20 | Annual re-ranking | 521 |
| MIR | Mirage Resorts | 2000-05-31 | Annual re-ranking | 526 |
| SCI | Service Corp. Int'l | 2000-03-15 | Annual re-ranking | 527 |

---

## Source 3 — Stooq (Investigated, Not Viable)

Stooq previously provided free CSV downloads via `pandas_datareader` and direct HTTP. As of 2025/2026 they now **require a captcha-verified API key** for programmatic access. Not a usable automated source.

---

## Dead Ends — Pre-2010 Famous Bankruptcies

The following tickers have **no price data on any tested free source:**

| Ticker | Company | Reason |
|---|---|---|
| LEH | Lehman Brothers | Data never ingested by Yahoo/FMP |
| ENE | Enron | Data never ingested by Yahoo/FMP |
| WCOM | WorldCom | Data never ingested by Yahoo/FMP |
| BSC | Bear Stearns | Data never ingested by Yahoo/FMP |
| CC | Circuit City | Ticker reused; original data gone |
| KODK | Eastman Kodak | Ticker reused; original data gone |

**If this data is needed**, paid options include:
- **CRSP** (via Wharton WRDS) — gold standard for academic survivorship-bias-free data
- **Bloomberg Terminal** — comprehensive but expensive
- **Refinitiv/LSEG Workspace** — enterprise pricing

For most backtesting purposes, the 184 confirmed tickers above provide sufficient sample size without needing the famous bankruptcies specifically.

---
