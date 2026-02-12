import pandas as pd
import requests
import datetime
import numpy as np
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import matplotlib.pyplot as plt

apikey = "fpm_api_key" # replace with your FMP API key

def get_120_day_window(start_date:datetime.date, end_date:datetime.date) -> list:
    if type(start_date) == str:
        print("data type error: expected datetime.datetime, got string")
        raise TypeError
    date_list = []
    next_date = start_date
    while start_date < end_date:
        next_date = start_date + datetime.timedelta(days=120)
        date_list.append([start_date.strftime("%Y-%m-%d"), next_date.strftime("%Y-%m-%d")])
        start_date = next_date + datetime.timedelta(days=1)
    return date_list

def get_listed_delisted_tickers(limit: int=10, listed_pct: float=0.6) -> pd.DataFrame:
    """
    Docstring for get_listed_delisted_tickers
    :param limit: Description - Total number of symbols to return
    :type limit: int
    :param listed_pct: Description - The percent of total companies returned that are still listed. 
    E.g. 0.9 means 90% of tickers that get returned should still be listed
    :type listed_pct: float
    """
    if limit > 500:
        print("please request less tickers")
        return ValueError
    if listed_pct > 1:
        print("please specify a valie less than or equel to 1 as the pct of listed tickers to return")
        return ValueError
    # delisted_url = "https://financialmodelingprep.com/stable/delisted-companies/" # Incase i ever want to widen this and use all delisted companies, at the time of writing this FMP only has 45 pages of delisted comapnies
    listed_df = pd.read_csv("C:/Users/james/OneDrive/Desktop/Investigations/Intrinsic Value/spy_current_constituents.csv")
    listed_df = listed_df.sample(frac=1)
    delisted_df = pd.read_csv("C:/Users/james/OneDrive/Desktop/Investigations/Intrinsic Value/spy_removed_constituents.csv")
    delisted_df = delisted_df.sample(frac=1)

    listed_limit = int(round(limit * listed_pct, ndigits=0))
    delisted_limit =  int(round(limit * (1 - listed_pct), ndigits=0))
    listed_df = listed_df["symbol"].iloc[0:listed_limit]
    delisted_df = delisted_df["removedTicker_clean"].iloc[0:delisted_limit]
    df = pd.concat([listed_df, delisted_df])
    return df

def get_4hour_price_hist(ticker, start_date, end_date, session=requests.Session()):
    """
    Docstring for get_intrinsic_val_hist
    :param ticker: Description - the ticker you want to fetch data for 
    :param start_date: Description - when you want the price history to start, this typicaly would be the IPO date 
    :param end_date: Description - when you want the price history to go up until
    :param session: Description - requests.Session for faster API calls
    """
    folder = "C:/Users/james/OneDrive/Desktop/Investigations - Data/4h price data/"
    url = "https://financialmodelingprep.com/stable/historical-chart/4hour"
    dfs = []
    periods = get_120_day_window(start_date, end_date)
    for period in periods:
        params = {
        "apikey" : apikey,
        "symbol" : ticker,
        "from" : period[0],
        "to" : period[1]
        }
        print(f"working on {ticker} for periods {period[0]} to {period[1]}")
        request = session.get(url=url, params=params)
        if request.status_code != 200:
            print(f"{request.status_code} error when getting data for ticker")
            continue
        data = request.json()
        data = pd.DataFrame(data)
        if data.empty:
            print(f"no historical data for {ticker} - skipping")
            continue
        dfs.append(data)
    if not dfs:
        print(f"no data collected for {ticker} - skipping")
        return None
    price_history = pd.concat(dfs, ignore_index=True)
    price_history.to_csv(f"{folder}{ticker}_4hour_chart.csv", index=False, encoding="utf-8", mode="w")
    print(f"price history df saved to {folder}{ticker}_4hour_chart.csv")
    return price_history

