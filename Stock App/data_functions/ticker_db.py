import sqlite3
import sys
from pathlib import Path
from decimal import Decimal
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).parent.parent)) # forces Python to go up 2 parents to look for the right thing to import (usualy just goes up 1 level from the current file)
sql_db_path = Path(__file__).parent.parent.joinpath("data/tickers/tickers.db") 

from api.trading212 import TradingAccount


class TickerDB(TradingAccount):
    def __init__(self):
        super().__init__()
        self.connection = sqlite3.connect(sql_db_path)
        self.cursor = self.connection.cursor()

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
        self.cursor.executemany("""
                            insert or ignore into tickers values (
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
        ticker = ticker.upper()
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
        except Exception:
            print(f"Unable to confert {pct} to data type Decimal")
            return None
        if pct > Decimal(1.0):
            print(f"The size of a single position cannot be over 100%. Please lower it.")
            return None
        
        pct = round(pct, ndigits=6)
        return pct

    def get_pie_list(self):
        return next(self.get_all_pies(), [])

    def get_candidates(self, ticker:str):
        if not ticker:
            raise ValueError("Please provide either a ticker to search.")

        results = self.get_by_ticker(ticker=ticker)
        return [{"ticker" : r[0], "name" : r[5]} for r in results]

    def set_pie_holdings(self, pie_id: str, holdings: dict[str, float]):
        """Replace the full pie composition. holdings is {t212_ticker: weight_as_decimal}."""
        validated = {}
        for ticker, weight in holdings.items():
            v = self.take_pct(weight)
            if v is None:
                raise ValueError(f"Invalid weight {weight} for {ticker}")
            validated[ticker] = float(v)
        return self.update_pie(pie_id, validated)

    def add_stocks_to_pie(self, pie_id: str, selections: dict[str, float]):
        new_shares = {}
        for ticker, weight in selections.items():
            validated = self.take_pct(weight)
            if validated is None:
                raise ValueError(f"Invalid weight {weight} for {ticker}")
            new_shares[ticker] = float(validated)

        current = self.get_one_pie(pie_id)
        # weights live in instruments[].expectedShare, not settings.instrumentShares (that field is null)
        existing = {item["ticker"]: item["expectedShare"] for item in current.get("instruments", [])}
        merged = {**existing, **new_shares}

        return self.update_pie(pie_id, merged, pie_info=current)


