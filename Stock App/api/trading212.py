import json
from dotenv import load_dotenv

import os
import datetime
import requests
from pathlib import Path
import time

import base64

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

    def get_all_pies(self):
        pie_url = "https://live.trading212.com/api/v0/equity/pies"
        response = requests.get(url=pie_url, headers=self.auth_header)
        if response.status_code == 429:
            time.sleep(6)
            response = requests.get(url=pie_url, headers=self.auth_header)
        if response.status_code != 200:
            print(f"Request to trading 212 api did not work. Status: {response.status_code}")
            return {}
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
        response = requests.get(url=pie_url, headers=self.auth_header)
        if response.status_code == 429:
            time.sleep(6)
            response = requests.get(url=pie_url, headers=self.auth_header)
        if response.status_code != 200:
            print(f"Request to trading 212 api did not work. Status: {response.status_code}")
            return []
        return response.json()

    def update_pie(self, pie_id):
        update_url = f"https://live.trading212.com/api/v0/equity/pies/{pie_id}"
        pie_info = self.get_one_pie(pie_id)
        pie_name = pie_info.get("settings").get("name")
        payload = {
        "dividendCashAction": "REINVEST",
        "goal": 0,
        "icon": "string",
        "instrumentShares": {
            "AAPL_US_EQ": 0.5,
            "MSFT_US_EQ": 0.5
        },
        "name": str(pie_name + "1")
        }
        responce = requests.post(url=update_url, json=payload, headers=self.auth_header)
        print(responce.status_code)
        print(responce.json())

account = TradingAccount(api_key, t212_secret_key)
print(account.update_pie(pie_id=7873366))