# Project 4 — Stock Analysis App with API Integration

## Overview

This project is a stock analysis application built in Python. The goal is to fetch real financial data from an external API, calculate useful valuation and financial health metrics, and present a simple investment summary for one or more stocks.

This is an analysis and research tool, not a live trading bot.

The project is designed to help build the skills needed for a later project: an API-integrated Graham-style valuation bot that can make basic buy, hold, and sell decisions.

---

## Project Goals

This project should help develop skills in:

- working with external APIs
- handling JSON responses
- structuring a multi-file Python project
- cleaning and validating real-world data
- calculating financial metrics
- separating data fetching, calculations, and reporting
- presenting analysis clearly in both CLI and UI formats
- designing a clear internal data model between API responses and app logic

---

## Core Design Principle

This project should treat **raw API JSON, internal application data, and tabular output data as different layers**.

Best practice for this project is:

- keep **raw API responses** in JSON format at the API boundary
- convert raw JSON into **clean normalized Python objects** for internal calculations
- use **pandas DataFrames only where tabular analysis or presentation is useful**

The app should **not** rely on deeply nested raw JSON throughout the codebase, and it should **not** convert all data into DataFrames immediately after fetching.

Instead, each layer should use the data structure that best fits its purpose.

---

## Data Handling Architecture

### 1. Raw API Layer

The API client should return raw JSON responses from the external provider with minimal transformation.

This layer exists to:

- communicate with the API
- preserve original response structure
- support debugging when data is missing or malformed
- optionally save raw payloads to disk

Raw API JSON should be considered an **input format**, not the app's main working format.

### 2. Normalization Layer

After fetching raw JSON, the app should extract only the fields it needs and map them into a clean internal structure.

This normalized structure should:

- use consistent field names
- convert values into appropriate Python types
- handle missing or null values safely
- isolate provider-specific response shapes from the rest of the application

This internal structure can be represented with:

- dictionaries with clearly defined keys
- `TypedDict`
- `dataclass`
- or another simple typed model

For this project, using a small typed internal model is encouraged because it makes the code easier to test, validate, and extend.

### 3. Calculation and Analysis Layer

Metric calculations and stock commentary should use the normalized internal data model rather than raw JSON or DataFrames.

This layer should focus on:

- calculating valuation metrics
- calculating financial health metrics
- applying interpretation rules
- generating summary commentary

Using normalized Python objects here keeps formulas easier to read, easier to test, and less dependent on the API provider's response structure.

### 4. Tabular Reporting Layer

DataFrames should be introduced when the app needs to work with data in a table-like way.

Good uses for DataFrames in this project include:

- comparing multiple stocks
- sorting and ranking by selected metrics
- exporting results to CSV
- rendering tables in Streamlit
- preparing data for simple charts

DataFrames should be treated primarily as a **reporting and comparison format**, not the default format for every internal operation.

---

## Core Features

### Phase 1 — Single Stock Analysis

- accept a stock ticker as input
- fetch company profile data
- fetch current price or recent price data
- fetch key financial statement data
- preserve raw API responses when useful for debugging
- normalize required fields into a clean internal stock data structure
- calculate a small set of financial and valuation metrics
- return a readable stock summary

### Initial Metrics

The first version should aim to calculate:

- current price
- EPS
- P/E ratio
- earnings yield
- revenue
- net income
- free cash flow
- total debt
- debt/equity ratio
- market cap

### Simple Analysis Output

The app should also generate basic commentary such as:

- profitable or unprofitable
- positive or negative free cash flow
- high or low leverage
- expensive, fair, or attractive valuation based on simple rules

---

## Extended Features

### Phase 2 — Multi-Stock Comparison

- accept multiple tickers
- analyse each ticker using the normalized internal data model
- convert final analysis results into a DataFrame for comparison
- display results in a comparison table
- rank or sort stocks by selected metrics

### Phase 3 — Exporting

- export analysis results to CSV
- optionally save raw API responses to JSON for debugging
- keep exported outputs separate from raw source data

### Phase 4 — UI

Once the backend works in the CLI, add a simple Streamlit UI that allows:

- ticker input
- analysis button
- stock summary cards
- comparison tables
- simple price charts
- optional filtering

The UI should display final processed results, while raw API JSON should remain behind the scenes except where needed for debugging or developer inspection.

---

## Suggested Tech Stack

- Python
- requests
- pandas
- python-dotenv
- matplotlib
- streamlit
- pytest

---

## Suggested Internal Data Strategy

A good default strategy for this project is:

- **JSON** for API input and optional raw storage
- **normalized Python objects** for cleaning, validation, calculations, and commentary
- **DataFrames** for multi-stock comparison, export, and display

A simple example normalized stock record might contain fields such as:

- ticker
- company_name
- current_price
- eps
- revenue
- net_income
- free_cash_flow
- total_debt
- shareholders_equity
- market_cap

The exact model may vary depending on the API used, but the important rule is that the rest of the app should work from this normalized structure rather than directly from provider-specific JSON.

---

## Suggested File Responsibilities

### `api_client.py` -- sorted for stocks but need to add treasurey rate data 

Responsible for:

- making API requests
- handling authentication and headers
- returning raw JSON responses
- handling request errors and response status checks

This file should know about the external provider format.

### `data_fetcher.py` -- mostly sorted, could add some batter file saving / updating 

Responsible for:

- calling API client functions
- selecting relevant parts of API responses
- validating and normalizing raw JSON into the app's internal stock data model
- combining data from multiple endpoints into one clean stock record

This file acts as the bridge between the external API and internal logic.

### `metrics.py` -- 

Responsible for:

- calculating financial and valuation metrics from normalized stock data
- handling divide-by-zero and missing-value cases safely
- returning computed metric results in a clean format

### `analysis.py`

Responsible for:

- interpreting the calculated metrics
- applying simple rules for valuation and financial health commentary
- returning readable investment-style summaries

### `reporting.py`

Responsible for:

- formatting output for CLI display
- converting multiple analysis results into DataFrames
- sorting and ranking results
- exporting results to CSV
- preparing tabular output for Streamlit

### `app.py`

Responsible for:

- Streamlit UI interactions
- collecting user input
- triggering analysis flow
- displaying summaries, tables, and charts

### `utils.py`

Responsible for shared helper functions such as:

- safe numeric conversion
- null handling
- formatting currency and percentages
- date handling
- logging or file-saving helpers

---

## Suggested File Structure

```text
project_4_stock_analyzer/
│
├── main.py
├── config.py
├── api_client.py
├── data_fetcher.py
├── metrics.py
├── analysis.py
├── reporting.py
├── utils.py
├── app.py
├── requirements.txt
├── README.md
├── tests/
│   ├── test_metrics.py
│   └── test_analysis.py
└── data/
    ├── raw/
    └── outputs/