def get_intrinsic_val(ticker):
    url = "https://financialmodelingprep.com/stable/earnings"
    params = {
        "apikey" : apikey,
        "symbol" : ticker,
        "limit" : 500 # just to get all earnings history 
    }
    data = requests.get(url=url, params=params)
    if data.status_code != 200:
        print(f"no earnings data for {ticker} - skipping")
        return None
    print(f"Working on {ticker} earnings data")
    data = data.json()
    data = pd.DataFrame(data)
    if data.empty:
        print(f"no data collected for {ticker} - skipping")
        return None
    # Calculations for 6 year EPS growth
    eps_data = data[["symbol", "date", "epsActual"]].dropna(axis=0)
    eps_data["date"] = pd.to_datetime(eps_data["date"], format="%Y-%m-%d")
    eps_data = eps_data.sort_values(by="date", ascending=True)
    years = 6
    quarters = years * 4
    eps_data["epsTTM"] = eps_data["epsActual"].rolling(4, min_periods=4).sum() # To extrapolate the quarterly EPS out to Annual EPS
    past = eps_data["epsTTM"].shift(quarters)
    curr = eps_data["epsTTM"]
    valid = (curr > 0) & (past > 0) # Handle zero/negative EPS safely (CAGR is not well-defined if either <= 0)
    eps_data["6yGrowth"] = np.where(valid, (curr / past) ** (1 / years) - 1, np.nan)
    if eps_data.empty:
        print(f"Dataframe is empty after calculating 6 year growth for {ticker} - skipping")
        return None
    # getting Y - the current yield (%) on high-grade corporate bonds
    aaa_bond_df = pd.read_csv("C:/Users/james/OneDrive/Desktop/Investigations/Intrinsic Value/AAA.csv")
    aaa_bond_df["observation_date"] = pd.to_datetime(aaa_bond_df["observation_date"], format="%d/%m/%Y")
    # Joining the 2 dataframes 
    eps_bond_df = pd.merge_asof(eps_data.sort_values("date"), aaa_bond_df.sort_values("observation_date"), left_on="date", right_on="observation_date", direction="backward")

    # Cleaning dataframes, dropping unneeded columns and de-duping
    eps_bond_df = eps_bond_df.dropna().drop(columns=["epsActual", "observation_date"])
    eps_bond_df = eps_bond_df.drop_duplicates(subset="date", keep="last")
    if eps_bond_df.empty:
        print(f"Dataframe is empty after merging and clearning data for {ticker} - skipping")
        return None
    # Graham's formula: Intrinsic Value = (EPS * (8.5 + 2 * Growth Rate) * 4.4) / Y
    # I chose to replace the 4.4 with 5.63 since it is the average yeild of AAA bonds over the last 100 years 
    eps_bond_df["intrinsic_val"] = (eps_bond_df["epsTTM"] * (8.5 + 2 * eps_bond_df["6yGrowth"]) * 5.63) / eps_bond_df["AAA"] 
    return eps_bond_df


# Building a number of dataframes for stocks to backtest on 
tickers = get_listed_delisted_tickers(limit=20, listed_pct=0.5) 
for ticker in tickers:
    price_df = get_4hour_price_hist(ticker, start_date=datetime.datetime(2000, 1, 1).date(), end_date=datetime.datetime.today().date())
    if price_df is None or price_df.empty:
        print(f"no price data for {ticker}, moving on")
        continue
    price_df["date"] = pd.to_datetime(price_df["date"], format="%Y-%m-%d %H:%M:%S")
    intrinsic_val_df = get_intrinsic_val(ticker)
    if intrinsic_val_df is None or intrinsic_val_df.empty:
        print(f"no intrinsic value data for {ticker}, moving on") 
        continue
    intrinsic_val_df["date"] = pd.to_datetime(intrinsic_val_df["date"], format="%Y-%m-%d")
    joined_df = pd.merge_asof(price_df.sort_values("date"), intrinsic_val_df.sort_values("date"), left_on="date", right_on="date", direction="backward")
    if joined_df.empty:
        print(f"no data for {ticker}, moving on")
        continue
    folder = "C:/Users/james/OneDrive/Desktop/Investigations - Data/intrinsic data/"
    joined_df.to_csv(f"{folder}{ticker}_joined_data.csv", index=False, encoding="utf-8", mode="w")


