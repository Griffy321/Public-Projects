# Responsible for:
# - calculating financial and valuation metrics from normalized stock data
# - handling divide-by-zero and missing-value cases safely
# - returning computed metric results in a clean format

import pandas as pd
import os
import data_fetcher
from datetime import datetime as dt
from datetime import timedelta as td


class Metrics:
    def __init__(self, ticker:str):
        self.ticker = ticker.upper()

    def mega_df(self) -> pd.DataFrame: 
        ticker = self.ticker
        paths = {
                "price"     : f"C:/Users/james/OneDrive/Desktop/Public-Projects/Stock App/data/price_data/{ticker}.parquet",
                "cash_flow" : f"C:/Users/james/OneDrive/Desktop/Public-Projects/Stock App/data/cash_flow_data/{ticker}.parquet",
                # "ratio"     : f"C:/Users/james/OneDrive/Desktop/Public-Projects/Stock App/data/ratio_data/{ticker}.parquet"
                }
        for path in paths.items():
            print(path[1])
            exists = os.path.exists(path[1])
            if exists is True:
                continue
            else:
                print(f"The file with the following path does not exist: {path[1]}. Building the dataframes")
                start = (dt.today().date() - td(days=90)).strftime(format="%Y-%m-%d")
                print(start)
                end = dt.today().date().strftime(format="%Y-%m-%d")
                print(end)
                data_fetcher.get_company_data(ticker=ticker, start_date=start, end_date=end)

        # Joining cash flow data 
        price = pd.read_parquet(paths["price"])
        price["date"] = pd.to_datetime(price["date"], errors="coerce")
        cash = pd.read_parquet(paths["cash_flow"])
        cash["acceptedDate"] = pd.to_datetime(cash["acceptedDate"], errors="coerce")
        cash = cash[['symbol', 'acceptedDate','netIncome',
       'depreciationAndAmortization', 'deferredIncomeTax',
       'stockBasedCompensation', 'changeInWorkingCapital',
       'accountsReceivables', 'inventory', 'accountsPayables',
       'otherWorkingCapital', 'otherNonCashItems',
       'netCashProvidedByOperatingActivities',
       'investmentsInPropertyPlantAndEquipment', 'acquisitionsNet',
       'purchasesOfInvestments', 'salesMaturitiesOfInvestments',
       'otherInvestingActivities', 'netCashProvidedByInvestingActivities',
       'netDebtIssuance', 'longTermNetDebtIssuance',
       'shortTermNetDebtIssuance', 'netStockIssuance',
       'netCommonStockIssuance', 'commonStockIssuance',
       'commonStockRepurchased', 'netPreferredStockIssuance',
       'netDividendsPaid', 'commonDividendsPaid', 'preferredDividendsPaid',
       'otherFinancingActivities', 'netCashProvidedByFinancingActivities',
       'effectOfForexChangesOnCash', 'netChangeInCash', 'cashAtEndOfPeriod',
       'cashAtBeginningOfPeriod', 'operatingCashFlow', 'capitalExpenditure',
       'freeCashFlow', 'incomeTaxesPaid', 'interestPaid']]
        price_cash = pd.merge_asof(price, cash, left_on="date", right_on="acceptedDate", direction='backward').sort_values(by="date", ascending=False)



    # # Valuation Dynamics
    # def pe_ratio(self, df):
    #     pass

    # # Earnings Quality
    # def cash_conversion_of_earnings(self, df): # operating cash flow / net income; persistently <1 is a red flag
    #     pass

    # # Capital Allocation Efficiency
    # def rnd_yield (self, df): # revenue growth per dollar of R&D spend, lagged 2-3 yea_s
    #     pass

    # # Operational Drift
    # def gross_margin_durability(self, df): # rolling standard deviation of gross margins (stability is often undervalued)
    #     pass

    # # Balance Sheet Dynamics
    # def net_cash_pct_market_cap(self, df): # especially interesting for small caps, shows hidden value

    # # Market Structure
    # def institutional_ownership_drift(self, df): # umulative insider buy/sell ratio over rolling 12 months
    #     pass

cls = Metrics("AAPL")
print(cls.mega_df())