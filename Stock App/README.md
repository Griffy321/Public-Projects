# Stock Analyser

A personal stock analysis tool built in Python and Streamlit. You type in a ticker, it pulls the financial data, calculates a bunch of useful metrics and shows everything in a clean dark UI. You can compare stocks side by side, overlay metrics on price charts, and even edit your Trading 212 pies directly from the app.

This started as a project to get comfortable working with financial APIs and real-world data, but it's grown into something I actually use here and there.

---

## What it does

- Pull financial data for any stock via the FMP API and cache it locally as Parquet files
- Calculate key metrics: P/E, P/B, FCF yield, D/E ratio, ROE, ROA, earnings quality, current ratio, net cash as a % of market cap
- Side-by-side comparison table across multiple stocks with green/red highlighting for best and worst values
- Price history charts with optional metric overlays (so you can see if P/E moved with the price, for example)
- Quick commentary on each stock — profitable, FCF positive, leverage level, etc.
- Trading 212 Pies tab to view, edit and rebalance your T212 pies without opening the T212 app

---

## APIs needed

**Financial Modeling Prep (FMP)** — for all the stock data. You need an API key from [financialmodelingprep.com](https://financialmodelingprep.com). The free tier covers basic usage but some endpoints need a paid plan.

**Trading 212** — only needed if you want to use the Pies tab. You need an API key and secret from your T212 account settings.

Both keys are entered through the sidebar in the app and saved locally — they're never sent anywhere other than the respective APIs.

---

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

Enter your FMP key in the sidebar when the app opens and you're good to go.

---

## How it works

Data is fetched from FMP, normalised into clean internal objects, and then metrics are calculated from those. Everything gets stored locally as Parquet files so repeat lookups are fast and don't eat API calls. The Streamlit UI sits on top and just reads from those cached files.

The T212 integration lets you load up a pie, adjust the weightings, and push the update back — useful for rebalancing without having to faff around in the T212 UI.

---

## Stack

- Python
- Streamlit
- Pandas
- Plotly
- FMP API
- Trading 212 API
