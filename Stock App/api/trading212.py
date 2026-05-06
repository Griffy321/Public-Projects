from dotenv import load_dotenv
import os
import datetime
import requests
from pathlib import Path
import time
import base64
import sqlite3 as sql

# Responsible for:
# - making API requests to Trading 212
# - handling authentication and headers
# - returning raw JSON responses
# - handling request errors and response status checks

load_dotenv(Path(__file__).parent.parent / "config.env")
api_key = os.getenv("t212_api_key")
t212_secret_key = os.getenv("t212_secret_key")

class TradingAccount():
    def __init__(self, api_key, secret_key):
        credentials = base64.b64encode(f"{api_key}:{secret_key}".encode()).decode()
        self.auth_header = {"Authorization": f"Basic {credentials}"}
        self.pies = []

    def get_account_info(self):
        account_url = "https://live.trading212.com/api/v0/equity/account/summary"
        response = requests.get(url=account_url, headers=self.auth_header)
        if response.status_code == 429:
            time.sleep(6)
            response = requests.get(url=account_url, headers=self.auth_header)
        if response.status_code != 200:
            print(f"Request failed. Status: {response.status_code}")
            return {}
        return response.json()

    def update_pie_ids(self, pie_data):
        for pie in pie_data:
            pie_id = pie.get("id")
            data = self.get_one_pie(pie_id=pie_id)
            pie_name = data.get("settings").get("name")
            if pie_id in self.pies:
                pass
            else:
                self.pies.append({pie_id : pie_name})
        print(self.pies)

    def try_request(self, url, pie_id=None):
        retries = 0
        response = requests.get(url=url, headers=self.auth_header)
        while response.status_code == 429:
            if retries < 10:
                retries += 1
                print(f"Request failed with 429. Retrying... Attempt {retries}")
                time.sleep(15)
                response = requests.get(url=url, headers=self.auth_header)  # retry request in the while statment 
            elif response.status_code in [401, 403, 408]:
                print(f"Request failed with responce code: {response.status_code}")
                return {}
            else:
                print(f"Request failed 10 times. Endpoint returned status code: {response.status_code}")
                return {}
        return response
    
    def try_post(self, url, payload):
        retries = 0
        response = requests.post(url=url, json=payload, headers=self.auth_header) 
        while response.status_code == 429:
            if retries < 10:
                retries += 1 # add a new try 
                print(f"Post failed with 429. Retrying... Attempt {retries}")
                time.sleep(15) # sleep before the retry 
                response = requests.post(url=url, json=payload, headers=self.auth_header)
            elif response.status_code in [401, 403, 408]:
                print(f"Request failed with responce code: {response.status_code}")
                return{}
            else:
                print(f"Request failed 10 times. Endpoint returned status code: {response.status_code}")
                return {}
        return response    

    def get_all_pies(self):
        pie_url = "https://live.trading212.com/api/v0/equity/pies"
        response = self.try_request(url = pie_url)
        return response.json()

    def get_one_pie(self, pie_id=None):
        if pie_id is None:
            self.update_pie_ids(self.get_all_pies())
            if not self.pies:
                print("No pies available.")
                return {}
            index = input("enter the pie you want to view (0 indexed):")
            index = int(index)
            pie_id = self.pies[index].keys()
            pie_id = next(iter(pie_id))
        pie_url = f"https://live.trading212.com/api/v0/equity/pies/{pie_id}"
        response = self.try_request(url = pie_url)
        return response.json()

    def update_pie(self, pie_id):
        now = datetime.datetime.strftime(datetime.datetime.now(), format="%Y-%m-%dT%H:%M:%S")
        update_url = f"https://live.trading212.com/api/v0/equity/pies/{pie_id}"
        pie_info = self.get_one_pie(pie_id)
        settings = pie_info.get("settings")
        if " : " not in settings.get("name"): 
            payload = {
            "dividendCashAction": settings.get("dividendCashAction"),
            "goal": settings.get("goal"),
            "icon": settings.get("icon"),
            "instrumentShares": {
                "AAPL_US_EQ": 0.5,
                "MSFT_US_EQ": 0.5
                },
            "name": settings.get("name") + " : " + now
            }
        else:
            name = settings.get("name").split(" : ")
            name[1] = now
            payload = {
            "dividendCashAction": settings.get("dividendCashAction"),
            "goal": settings.get("goal"),
            "icon": settings.get("icon"),
            "instrumentShares": {
                "AAPL_US_EQ": 0.5,
                "MSFT_US_EQ": 0.5
                },
            "name": name[0] + " : " + name[1]
            }
        response = self.try_post(url=update_url, payload=payload)
        return response.json()
    
    def fetch_tickers(self):
        url = "https://live.trading212.com/api/v0/equity/metadata/instruments"
        response = self.try_request(url)
        return response.json()

# account = TradingAccount(api_key, t212_secret_key)
# print(account.fetch_tickers())
