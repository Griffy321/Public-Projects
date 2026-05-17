# Responsible for:
# - calling API client functions
# - selecting relevant parts of API responses
# - validating and normalizing raw JSON into the app's internal stock data model
# - combining data from multiple endpoints into one clean stock record

import asyncio
import pandas as pd
import os
from api import fmp as api
from pathlib import Path
import datetime as dt

parent_path = Path(__file__).parent.parent.joinpath("data/")

price_data_path         = parent_path.joinpath("price_data")
cash_flow_data_path     = parent_path.joinpath("cash_flow_data")
ratio_data_path         = parent_path.joinpath("ratio_data")
profile_data_path       = parent_path.joinpath("profile_data")
mkt_cap_data_path       = parent_path.joinpath("mkt_cap_data")
balance_sheet_data_path = parent_path.joinpath("balance_sheet_data")
folder_paths = [price_data_path, cash_flow_data_path, ratio_data_path, profile_data_path, mkt_cap_data_path, balance_sheet_data_path]

def load_data(filename: str, path: str) -> pd.DataFrame:
    """Load a parquet file into a DataFrame, fetching a delta first if the data is stale."""
    df = pd.read_parquet(f"{path}/{filename}.parquet")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])

    data_type = next(
        (t for t in ("price_data", "cash_flow_data", "balance_sheet_data", "ratio_data", "profile_data", "mkt_cap_data")
         if t in str(path)),
        None
    )
    if data_type:
        try:
            stale = is_stale(df)
        except ValueError:
            stale = True  # no date column (e.g. profile_data) — always refresh
        if stale:
            delta = fetch_delta(filename, df, data_type)
            update_save_files(filename, {data_type: delta})
            df = pd.read_parquet(f"{path}/{filename}.parquet")
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])

    return df

def check_existence(filename:str, path:str) -> bool:
    """Return True if the parquet file for the given filename exists."""
    return os.path.exists(f"{path}/{filename}.parquet")

def to_dataframe(data_list: list) -> pd.DataFrame:
    df = pd.DataFrame(data_list)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df

def to_dataframe_dict(data_dict: dict) -> dict[str, pd.DataFrame]:
    return {key: pd.DataFrame(value) for key, value in data_dict.items() if key.lower() != "ticker"}

def is_stale(df: pd.DataFrame) -> bool:
    """Returns True if the most recent record in the DataFrame is older than 1 trading day."""
    col = next((c for c in df.columns if c.lower() == "date"), None)
    if col is None:
        raise ValueError("DataFrame must contain a 'date' column to check staleness.")
    last_date = pd.to_datetime(df[col]).max()
    return dt.datetime.now() - last_date > dt.timedelta(days=1)

def fetch_delta(ticker: str, df: pd.DataFrame, data_type: str) -> pd.DataFrame:
    """Fetches new records for a ticker since the last date in df. Call after is_stale() returns True."""
    valid_types = ("price_data", "cash_flow_data", "balance_sheet_data", "ratio_data", "profile_data", "mkt_cap_data")
    if data_type not in valid_types:
        raise ValueError(f"Invalid data type. Must be one of: {valid_types}")

    ticker = ticker.strip().upper()

    if data_type in ("price_data", "mkt_cap_data"):
        last_date = pd.to_datetime(df["date"]).max()
        start = (last_date + pd.offsets.BDay(1)).strftime("%Y-%m-%d")
        end = dt.datetime.now().strftime("%Y-%m-%d")

        if data_type == "price_data":
            raw = asyncio.run(api.get_30_min_chart(ticker, start_date=start, end_date=end))
        else:
            raw = api.get_historical_mkt_cap(ticker, start_date=start, end_date=end)
    else:
        # re-fetch full statement history; update_save_files deduplication handles merging
        if data_type == "cash_flow_data":
            raw = api.get_cash_flow(ticker)
        elif data_type == "balance_sheet_data":
            raw = api.get_balance_sheet(ticker)
        elif data_type == "ratio_data":
            raw = api.get_ratio_data(ticker)
        else:
            raw = api.get_profile_data(ticker)

    return to_dataframe(raw)

async def get_company_data(ticker:str, start_date:str, end_date:str) -> dict:
    """Fetch chart, cash flow, ratio, and profile data for a ticker and return as a dict of DataFrames."""
    ticker = ticker.strip().upper()
    chart_data_task = api.get_30_min_chart(ticker, start_date=start_date, end_date=end_date)

    price_data = await chart_data_task
    cash_flow_data = api.get_cash_flow(ticker)
    balance_sheet_data = api.get_balance_sheet(ticker)
    ratio_data = api.get_ratio_data(ticker)
    profile_data = api.get_profile_data(ticker)
    mkt_cap_data = api.get_historical_mkt_cap(ticker, start_date=start_date, end_date=end_date)

    data_dict = {
        "ticker": ticker,
        "price_data": price_data,
        "cash_flow_data": cash_flow_data,
        "balance_sheet_data": balance_sheet_data,
        "ratio_data": ratio_data,
        "profile_data": profile_data,
        "mkt_cap_data": mkt_cap_data
    }
    df_dict = to_dataframe_dict(data_dict=data_dict)
    return df_dict

def update_save_files(ticker:str, df_dict:dict):
    """Save or merge DataFrames in df_dict to their corresponding parquet files.

    For each key in df_dict, finds the matching file path by substring and writes the data.
    If a file already exists, merges with existing data, deduplicates on 'date', and sorts before saving.
    """
    if not df_dict:
        raise ValueError("You must provide a dictionary of dataframes")
    ticker = ticker.strip().upper()
    file_paths = [f"{path}/{ticker}.parquet" for path in folder_paths]

    key_file_dict = {}
    if df_dict is not None:
        for key in df_dict.keys():
            if key == "ticker":
                pass
            for path in file_paths:
                if path.find(key) != -1:
                    key_file_dict[key] = path
                else:
                    continue

    for key, path in key_file_dict.items():
        if not os.path.exists(path):
            df = pd.DataFrame(df_dict[key])
            df.to_parquet(path, index=False)
        else:
            existing_df = pd.read_parquet(path)
            df = pd.DataFrame(df_dict[key])
            combined_df = pd.concat([existing_df, df], ignore_index=True)
            if "date" in combined_df.columns:
                combined_df["date"] = pd.to_datetime(combined_df["date"])
                combined_df = combined_df.drop_duplicates(subset=["date"]).sort_values("date")
            combined_df.to_parquet(path, index=False)
