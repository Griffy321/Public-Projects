import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent)) # forces Python to go up 2 parents to look for the right thing to import (usualy just goes up 1 level from the current file)
sql_db_path = Path(__file__).parent.parent.joinpath("data/tickers/tickers.db") 

from api import trading212 as t212

connection = sqlite3.connect(sql_db_path)
cursor = connection.cursor()
cursor.execute("DROP TABLE IF EXISTS tickers")
cursor.execute("CREATE TABLE tickers(isin PRIMARY KEY, ticker, type, workingScheduleId, currencyCode, name, shortName, maxOpenQuantity, extendedHours, addedOn)")

data = t212.TradingAccount().fetch_tickers()

deduped = []
isins = []
dupes = []
for dict in data:
    isin = dict.get("isin")
    if isin in isins:
        dupes.append(isin) # need to investigate these, isins should be distinct 
    else:
        isins.append(isin)
        deduped.append(dict)

# setting the primary key makes sure we cannot insert dupes anywhere + we dedupe the data 
cursor.executemany("INSERT INTO tickers VALUES(:isin, :ticker, :type, :workingScheduleId, :currencyCode, :name, :shortName, :maxOpenQuantity,:extendedHours, :addedOn)", deduped) 

connection.commit() # this is needed so the insert stays in the table 
cursor.execute("SELECT * FROM tickers")
query_results = cursor.fetchall()

print(dupes)