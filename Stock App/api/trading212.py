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
    def __init__(self, api_key):
        self.api_key = api_key
        self.pies = []

    def get_account_info(self):
        account_url = "https://live.trading212.com/api/v0/equity/account/summary"
        headers = {"Authorization": self.api_key}
        response = requests.get(url=account_url, headers=headers)
        if response.status_code == 429:
            time.sleep(6)
            response = requests.get(url=account_url, headers=headers)
        if response.status_code != 200:
            print(f"Request failed. Status: {response.status_code}")
            return {}
        return response.json()
    
    def update_pie_ids(self, pie_data):
        for pie in pie_data:
            pie_id = pie.get("id")
            if pie_id in self.pies:
                pass
            else:
                self.pies.append(pie_id)
        print(self.pies)

    def get_all_pies(self):
        pie_url = "https://live.trading212.com/api/v0/equity/pies"
        headers = {"Authorization": self.api_key}
        response = requests.get(url=pie_url, headers=headers)
        if response.status_code == 429:
            time.sleep(6)
            response = requests.get(url=pie_url, headers=headers)
        if response.status_code != 200:
            print(f"Request to trading 212 api did not work. Status: {response.status_code}")
            return {}
        return response.json()

    def get_one_pie(self, pie_id=None):
        if pie_id is None:
            self.update_pie_ids(self.get_all_pies())
            index = input("enter the pie you want to view (0 indexed):")
            index = int(index)
            pie_id = self.pies[index]
        pie_url = f"https://live.trading212.com/api/v0/equity/pies/{pie_id}"
        headers = {"Authorization": self.api_key}
        response = requests.get(url=pie_url, headers=headers)
        if response.status_code == 429:
            time.sleep(6)
            response = requests.get(url=pie_url, headers=headers)
        if response.status_code != 200:
            print(f"Request to trading 212 api did not work. Status: {response.status_code}")
            return {}
        return response.json()
    

account = TradingAccount(api_key)
print(account.get_one_pie())

