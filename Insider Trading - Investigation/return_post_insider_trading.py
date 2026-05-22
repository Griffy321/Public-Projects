import os
import requests
import sys
import pandas as pd
import yfinance as yf
import random

# 1) Grab your real key from the environment (set SEC_API_KEY beforehand).
API_KEY = os.getenv("", "")
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
    Fetch insider Form 4 trades for a given Lucene query, returning empty DataFrame on errors.
    """
    size = min(size, 50)
    payload = {"query": query, "from": 0, "size": size, "sort": [{"filedAt": {"order": "desc"}}]}
    try:
        resp = requests.post(BASE_URL, headers=HEADERS, json=payload)
        resp.raise_for_status()
    except Exception as e:
        print(f"Error fetching insider trades for '{query}': {e}\n{getattr(resp, 'text', '')}")
        return pd.DataFrame()

    data = resp.json().get("transactions", [])
    records = []
    for grp in data:
        symbol = grp.get("issuer", {}).get("tradingSymbol") or query.split(':')[-1]
        for table in ("nonDerivativeTable", "derivativeTable"):
            for tx in grp.get(table, {}).get("transactions", []) or []:
                code = tx.get("coding", {}).get("code")
                rec = {
                    "ticker": symbol,
                    "transactionDate": tx.get("transactionDate"),
                    "transactionCode": code,
                    "transactionDesc": TRANSACTION_CODE_MEANINGS.get(code, "Unknown"),
                    "shares": tx.get("amounts", {}).get("shares"),
                    "pricePerShare": tx.get("amounts", {}).get("pricePerShare"),
                    "officerTitle": grp.get("reportingOwner", {}).get("relationship", {}).get("officerTitle"),
                }
                records.append(rec)
    return pd.DataFrame(records)


def get_random_small_caps(sample_size: int = 2) -> list:
    default_universe = [
        "AAXN", "CZR", "CRMT", "GLBE", "HZN", "IDEX", "LLEX", "MNST", "NWSA", "OTEX",
        "PNRG", "QDEL", "RGEN", "SAIC", "TALO", "UBSI", "VCRA", "WOR", "XYL", "ZION"
    ]
    return random.sample(default_universe, k=sample_size)


def is_listed(ticker: str) -> bool:
    try:
        info = yf.Ticker(ticker).info
        return info.get("regularMarketPrice") is not None
    except Exception:
        return False


def analyze_trade_momentum(df: pd.DataFrame, hours_after: int = 48) -> pd.DataFrame:
    if df.empty:
        print("No trades to analyze.")
        return df
    results = []
    df["transactionDate"] = pd.to_datetime(df["transactionDate"])
    for _, row in df.iterrows():
        tkr = row["ticker"]
        trade_dt = row["transactionDate"]
        if trade_dt.tzinfo is not None:
            trade_dt = trade_dt.tz_convert(None).tz_localize(None)
        end_dt = trade_dt + pd.Timedelta(hours=hours_after)
        try:
            hist = yf.Ticker(tkr).history(start=trade_dt, end=end_dt, interval="1h")
            closes = hist["Close"]
        except Exception as e:
            print(f"Error fetching intraday history for {tkr}: {e}")
            closes = pd.Series()
        if not closes.empty:
            initial = closes.iloc[0]
            later = closes.iloc[-1]
            ret = (later - initial) / initial
            realized_ts = closes.index[-1]
            if realized_ts.tzinfo is not None:
                realized_ts = realized_ts.tz_convert(None).tz_localize(None)
            hours_diff = (realized_ts.to_pydatetime() - trade_dt.to_pydatetime()).total_seconds() / 3600.0
            realized_date = realized_ts
        else:
            ret = pd.NA
            realized_date = pd.NaT
            hours_diff = pd.NA
        res = row.to_dict()
        res.update({"return": ret, "realizedDate": realized_date, "hoursDiff": hours_diff})
        results.append(res)
    return pd.DataFrame(results)


if __name__ == "__main__":
    universe = []
    selected = universe[:2] if universe else get_random_small_caps(2)
    listed = [t for t in selected if is_listed(t)]
    if not listed:
        print("No listed small-cap candidates found; please adjust universe or sample list.")
        sys.exit(1)
    print(f"Small-cap candidates (listed): {listed}")
    trades_list = []
    for t in listed:
        df_t = fetch_insider_trades(f"issuer.tradingSymbol:{t}", size=50)
        if df_t.empty:
            print(f"No trades for {t}, skipping.")
        else:
            trades_list.append(df_t)
    if not trades_list:
        print("No insider trades found for candidates.")
        sys.exit(1)
    df_trades = pd.concat(trades_list, ignore_index=True, sort=False)
    df_momentum = analyze_trade_momentum(df_trades, hours_after=48)
    print(df_momentum)
    out_path = r"C:\Users\james\OneDrive\Desktop\Insider Buys and Sells\insider_momentum.csv"
    df_momentum.to_csv(out_path, index=False)
    print(f"Data saved to {out_path}")