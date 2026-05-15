import sqlite3
import sys
from pathlib import Path
from decimal import Decimal
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).parent.parent)) # forces Python to go up 2 parents to look for the right thing to import (usualy just goes up 1 level from the current file)
sql_db_path = Path(__file__).parent.parent.joinpath("data/tickers/tickers.db") 

from api.trading212 import TradingAccount


class TickerDB(TradingAccount):
    def __init__(self, 
                 connection=sqlite3.connect(sql_db_path),
                 cursor = sqlite3.connect(sql_db_path).cursor()
                 ):
        self.connection = connection # db connection
        self.cursor = cursor # cursor connection for querying 

    def create_db(self):
        self.cursor.execute("""
                            CREATE TABLE if not exists tickers (
                                ticker, 
                                isin, 
                                type, 
                                workingScheduleId, 
                                currencyCode, 
                                name, 
                                shortName, 
                                maxOpenQuantity, 
                                extendedHours, 
                                addedOn, 
                                PRIMARY KEY(ticker, isin) 
                            )""") # setting the primary key makes sure we cannot insert dupes 

    def update_ticker_db(self):
        data = self.fetch_tickers()
        self.cursor.execute("""
                            insert into tickers values (
                            :ticker, 
                            :isin, 
                            :type, 
                            :workingScheduleId, 
                            :currencyCode, 
                            :name, 
                            :shortName, 
                            :maxOpenQuantity, 
                            :extendedHours, 
                            :addedOn
                            )
                            """, data)
        self.connection.commit()

    # get_by_ticker(ticker) - return full instrument row for a given ticker string
    def get_by_ticker(self, ticker:str): 
        if ticker is None:
            raise ValueError("Please provide a ticker to be searched")
        query = f"""
                select
                    *
                from
                    tickers
                where
                    upper(ticker) like upper(('{ticker}%'))
                """
        results = self.cursor.execute(query).fetchall()
        return results
    
    # get_by_isin(isin) - return all instruments matching an ISIN (may be >1 if multi-exchange)
    def get_by_isin(self, isin:str): 
        if isin is None:
            raise ValueError("Please provide an isin to be searched")
        query = f"""
                select
                    *
                from
                    tickers
                where
                    upper(shortName) like upper(('{isin}%'))
                """
        results = self.cursor.execute(query).fetchall()
        return results

    # is_tradeable(isin) - return bool, check if a given ISIN exists in the tickers table
    def is_tradeable(self, isin:str):
        if not isin:
            raise ValueError("Please provide an ISIN")
        
        if isin:
            query = f"""
                    select
                        *
                    from
                        tickers
                    where 
                        upper(isin) like upper(('{isin}'))
                    """
            results = self.cursor.execute(query).fetchall()
            if len(results) > 0:
                return True
            else:
                return False    

    # TODO: get_by_currency(currency_code) - return all instruments traded in a given currency e.g. "GBP", "USD"
    def get_by_currency(self, currency_code:str):
        pass

    # TODO: get_extended_hours() - return all instruments where extendedHours is true
    def get_extended_hours(self, extended_hours:bool):
        pass

    # TODO: get_by_type(type) - filter instruments by type e.g. ETF, STOCK
    def get_by_type(self, type:str):
        pass

    # TODO: search_by_name(name) - fuzzy search on the name field, useful for a stock picker UI
    def search_by_name(self, name:str):
        pass

    # TODO: filter_tradeables(isin_list) - given a list of ISINs (e.g. from FMP portfolio data), return which ones are available on T212
    def filter_tradeables(self, isin_list:list):
        pass

    # TODO: get_max_quantity(isin) - return maxOpenQuantity for an instrument, useful before placing a trade
    def get_max_quantity(self, isin:str):
        pass

    def take_pct(self, pct):
        try:
            pct = Decimal(pct)
        except Exception as e:
            print(f"Unable to confert {pct} to data type Decimal")
            return None
        if pct > Decimal(1.0):
            print(f"The size of a single position cannot be over 100%. Please lower it.")
            return None
        
        pct = round(pct, ndigits=6)
        return pct

    def get_candidates(self, ticker:str):
        if not ticker:
            raise ValueError("Please provide either a ticker to search.")

        results = self.get_by_ticker(ticker=ticker)
        return [{"ticker" : r[0], "name" : r[5]} for r in results]
    # NOTE (UI contract): get_candidates is called live as the user types in the
    # "Additional ticker" search box. No changes needed here — shape is correct.

    # TODO (UI contract): add_stocks_to_pie(pie_id: str, selections: dict[str, float])
    # This is the main action behind the "Add to Pie" button. selections is a dict of
    # {ticker_string: weight_as_float} e.g. {"AAPL": 0.60, "MSFT": 0.40}.
    # Weights will always sum to 1.0 — the UI enforces this before calling.
    #
    # Steps to implement:
    #   1. Resolve each ticker string to the format T212 expects in instrumentShares.
    #      Use get_by_ticker(ticker) — row[0] is the T212 ticker (e.g. "AAPL_US_EQ").
    #      Confirm the exact key format against a real get_one_pie() response.
    #   2. Decide merge vs replace (see note on update_pie in trading212.py).
    #      If merging: call get_one_pie(pie_id), extract existing instrumentShares,
    #      update with the new entries, then pass the combined dict to update_pie.
    #   3. Validate weights with take_pct() before building the payload.
    #   4. Call self.update_pie(pie_id, instrument_shares_dict) and return the response.

    # TODO (UI contract): get_pie_list() — see note in trading212.py. Implement there
    # on TradingAccount; it will be inherited here automatically.


# add FastAPI intergration between frount and backend 


results = TickerDB().get_candidates(ticker="aap")
print(results)
print(type(results))