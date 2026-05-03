import os
import requests
import sys
import pandas as pd
import yfinance as yf
import random

# 1) Grab your real key from the environment (set SEC_API_KEY beforehand).
API_KEY = os.getenv("API_KEY", "API_KEY")
if not API_KEY:
    raise ValueError("Please set your SEC_API_KEY environment variable to your real API key.")

# Base endpoint for insider trading
BASE_URL = "https://api.sec-api.io/insider-trading"
HEADERS = {"Authorization": API_KEY}

# Transaction code descriptions
TRANSACTION_CODE_MEANINGS = {
    "P": "Purchase",
    "S": "Sale",
    "A": "Grant/Award",
    "D": "Disposition",
    "F": "Payment",
    "M": "Conversion/Exercise",
    "G": "Gift",
    "V": "Voluntary",
    "J": "Other",
    "K": "Equity Swap",
    "L": "Small Acquisition",
    "U": "Tender"
}

def fetch_insider_trades(query: str, size: int = 50) -> pd.DataFrame:
    """
    Fetch up to `size` insider Form 4 trades for the given Lucene query.
    Returns empty DataFrame on errors.
    """
    size = min(size, 50)
    payload = {"query": query, "from": 0, "size": size, "sort": [{"filedAt": {"order": "desc"}}]}
    try:
        resp = requests.post(BASE_URL, headers=HEADERS, json=payload)
        resp.raise_for_status()
    except Exception as e:
        print(f"Error fetching insider trades for '{query}': {e}\n{getattr(resp, 'text', '')}")
        return pd.DataFrame()

    transactions = resp.json().get("transactions", [])
    rows = []
    for grp in transactions:
        symbol = grp.get("issuer", {}).get("tradingSymbol") or query.split(':')[-1]
        for table_name in ("nonDerivativeTable", "derivativeTable"):
            for tx in grp.get(table_name, {}).get("transactions", []) or []:
                code = tx.get("coding", {}).get("code")
                rows.append({
                    "ticker": symbol,
                    "transactionDate": tx.get("transactionDate"),
                    "transactionCode": code,
                    "transactionDesc": TRANSACTION_CODE_MEANINGS.get(code, "Unknown"),
                    "shares": tx.get("amounts", {}).get("shares"),
                    "pricePerShare": tx.get("amounts", {}).get("pricePerShare"),
                    "officerTitle": grp.get("reportingOwner", {}).get("relationship", {}).get("officerTitle")
                })
    return pd.DataFrame(rows)

def is_listed(ticker: str) -> bool:
    """Return True if the ticker has a valid market price (i.e., is currently listed)."""
    try:
        info = yf.Ticker(ticker).info
        return info.get("regularMarketPrice") is not None
    except Exception:
        return False

def get_random_mega_caps(sample_size: int = 20) -> list:
    """
    Sample from a predefined list of mega-cap tickers,
    filtered to ensure they are currently listed.
    """
    default_universe = [
        "AAPL", "MSFT", "AMZN", "GOOGL", "BRK.B", "NVDA", "META", "TSLA", "JPM", "V",
        "UNH", "HD", "PG", "MA", "DIS", "NFLX", "PFE", "BAC", "VZ", "KO",
        "NKE", "CRM", "ORCL", "IBM", "WMT", "COST", "ADBE", "CSCO", "XOM", "CVX",
        "PEP", "ABT", "TMO", "MDT", "ACN", "LLY", "TXN", "NEE", "AVGO", "SAP"
    ]
    unique_universe = list(dict.fromkeys(default_universe))
    listed = [t for t in unique_universe if is_listed(t)]
    if len(listed) < sample_size:
        print(f"Only {len(listed)} listed mega-cap tickers available; sampling all.")
        return listed
    return random.sample(listed, k=sample_size)

def analyze_trade_momentum(df: pd.DataFrame, days_after: int = 30) -> pd.DataFrame:
    """
    For each trade, fetch daily close prices from the filing date
    to `days_after` later, compute return, realizedDate, and daysDiff.
    """
    if df.empty:
        print("No trades to analyze.")
        return df
    df["transactionDate"] = pd.to_datetime(df["transactionDate"]).dt.date
    results = []
    for _, row in df.iterrows():
        tkr = row["ticker"]
        trade_date = row["transactionDate"]
        start = trade_date
        end = trade_date + pd.Timedelta(days=days_after)
        try:
            hist = yf.Ticker(tkr).history(start=start, end=end)
            closes = hist["Close"]
        except Exception as e:
            print(f"Error fetching history for {tkr}: {e}")
            closes = pd.Series()

        if len(closes) >= 1:
            initial = closes.iloc[0]
            later = closes.iloc[-1]
            ret = (later - initial) / initial
            realized_date = closes.index[-1].date()
            days_diff = (closes.index[-1].date() - trade_date).days
        else:
            ret = pd.NA
            realized_date = pd.NaT
            days_diff = pd.NA

        record = row.to_dict()
        record.update({"return": ret, "realizedDate": realized_date, "daysDiff": days_diff})
        results.append(record)
    return pd.DataFrame(results)

if __name__ == "__main__":
    universe = []  # replace with your tickers if desired
    candidates = universe if universe else get_random_mega_caps(20)
    print(f"Mega-cap candidates (listed): {candidates}")

    trades_frames = []
    for t in candidates:
        df_t = fetch_insider_trades(f"issuer.tradingSymbol:{t}", size=50)
        if df_t.empty:
            print(f"No trades for {t}, skipping.")
        else:
            trades_frames.append(df_t)
    if not trades_frames:
        print("No insider trades found; adjust candidates or try again.")
        sys.exit(1)
    df_trades = pd.concat(trades_frames, ignore_index=True, sort=False)

    df_momentum = analyze_trade_momentum(df_trades, days_after=30)
    print(df_momentum)

    out_path = r"C:\Users\james\OneDrive\Desktop\Insider Buys and Sells\insider_momentum.csv"
    df_momentum.to_csv(out_path, index=False)
    print(f"Data saved to {out_path}")