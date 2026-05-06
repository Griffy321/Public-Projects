import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent)) # forces Python to go up 2 parents to look for the right thing to import (usualy just goes up 1 level from the current file)
from api import trading212 as t212

sql_db_path = Path(__file__).parent.parent.joinpath("data/tickers/tickers.db") 

connection = sqlite3.connect(sql_db_path)
cursor = connection.cursor()
cursor.execute("CREATE TABLE tickers(ticker, type, workingScheduleId, isin, currencyCode, name, shortName, maxOpenQuantity, extendedHours, addedOn)")

