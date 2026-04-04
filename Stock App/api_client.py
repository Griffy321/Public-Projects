# I could use some form of class here not not super needed 
import json
from dotenv import load_dotenv
import os
import datetime
import time
import data_fetcher
import requests

import aiohttp # for async functions and making API requests
import asyncio # for async functions and making API requests

# Responsible for:
# - making API requests
# - handling authentication and headers
# - returning raw JSON responses
# - handling request errors and response status checks

# This file should know about the external provider format.

load_dotenv("config.env")
api_key = os.getenv("api_key")
chart_30_min_url = os.getenv("30_min_chart_url")
cash_flow_url = os.getenv("cash_flow_url")
ratio_url = os.getenv("ratio_url")
profile_url = os.getenv("profile_url")


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
    intervals = data_fetcher.build_intervals(start_date, end_date, num_days=15)
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

# print(asyncio.run(get_30_min_chart("AAPL", start_date="2026-01-01", end_date="2026-02-01")))

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
            time.sleep(30) # wait for 30 seconds before retrying
            response = requests.get(cash_flow_url, params=params) # retry the request
            if response.status_code != 200:
                print(f"Failed to retrieve cash flow data for {ticker} after retrying: {response.status_code}")
                return False
        response.raise_for_status()
        data = response.json() 
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving cash flow data for {ticker}: {e}")
        return False
    
# print(type(get_cash_flow("AAPL", limit=4, period="annual")))

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
            time.sleep(30) # wait for 30 seconds before retrying
            response = requests.get(ratio_url, params=params) # retry the request
            if response.status_code != 200:
                print(f"Failed to retrieve ratio data for {ticker} after retrying: {response.status_code}")
                return False
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving ratio data for {ticker}: {e}")
        return False

# print(type(get_ratio_data("AAPL", limit=4, period="annual")))

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
            time.sleep(30) # wait for 30 seconds before retrying
            response = requests.get(profile_url, params=params) # retry the request
            if response.status_code != 200:
                print(f"Failed to retrieve profile data for {ticker} after retrying: {response.status_code}")
                return False
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving profile data for {ticker}: {e}")
        return False

# print(type(get_profile_data("AAPL")))