# Responsible for:
# - calculating financial and valuation metrics from normalized stock data
# - handling divide-by-zero and missing-value cases safely
# - returning computed metric results in a clean format 

import pandas as pd
import os
from data_functions import data_fetcher
from datetime import datetime as dt
from datetime import timedelta as td


class Metrics:
    def __init__(self, ticker:str):
        self.ticker = ticker.upper()

    def mega_df(self) -> pd.DataFrame: 
        ticker = self.ticker
        paths = {
                "price"         : f"C:/Users/james/OneDrive/Desktop/Public-Projects/Stock App/data/price_data/{ticker}.parquet",
                "cash_flow"     : f"C:/Users/james/OneDrive/Desktop/Public-Projects/Stock App/data/cash_flow_data/{ticker}.parquet",
                "mkt_cap"       : f"C:/Users/james/OneDrive/Desktop/Public-Projects/Stock App/data/mkt_cap_data/{ticker}.parquet",
                "balance_sheet" : f"C:/Users/james/OneDrive/Desktop/Public-Projects/Stock App/data/balance_sheet_data/{ticker}.parquet"
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
        price = price.sort_values("date")
        cash = pd.read_parquet(paths["cash_flow"])
        cash["acceptedDate"] = pd.to_datetime(cash["acceptedDate"], errors="coerce")
        cash = cash.sort_values("acceptedDate")
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
        price_cash = pd.merge_asof(price, cash, left_on="date", right_on="acceptedDate", direction='backward').sort_values(by="date", ascending=True)

        # Joining market cap
        mkt = pd.read_parquet(paths["mkt_cap"])
        mkt["date"] = pd.to_datetime(mkt["date"], errors="coerce")
        mkt["date_plus_1"] = mkt["date"] + pd.Timedelta(days=1) # adding one day to have the market cap on the last day show for the current day 
        mkt = mkt[["date_plus_1", "marketCap"]].sort_values(by="date_plus_1", ascending=True)

        price_mkt = pd.merge_asof(price_cash, mkt, left_on="date", right_on="date_plus_1", direction="backward").sort_values(by="date", ascending=True)
        price_mkt = price_mkt.drop(columns=["date_plus_1"])

        # Joining balance sheet
        balance = pd.read_parquet(paths["balance_sheet"])
        balance["acceptedDate"] = pd.to_datetime(balance["acceptedDate"])
        balance = balance[['acceptedDate', 'cashAndCashEquivalents',
       'shortTermInvestments', 'cashAndShortTermInvestments', 'netReceivables',
       'accountsReceivables', 'otherReceivables', 'inventory', 'prepaids',
       'otherCurrentAssets', 'totalCurrentAssets', 'propertyPlantEquipmentNet',
       'goodwill', 'intangibleAssets', 'goodwillAndIntangibleAssets',
       'longTermInvestments', 'taxAssets', 'otherNonCurrentAssets',
       'totalNonCurrentAssets', 'otherAssets', 'totalAssets', 'totalPayables',
       'accountPayables', 'otherPayables', 'accruedExpenses', 'shortTermDebt',
       'capitalLeaseObligationsCurrent', 'taxPayables', 'deferredRevenue',
       'otherCurrentLiabilities', 'totalCurrentLiabilities', 'longTermDebt',
       'capitalLeaseObligationsNonCurrent', 'deferredRevenueNonCurrent',
       'deferredTaxLiabilitiesNonCurrent', 'otherNonCurrentLiabilities',
       'totalNonCurrentLiabilities', 'otherLiabilities',
       'capitalLeaseObligations', 'totalLiabilities', 'treasuryStock',
       'preferredStock', 'commonStock', 'retainedEarnings',
       'additionalPaidInCapital', 'accumulatedOtherComprehensiveIncomeLoss',
       'otherTotalStockholdersEquity', 'totalStockholdersEquity',
       'totalEquity', 'minorityInterest', 'totalLiabilitiesAndTotalEquity',
       'totalInvestments', 'totalDebt', 'netDebt']].sort_values(by="acceptedDate", ascending=True)

        price_balance = pd.merge_asof(price_mkt, balance, left_on="date", right_on="acceptedDate", direction="backward").sort_values(by="date", ascending=True)

        return price_balance

    # Valuation Dynamics
    def pe_ratio(self, df):
        if "marketCap" not in df.columns:
            raise ValueError("The dataframe provided does not contain the marketCap column")
        if "netIncome" not in df.columns:
            raise ValueError("The dataframe provided does not contain the netIncome column")
        df["peRatio"] = df["marketCap"] / df["netIncome"].replace(0, float("nan"))
        return df

    # Earnings Quality
    def cash_conversion_of_earnings(self, df): # operating cash flow / net income; persistently <1 is a red flag
        if "operatingCashFlow" not in df.columns:
            raise ValueError("The dataframe provided does not contain the operatingCashFlow column")
        if "netIncome" not in df.columns:
            raise ValueError("The dataframe provided does not contain the netIncome column")
        df["earningsQuality"] = df["operatingCashFlow"] / df["netIncome"].replace(0, float("nan"))
        return df

    # Capital Allocation Efficiency
    def rnd_yield (self, df): # revenue growth per dollar of R&D spend, lagged 2-3 years
        # Do not have data yet 
        pass

    # Operational Drift
    def gross_margin_durability(self, df): # rolling standard deviation of gross margins (stability is often undervalued)
        # Do not have data yet 
        pass

    # Balance Sheet Dynamics
    def net_cash_pct_market_cap(self, df): # -netDebt / marketCap; negative means more debt than cash
        if "netDebt" not in df.columns:
            raise ValueError("The dataframe provided does not contain the netDebt column")
        if "marketCap" not in df.columns:
            raise ValueError("The dataframe provided does not contain the marketCap column")
        df["netCashPctMarketCap"] = -df["netDebt"] / df["marketCap"].replace(0, float("nan"))
        return df

    def current_ratio(self, df): # totalCurrentAssets / totalCurrentLiabilities; <1 means short-term liabilities exceed short-term assets
        if "totalCurrentAssets" not in df.columns:
            raise ValueError("The dataframe provided does not contain the totalCurrentAssets column")
        if "totalCurrentLiabilities" not in df.columns:
            raise ValueError("The dataframe provided does not contain the totalCurrentLiabilities column")
        df["currentRatio"] = df["totalCurrentAssets"] / df["totalCurrentLiabilities"].replace(0, float("nan"))
        return df

    def debt_to_equity(self, df): # totalDebt / totalStockholdersEquity; higher ratio = more leveraged
        if "totalDebt" not in df.columns:
            raise ValueError("The dataframe provided does not contain the totalDebt column")
        if "totalStockholdersEquity" not in df.columns:
            raise ValueError("The dataframe provided does not contain the totalStockholdersEquity column")
        df["debtToEquity"] = df["totalDebt"] / df["totalStockholdersEquity"].replace(0, float("nan"))
        return df

    def price_to_book(self, df): # marketCap / totalStockholdersEquity; <1 may indicate undervaluation
        if "marketCap" not in df.columns:
            raise ValueError("The dataframe provided does not contain the marketCap column")
        if "totalStockholdersEquity" not in df.columns:
            raise ValueError("The dataframe provided does not contain the totalStockholdersEquity column")
        df["priceToBook"] = df["marketCap"] / df["totalStockholdersEquity"].replace(0, float("nan"))
        return df

    def return_on_equity(self, df): # netIncome / totalStockholdersEquity; how efficiently equity is being used to generate profit
        if "netIncome" not in df.columns:
            raise ValueError("The dataframe provided does not contain the netIncome column")
        if "totalStockholdersEquity" not in df.columns:
            raise ValueError("The dataframe provided does not contain the totalStockholdersEquity column")
        df["returnOnEquity"] = df["netIncome"] / df["totalStockholdersEquity"].replace(0, float("nan"))
        return df

    def return_on_assets(self, df): # netIncome / totalAssets; how efficiently assets are being used to generate profit
        if "netIncome" not in df.columns:
            raise ValueError("The dataframe provided does not contain the netIncome column")
        if "totalAssets" not in df.columns:
            raise ValueError("The dataframe provided does not contain the totalAssets column")
        df["returnOnAssets"] = df["netIncome"] / df["totalAssets"].replace(0, float("nan"))
        return df

    # Valuation vs. Cash Generation
    def fcf_yield(self, df): # freeCashFlow / marketCap; how much free cash the business generates per dollar of market value
        if "freeCashFlow" not in df.columns:
            raise ValueError("The dataframe provided does not contain the freeCashFlow column")
        if "marketCap" not in df.columns:
            raise ValueError("The dataframe provided does not contain the marketCap column")
        df["fcfYield"] = df["freeCashFlow"] / df["marketCap"].replace(0, float("nan"))
        return df

    # Market Structure
    def institutional_ownership_drift(self, df): # umulative insider buy/sell ratio over rolling 12 months
        # Do not have data yet 
        pass

    def calculate_all(self):
        """This function will apply all functions to the mega df for a ticker"""
        df = self.mega_df()
        df = self.pe_ratio(df)
        df = self.cash_conversion_of_earnings(df)
        # df = self.rnd_yield(df)
        # df = self.gross_margin_durability(df)
        df = self.net_cash_pct_market_cap(df)
        df = self.current_ratio(df)
        df = self.debt_to_equity(df)
        df = self.price_to_book(df)
        df = self.return_on_equity(df)
        df = self.return_on_assets(df)
        df = self.fcf_yield(df)
        # df = self.institutional_ownership_drift(df)
        return df