import json
import dotenv
import os
import datetime
import time
import requests
import pandas as pd
import aiohttp
import asyncio
from pathlib import Path

# Responsible for:
# - making API requests to Financial Modeling Prep
# - handling authentication and headers
# - returning raw JSON responses
# - handling request errors and response status checks

dotenv.load_dotenv(Path(__file__).parent.parent / "config.env")
api_key = os.getenv("api_key")
chart_30_min_url = os.getenv("30_min_chart_url")
cash_flow_url = os.getenv("cash_flow_url")
ratio_url = os.getenv("ratio_url")
profile_url = os.getenv("profile_url")
historical_mkt_cap_url = os.getenv("historical_mkt_cap")
balance_sheet_url = os.getenv("balance_sheet_url")


def set_api_key(key: str):
    global api_key
    api_key = key


def build_intervals(start_date: datetime.date = None, end_date: datetime.date = None, num_days: int = 60) -> list:
    """Split a date range into chunks of num_days, returning a list of [start, end] string pairs."""
    try:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
    except Exception as e:
        print(f"Error converting dates: {e}")
        return []
    num_days = pd.Timedelta(days=num_days)
    date_list = []
    next_date = start_date
    while start_date <= end_date:
        next_date = start_date + num_days
        date_list.append([start_date.strftime("%Y-%m-%d"), next_date.strftime("%Y-%m-%d")])
        start_date = start_date + num_days + pd.Timedelta(days=1)
    return date_list


async def get_30_min_chart(ticker: str, start_date: datetime.date | str | None = None, end_date: datetime.date | str | None = None,) -> list:
    """Fetch 30-minute OHLCV chart data for a ticker over a date range, paginated into 60-day intervals."""
    ticker = ticker.upper()
    if start_date is None:
        raise ValueError("Missing start_date. Please provide a start_date to get going in for format: 'yyyy-mm-dd'")
    if end_date is None:
        end_date = datetime.date.today()
    if isinstance(start_date, str):
        start_date = datetime.date.fromisoformat(start_date)
    if isinstance(end_date, str):
        end_date = datetime.date.fromisoformat(end_date)
    all_data = []
    intervals = build_intervals(start_date, end_date, num_days=15)
    async with aiohttp.ClientSession() as session:
        for dates in intervals:
            params = {
                "apikey": api_key,
                "symbol": ticker,
                "from": dates[0],
                "to": dates[1]
            }
            try:
                async with session.get(chart_30_min_url, params=params) as response:
                    if response.status == 503:
                        await asyncio.sleep(30)
                        async with session.get(chart_30_min_url, params=params) as retry_response:
                            if retry_response.status != 200:
                                print(
                                    f"Failed to retrieve data for {ticker} from {dates[0]} to {dates[1]} "
                                    f"after retrying: {retry_response.status}"
                                )
                                continue
                            retry_response.raise_for_status()
                            data = await retry_response.json()
                    else:
                        response.raise_for_status()
                        data = await response.json()
                all_data.extend(data)
            except ValueError as e:
                print(f"JSON decoding error for {ticker} from {dates[0]} to {dates[1]}: {e}")
            except aiohttp.ClientError as e:
                print(f"HTTP error for {ticker} from {dates[0]} to {dates[1]}: {e}")
    return all_data


def get_cash_flow(ticker:str, limit:int=500, period:str="annual") -> json:
    """Fetch cash flow statements for a ticker. Returns parsed JSON or False on failure."""
    ticker = ticker.upper()
    if period not in ["Q1", "Q2", "Q3", "Q4", "FY", "annual", "quarter"]:
        raise ValueError(f"Invalid period: {period}. Must be one of 'Q1', 'Q2', 'Q3', 'Q4', 'FY', 'annual', or 'quarter'.")
    params = {
        "apikey": api_key,
        "symbol": ticker,
        "limit": limit,
        "period": period
    }
    try:
        response = requests.get(cash_flow_url, params=params)
        if response.status_code == 503:
            time.sleep(30)
            response = requests.get(cash_flow_url, params=params)
            if response.status_code != 200:
                print(f"Failed to retrieve cash flow data for {ticker} after retrying: {response.status_code}")
                return False
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving cash flow data for {ticker}: {e}")
        return False

def get_balance_sheet(ticker:str, limit:int=500, period:str="annual") -> json:
    """Fetch balance sheet statements for a ticker. Returns parsed JSON or False on failure."""
    ticker = ticker.upper()
    if period not in ["Q1", "Q2", "Q3", "Q4", "FY", "annual", "quarter"]:
        raise ValueError(f"Invalid period: {period}. Must be one of 'Q1', 'Q2', 'Q3', 'Q4', 'FY', 'annual', or 'quarter'.")
    params = {
        "apikey": api_key,
        "symbol": ticker,
        "limit": limit,
        "period": period
    }
    try:
        response = requests.get(balance_sheet_url, params=params)
        if response.status_code == 503:
            time.sleep(30)
            response = requests.get(balance_sheet_url, params=params)
            if response.status_code != 200:
                print(f"Failed to retrieve balance sheet data for {ticker} after retrying: {response.status_code}")
                return False
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving balance sheet data for {ticker}: {e}")
        return False

def get_ratio_data(ticker:str, limit:int=500, period:str="annual") -> json:
    """Fetch financial ratios (P/E, P/B, etc.) for a ticker. Returns parsed JSON or False on failure."""
    ticker = ticker.upper()
    if period not in ["Q1", "Q2", "Q3", "Q4", "FY", "annual", "quarter"]:
        raise ValueError(f"Invalid period: {period}. Must be one of 'Q1', 'Q2', 'Q3', 'Q4', 'FY', 'annual', or 'quarter'.")
    params = {
        "apikey": api_key,
        "symbol": ticker,
        "limit": limit,
        "period": period
    }
    try:
        response = requests.get(ratio_url, params=params)
        if response.status_code == 503:
            time.sleep(30)
            response = requests.get(ratio_url, params=params)
            if response.status_code != 200:
                print(f"Failed to retrieve ratio data for {ticker} after retrying: {response.status_code}")
                return False
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving ratio data for {ticker}: {e}")
        return False

def get_profile_data(ticker:str) -> json:
    """Fetch company profile data (sector, description, exchange, etc.) for a ticker. Returns parsed JSON or False on failure."""
    ticker = ticker.upper()
    params = {
        "apikey": api_key,
        "symbol": ticker
    }
    try:
        response = requests.get(profile_url, params=params)
        if response.status_code == 503:
            time.sleep(30)
            response = requests.get(profile_url, params=params)
            if response.status_code != 200:
                print(f"Failed to retrieve profile data for {ticker} after retrying: {response.status_code}")
                return False
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving profile data for {ticker}: {e}")
        return False

def get_historical_mkt_cap(ticker: str, limit: int = 500, start_date: datetime.date | str | None = None, end_date: datetime.date | str | None = None) -> json:
    """Fetch historical daily market cap for a ticker. Returns parsed JSON or False on failure."""
    ticker = ticker.upper()
    params = {
        "apikey": api_key,
        "symbol": ticker,
        "limit": limit
    }
    if start_date is not None:
        params["from"] = str(start_date)
    if end_date is not None:
        params["to"] = str(end_date)
    try:
        response = requests.get(historical_mkt_cap_url, params=params)
        if response.status_code == 503:
            time.sleep(30)
            response = requests.get(historical_mkt_cap_url, params=params)
            if response.status_code != 200:
                print(f"Failed to retrieve historical market cap data for {ticker} after retrying: {response.status_code}")
                return False
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving historical market cap data for {ticker}: {e}")
        return False
