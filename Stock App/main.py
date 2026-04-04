import pandas as pd
import data_fetcher
import api_client as api
import asyncio
from datetime import datetime

# Responsibilities:
# accept ticker input
# trigger the data fetch and analysis pipeline
# display results in the terminal

def take_ticker_input():
    return input("Enter the stock ticker: ").upper()

def take_date_input():
    start = input("Enter the date you want the chart to start from (yyyy-mm-dd) (default - 2026-01-01): ")
    if len(start) == 0:
        start = "2026-01-01"
    print(start)
    end = input("Enter the date you want the chart to end at (yyyy-mm-dd) (default - today): ")
    if len(end) == 0:
        end = datetime.today().date().strftime(format="%Y-%m-%d")
    return start, end 

if __name__ == "__main__":
    while True:
        ticker = take_ticker_input()
        if ticker.lower() == 'exit':
            print("Exiting the program.")
            break
        start, end  = take_date_input()
        try:
            company_data = asyncio.run(data_fetcher.get_company_data(ticker, start_date=start, end_date=end))
            data_fetcher.update_save_files(ticker, df_dict=company_data)
            print(f"Data for {ticker}:")
            print("Price Data")
            print(company_data["price_data"])
            print("Cash Flow Data:")
            print(company_data["cash_flow_data"])
            print("Ratio Data:")
            print(company_data["ratio_data"])
            print("Profile Data")
            print(company_data["profile_data"])
        except Exception as error:
            print(f"An error occurred while fetching data for {ticker}: {error}")
