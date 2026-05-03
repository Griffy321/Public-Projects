import os
import requests
import pandas as pd

# 1) Grab your real key from the environment (set SEC_API_KEY beforehand).
API_KEY = os.getenv("API_KEY", "API_KEY")
BASE_URL = "https://api.sec-api.io/insider-trading"


def fetch_insider_trades_enhanced(query: str, size: int = 50, use_header: bool = True) -> pd.DataFrame:
    """
    Fetch insider trades matching `query` and return a flattened DataFrame
    including transaction code, amounts, equity-swap flag, footnotes/remarks,
    post-transaction holdings, role details, and amendment type.
    """
    payload = {
        "query": query,
        "from": 0,
        "size": size,
        "sort": [{"filedAt": {"order": "desc"}}]
    }

    # Authenticate
    if use_header:
        headers = {"Authorization": API_KEY}
        resp = requests.post(BASE_URL, headers=headers, json=payload)
    else:
        resp = requests.post(f"{BASE_URL}?token={API_KEY}", json=payload)

    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        print(f"HTTP {resp.status_code} error: {e}")
        print("Response body:", resp.text)
        return pd.DataFrame()

    data = resp.json()
    tx_groups = data.get("transactions", [])
    records = []

    for grp in tx_groups:
        # Meta fields
        doc_type = grp.get("documentType")
        footnotes_list = grp.get("footnotes", []) or []
        footnotes_text = "; ".join([fn.get("text", "") for fn in footnotes_list])
        remarks = grp.get("remarks")
        rel = grp.get("reportingOwner", {}).get("relationship", {}) or {}
        officer_title = rel.get("officerTitle")
        other_text = rel.get("otherText")

        # Helper to extract from a transaction entry
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

        # Non-derivative trades
        for tx in grp.get("nonDerivativeTable", {}).get("transactions", []) or []:
            records.append(extract(tx, "nonDerivative"))

        # Derivative trades
        for tx in grp.get("derivativeTable", {}).get("transactions", []) or []:
            records.append(extract(tx, "derivative"))

    df = pd.DataFrame(records)
    if df.empty:
        print("No transactions found or unable to extract nested transaction fields.")
    return df


if __name__ == "__main__":
    # Example: fetch latest Tesla insider trades enriched
    df_enhanced = fetch_insider_trades_enhanced("issuer.tradingSymbol:TSLA", size=5)
    if df_enhanced.empty:
        print("No enhanced records to display.")
    else:
        # Print to console
        print(df_enhanced)
        out_path = r"C:\Users\james\OneDrive\Desktop\Insider Buys and Sells\api_test_output.csv"
        df_enhanced.to_csv(out_path, index=False)
        print(f"Enhanced data saved to {out_path}")