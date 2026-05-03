import os
import requests
import pandas as pd

# 1) Grab your real key from the environment (set SEC_API_KEY beforehand).
API_KEY = os.getenv("API_KEY", "API_KEY")

# Endpoint URLs
BASE_URL_INSIDER = "https://api.sec-api.io/insider-trading"
BASE_URL_13F = "https://api.sec-api.io/form-13f"
BASE_URL_13F_HOLDINGS = f"{BASE_URL_13F}/holdings"
BASE_URL_13F_COVER = f"{BASE_URL_13F}/cover-pages"
BASE_URL_13D = "https://api.sec-api.io/form-13d-13g"

# Use header-based auth consistently
HEADERS = {"Authorization": API_KEY}


def fetch_insider_trades_enhanced(query: str, size: int = 50) -> pd.DataFrame:
    """
    Fetch insider trades and flatten nested non-derivative and derivative tables,
    extracting key fields for analysis.
    """
    payload = {"query": query, "from": 0, "size": size, "sort": [{"filedAt": {"order": "desc"}}]}
    resp = requests.post(BASE_URL_INSIDER, headers=HEADERS, json=payload)
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        print(f"Error fetching insider trades: {resp.status_code}\n{resp.text}")
        return pd.DataFrame()

    data = resp.json().get("transactions", [])
    records = []

    for grp in data:
        # Shared metadata
        doc_type = grp.get("documentType")
        footnotes_text = "; ".join(fn.get("text", "") for fn in grp.get("footnotes", []) or [])
        remarks = grp.get("remarks")
        rel = grp.get("reportingOwner", {}).get("relationship", {}) or {}
        officer_title = rel.get("officerTitle")
        other_text = rel.get("otherText")

        def extract(tx, category):
            coding = tx.get("coding", {}) or {}
            amounts = tx.get("amounts", {}) or {}
            post = tx.get("postTransactionAmounts", {}) or {}
            return {
                "documentType": doc_type,
                "footnotes": footnotes_text,
                "remarks": remarks,
                "officerTitle": officer_title,
                "otherText": other_text,
                "transactionCategory": category,
                "securityTitle": tx.get("securityTitle"),
                "transactionDate": tx.get("transactionDate"),
                "transactionCode": coding.get("code"),
                "equitySwapInvolved": coding.get("equitySwapInvolved"),
                "shares": amounts.get("shares"),
                "pricePerShare": amounts.get("pricePerShare"),
                "sharesOwnedFollowingTransaction": post.get("sharesOwnedFollowingTransaction"),
            }

        # Non-derivative and derivative
        for tx in grp.get("nonDerivativeTable", {}).get("transactions", []) or []:
            records.append(extract(tx, "nonDerivative"))
        for tx in grp.get("derivativeTable", {}).get("transactions", []) or []:
            records.append(extract(tx, "derivative"))

    df_insider = pd.DataFrame(records)
    if df_insider.empty:
        print("No insider transactions extracted.")
    return df_insider


def fetch_form13f_holdings(query: str, size: int = 50) -> pd.DataFrame:
    """Fetch Form 13F holdings for the given ticker or CIK."""
    payload = {"query": query, "from": 0, "size": size, "sort": [{"periodOfReport": {"order": "desc"}}]}
    resp = requests.post(BASE_URL_13F_HOLDINGS, headers=HEADERS, json=payload)
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        print(f"Error fetching 13F holdings: {resp.status_code}\n{resp.text}")
        return pd.DataFrame()

    items = resp.json().get("data", [])
    records = []
    for item in items:
        meta = {"cik": item.get("cik"), "periodOfReport": item.get("periodOfReport")}
        for h in item.get("holdings", []):
            records.append({**meta, **h})
    return pd.DataFrame(records)


def fetch_form13f_cover(query: str, size: int = 50) -> pd.DataFrame:
    """Fetch Form 13F cover pages for the given ticker or CIK."""
    payload = {"query": query, "from": 0, "size": size, "sort": [{"periodOfReport": {"order": "desc"}}]}
    resp = requests.post(BASE_URL_13F_COVER, headers=HEADERS, json=payload)
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        print(f"Error fetching 13F cover-pages: {resp.status_code}\n{resp.text}")
        return pd.DataFrame()

    return pd.DataFrame(resp.json().get("data", []))


def fetch_form13d13g(query: str, size: int = 50) -> pd.DataFrame:
    """Fetch Form 13D and 13G filings for the given query."""
    payload = {"query": query, "from": 0, "size": size, "sort": [{"filedAt": {"order": "desc"}}]}
    resp = requests.post(BASE_URL_13D, headers=HEADERS, json=payload)
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        print(f"Error fetching 13D/G filings: {resp.status_code}\n{resp.text}")
        return pd.DataFrame()

    return pd.json_normalize(resp.json().get("filings", []))


if __name__ == "__main__":
    if API_KEY == "YOUR_REAL_KEY_HERE":
        raise ValueError("Please set your SEC_API_KEY environment variable to your real API key.")

    # Fetch data with refined queries for TSLA
    df_insider = fetch_insider_trades_enhanced("issuer.tradingSymbol:TSLA", size=5)
    df_13f = fetch_form13f_holdings("holdings.ticker:TSLA", size=1)
    df_13f_cover = fetch_form13f_cover("holdings.ticker:TSLA", size=1)
    df_13d13g = fetch_form13d13g("issuer.tradingSymbol:TSLA")

    # Combine disparate columns into one DataFrame (missing columns become NaN)
    df_all = pd.concat([df_insider, df_13f, df_13f_cover, df_13d13g], ignore_index=True, sort=False)

    # Output to console and CSV
    print(df_all)
    out_path = r"C:\Users\james\OneDrive\Desktop\Insider Buys and Sells\api_test_output.csv"
    df_all.to_csv(out_path, index=False)
    print(f"All data saved to {out_path}")