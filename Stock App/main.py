import pandas as pd
from data_functions import data_fetcher
import asyncio
from datetime import datetime
from metrics import Metrics

# Responsibilities:
# accept ticker input
# trigger the data fetch and analysis pipeline
# display results in the terminal

def take_ticker_input():
    return input("Enter the stock ticker: ").upper()

def take_date_input():
    start = input("Enter the date you want the chart to start from (yyyy-mm-dd) (default - 2026-01-01): ")
    if len(start) == 0:
        start = "2025-01-01"
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
            print(f"Fetched all data for {ticker}")
        except Exception as error:
            print(f"An error occurred while fetching data for {ticker}: {error}")

        metrics = Metrics(ticker=ticker)
        print(f"Created class instance for {ticker}")
        try:
            mega_df = metrics.calculate_all()
            print(f"Calculated all metrics for {ticker}")
            print(mega_df.columns)
        except Exception as e:
            print(f"Got the following error: {e}")
        

        