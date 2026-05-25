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
        results = self.cursor.execute(
            "SELECT * FROM tickers WHERE upper(isin) LIKE upper(?)", (f"{isin}%",)
        ).fetchall()
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

    def get_by_currency(self, currency_code:str):
        if not currency_code:
            raise ValueError("Please provide a currency code")
        return self.cursor.execute(
            "SELECT * FROM tickers WHERE upper(currencyCode) = upper(?)", (currency_code,)
        ).fetchall()

    def get_extended_hours(self, extended_hours:bool = True):
        return self.cursor.execute(
            "SELECT * FROM tickers WHERE extendedHours = ?", (1 if extended_hours else 0,)
        ).fetchall()

    def get_by_type(self, type:str):
        if not type:
            raise ValueError("Please provide an instrument type e.g. STOCK, ETF")
        return self.cursor.execute(
            "SELECT * FROM tickers WHERE upper(type) = upper(?)", (type,)
        ).fetchall()

    def search_by_name(self, name:str):
        if not name:
            raise ValueError("Please provide a name to search")
        return self.cursor.execute(
            "SELECT * FROM tickers WHERE upper(name) LIKE upper(?)", (f"%{name}%",)
        ).fetchall()

    def filter_tradeables(self, isin_list:list):
        if not isin_list:
            return []
        placeholders = ",".join("?" * len(isin_list))
        rows = self.cursor.execute(
            f"SELECT isin FROM tickers WHERE isin IN ({placeholders})", isin_list
        ).fetchall()
        return [r[0] for r in rows]

    def get_max_quantity(self, isin:str):
        if not isin:
            raise ValueError("Please provide an ISIN")
        row = self.cursor.execute(
            "SELECT maxOpenQuantity FROM tickers WHERE upper(isin) = upper(?)", (isin,)
        ).fetchone()
        return row[0] if row else None

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
    def add_stocks_to_pie(self, pie_id:str, selections:dict[str, float]):
        pass

    # TODO (UI contract): get_pie_list() — see note in trading212.py. Implement there
    # on TradingAccount; it will be inherited here automatically.
    def get_pie_list():
        pass


# add FastAPI intergration between frount and backend 


# results = TickerDB().get_candidates(ticker="aap")
# print(results)
# print(type(results))