# Building a class to hold the backtesting functions
class backtest:
    """
    Docstring for backtest
    Multi-asset intrinsic-value backtest engine (folder-based).
    """
    def __init__(self, df=None, initial_capital: float = 10000.0):
        self.df = df  
        self.initial_capital = float(initial_capital)
        self.cash = float(initial_capital)
        self.trades: List[Tuple] = []

    def _load_folder_data(self, folder: str) -> Dict[str, pd.DataFrame]:
        """
        Loads all CSVs in `folder` into a dict {symbol: df}, cleaning and sorting ascending by date.
        """
        symbol_dataframes: Dict[str, pd.DataFrame] = {}

        for filename in sorted(os.listdir(folder)):  
            filepath = os.path.join(folder, filename)
            if not os.path.isfile(filepath):
                continue
            if not filename.lower().endswith(".csv"):
                continue

            print(f"reading {filename}")
            raw_df = pd.read_csv(filepath)

            required_columns = {"date", "symbol", "close", "intrinsic_val"}
            missing_columns = required_columns - set(raw_df.columns)
            if missing_columns:
                raise ValueError(f"{filename} missing columns: {missing_columns}")

            df = raw_df[["date", "symbol", "close", "intrinsic_val"]].copy()

            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df["intrinsic_val"] = pd.to_numeric(df["intrinsic_val"], errors="coerce")
            df = df.dropna(subset=["date", "symbol", "close", "intrinsic_val"])

            # If a file contains multiple symbols split them
            for symbol, group_df in df.groupby("symbol", sort=False):
                group_df = group_df.drop_duplicates(subset=["date"], keep="last")
                group_df = group_df.sort_values("date", ascending=True).reset_index(drop=True)

                if symbol in symbol_dataframes:
                    combined_df = pd.concat([symbol_dataframes[symbol], group_df], ignore_index=True)
                    combined_df = combined_df.drop_duplicates(subset=["date"], keep="last")
                    combined_df = combined_df.sort_values("date", ascending=True).reset_index(drop=True)
                    symbol_dataframes[symbol] = combined_df
                else:
                    symbol_dataframes[symbol] = group_df

        if not symbol_dataframes:
            raise ValueError(f"No CSV data found in folder: {folder}")

        return symbol_dataframes

    @staticmethod
    def _build_global_timeline(symbol_dataframes: Dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
        """
        Union of all timestamps across all symbols, sorted ascending.
        """
        all_timestamps = pd.Index([])
        for symbol_df in symbol_dataframes.values():
            all_timestamps = all_timestamps.union(pd.Index(symbol_df["date"].values))
        return pd.DatetimeIndex(all_timestamps).sort_values()

    def trade_multiple(
        self,
        folder: str = "C:/Users/james/OneDrive/Desktop/Investigations - Data/intrinsic data/",
        buy_multiple: float = 1.5,
        sell_multiple: float = 3.0,
        execute_next_bar: bool = True,
    ) -> pd.DataFrame:
        """
        Runs a multi-asset backtest across all CSVs in a folder and returns a trades dataframe.

        Execution model:
        - If execute_next_bar=True:
            - Generate signals using information at timestamp t_signal
            - Execute trades at the next global timestamp t_execute
        """

        # Reset run state (prevents cash/positions leaking between runs)
        self.cash = float(self.initial_capital)
        self.trades = []
        value_at_time = []

        symbol_dataframes = self._load_folder_data(folder)
        global_timeline = self._build_global_timeline(symbol_dataframes)
        
        symbol_timestamp_lookup: Dict[str, Dict[pd.Timestamp, Tuple[float, float]]] = {} # {symbol : {timestamp : (close_price, intrinsic_value)}}
        for symbol, symbol_df in symbol_dataframes.items():
            timestamp_dict: Dict[pd.Timestamp, Tuple[float, float]] = {}
            for timestamp, close_price, intrinsic_value in zip(symbol_df["date"], symbol_df["close"], symbol_df["intrinsic_val"]):
                timestamp_dict[pd.Timestamp(timestamp)] = (float(close_price), float(intrinsic_value))
            symbol_timestamp_lookup[symbol] = timestamp_dict
        
        open_positions: Dict[str, List[float]] = {} # {symbol : [shares_held, entry_price]}
        last_known_close_price: Dict[str, float] = {}
        last_known_intrinsic_value: Dict[str, float] = {}

        def calculate_portfolio_value() -> float:
            positions_value = 0.0
            for symbol, (shares_held, _entry_price_unused) in open_positions.items():
                close_price = last_known_close_price.get(symbol)
                if close_price is None:
                    continue
                positions_value += float(shares_held) * float(close_price)
            return float(self.cash) + float(positions_value)

        def get_execution_timestamp(signal_time_index: int) -> Optional[pd.Timestamp]:
            """
            Returns the timestamp at which we execute trades.
            - If execute_next_bar=False: execute on the same timestamp
            - If execute_next_bar=True: execute on the next timestamp in the global timeline
            """
            if not execute_next_bar:
                return global_timeline[signal_time_index]
            if signal_time_index + 1 >= len(global_timeline):
                return None
            return global_timeline[signal_time_index + 1]

        # loop through time 
        for signal_time_index, signal_timestamp in enumerate(global_timeline):
            # Update last-known prices/intrinsic values for any symbols that have a bar at this timestamp
            for symbol in symbol_timestamp_lookup.keys():
                bar_data = symbol_timestamp_lookup[symbol].get(signal_timestamp)
                if bar_data is not None:
                    close_price, intrinsic_value = bar_data
                    last_known_close_price[symbol] = close_price
                    last_known_intrinsic_value[symbol] = intrinsic_value

            execution_timestamp = get_execution_timestamp(signal_time_index)
            if execution_timestamp is None:
                break  # can't execute beyond the last bar if using next-bar execution

            # update value of portfolio at signal time (before executing trades)
            portfolio_value = calculate_portfolio_value()
            value_at_time.append((signal_timestamp, portfolio_value))

            # sell first
            symbols_to_close: List[str] = []

            for symbol in list(open_positions.keys()):
                close_price = last_known_close_price.get(symbol)
                intrinsic_value = last_known_intrinsic_value.get(symbol)
                if close_price is None or intrinsic_value is None:
                    continue

                sell_threshold_price = intrinsic_value * sell_multiple

                if close_price > sell_threshold_price:
                    shares_to_sell = int(open_positions[symbol][0])
                    if shares_to_sell > 0:
                        execution_price = close_price 
                        self.cash += shares_to_sell * execution_price

                        self.trades.append(
                            (execution_timestamp, symbol, "SELL", shares_to_sell, execution_price, self.cash, intrinsic_value, None, sell_threshold_price,))
                    symbols_to_close.append(symbol)

            for symbol in symbols_to_close:
                open_positions.pop(symbol, None)

            # buy pass
            buy_candidates: List[Tuple[str, float, float, float]] = []
            # (symbol, close_price, intrinsic_value, buy_threshold_price)

            for symbol in symbol_timestamp_lookup.keys():
                if symbol in open_positions:
                    continue

                close_price = last_known_close_price.get(symbol)
                intrinsic_value = last_known_intrinsic_value.get(symbol)
                if close_price is None or intrinsic_value is None:
                    continue

                buy_threshold_price = intrinsic_value * buy_multiple

                if close_price < buy_threshold_price:
                    buy_candidates.append((symbol, close_price, intrinsic_value, buy_threshold_price))

            # Deterministic ranking: strongest discount first (close_price / buy_threshold_price lowest)
            buy_candidates.sort(key=lambda item: (item[1] / item[3], item[0]))

            for (candidate_symbol, candidate_close_price, candidate_intrinsic_value, buy_threshold_price) in buy_candidates:
                number_of_positions_after_buy = len(open_positions) + 1
                total_portfolio_value = calculate_portfolio_value()
                target_dollar_allocation = total_portfolio_value / float(number_of_positions_after_buy)

                # if i can't value held positions (missing last price) skip 
                missing_prices_for_held = [s for s in open_positions if s not in last_known_close_price]
                if missing_prices_for_held:
                    continue

                # If not enough cash, trim existing positions proportionally to raise cash
                if self.cash < target_dollar_allocation and len(open_positions) > 0:
                    cash_shortfall = target_dollar_allocation - self.cash
                    cash_to_raise_per_position = cash_shortfall / float(len(open_positions))

                    for held_symbol in list(open_positions.keys()):
                        held_close_price = last_known_close_price.get(held_symbol)
                        if held_close_price is None:
                            continue

                        shares_held = open_positions[held_symbol][0]
                        if shares_held <= 1:
                            # add sell before pop to reclaim any cash from small positions
                            self.trades.append(
                                (execution_timestamp, held_symbol, "SELL", shares_held, held_close_price, self.cash, last_known_intrinsic_value.get(held_symbol), "TRIM-ZERO", None,))
                            self.cash += shares_held * held_close_price
                            open_positions.pop(held_symbol, None) 
                            continue

                        shares_held = int(open_positions[held_symbol][0]) # now we can continue with the cash raise logic for positions that have more than 1 share

                        shares_to_sell = int(cash_to_raise_per_position // held_close_price)
                        shares_to_sell = min(shares_to_sell, shares_held) # bounded

                        if shares_to_sell > 0:
                            self.cash += shares_to_sell * held_close_price
                            open_positions[held_symbol][0] -= shares_to_sell

                            self.trades.append(
                                (execution_timestamp, held_symbol, "SELL", shares_to_sell, held_close_price, self.cash, last_known_intrinsic_value.get(held_symbol), "TRIM", None,))

                            # Remove positions that become zero-share
                            if int(open_positions[held_symbol][0]) <= 0:
                                open_positions.pop(held_symbol, None)

                # Size buy to target allocation
                buy_budget = min(target_dollar_allocation, self.cash)
                shares_to_buy = int(buy_budget // candidate_close_price)

                if shares_to_buy > 0:
                    execution_price = candidate_close_price 
                    total_cost = shares_to_buy * execution_price
                    self.cash -= total_cost

                    open_positions[candidate_symbol] = [float(shares_to_buy), float(execution_price)]

                    self.trades.append(
                        (execution_timestamp, candidate_symbol, "BUY", shares_to_buy, execution_price, self.cash, candidate_intrinsic_value, None, buy_threshold_price,))

        trades_df = pd.DataFrame(
            self.trades,
            columns=["date","symbol","action","shares","price","cash_after_trade","intrinsic_val","reason","threshold",],
        ).sort_values("date", ascending=True).reset_index(drop=True)
        value_at_time_df = pd.DataFrame(value_at_time, columns=["date", "portfolio_value"])

        return trades_df, value_at_time_df

trade_multiple_instance = backtest(None)
trades_df, value_at_time_df = trade_multiple_instance.trade_multiple(folder="C:/Users/james/OneDrive/Desktop/Investigations - Data/intrinsic data/")

plt.plot(value_at_time_df["date"], value_at_time_df["portfolio_value"])
plt.xlabel("Date")
plt.ylabel("Portfolio Value")
plt.title("Portfolio Value Over Time")
plt.show()
