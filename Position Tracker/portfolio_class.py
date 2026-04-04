import pandas as pd
import datetime

class PortfolioActions:
    def __init__(self, initial_cash=10000):
        self.cash = initial_cash
        self.transaction_hist =pd.DataFrame(columns=['stock_number', 'quantity', 'price', "action", "time"])
        self.holdings = {}
        self.current_prices = {}

    def update_current_prices(self, prices: dict): # added so i can constantly consume the curent prices of stocks 
        self.current_prices = prices

    def update_transaction_hist(self, stock_number, quantity, price, action):
        time = datetime.datetime.now()
        new_row = pd.DataFrame({
            'stock_number': [stock_number],
            'quantity': [quantity],
            'price': [price],
            'action': [action],
            'time': [time]
        })
        self.transaction_hist = pd.concat([self.transaction_hist, new_row], ignore_index=True)

    def buy_stock(self, stock_number, amount):
        price = self.current_prices.get(stock_number)
        if price is None:
            print(f"No current price for stock {stock_number}")
            return
        if amount > self.cash:
            print(f"Not enough cash. Available: {self.cash}")
            return
        
        quantity = amount / price
        self.cash -= amount
        if stock_number not in self.holdings:
            self.holdings[stock_number] = {"quantity": 0, "avg_cost": 0}

        old_qty = self.holdings[stock_number]["quantity"]
        old_cost = self.holdings[stock_number]["avg_cost"]

        new_qty = old_qty + quantity
        new_avg = ((old_qty * old_cost) + (quantity * price)) / new_qty

        self.holdings[stock_number]["quantity"] = new_qty
        self.holdings[stock_number]["avg_cost"] = new_avg

        self.update_transaction_hist(stock_number=stock_number, quantity=quantity, price=price, action="buy")

    def sell_stock(self, stock_number, quantity):
        quantity = float(quantity)
        price = self.current_prices.get(stock_number)
        if price is None:
            print(f"No current price for stock {stock_number}")
            return
        if stock_number not in self.holdings:
            print(f"You do not own stock {stock_number}")
            return
        held_qty = self.holdings[stock_number]["quantity"]
        if quantity > held_qty:
            print(f"Not enough shares to sell. Held: {held_qty}")
            return

        proceeds = quantity * price
        self.cash += proceeds
        self.holdings[stock_number]["quantity"] -= quantity
        if self.holdings[stock_number]["quantity"] == 0:
            del self.holdings[stock_number]

        self.update_transaction_hist(stock_number=stock_number, quantity=quantity, price=price, action="sell")

    def total_value(self):
        total = self.cash
        for stock_number, info in self.holdings.items():
            current_price = self.current_prices.get(stock_number)
            if current_price is not None:
                total += info["quantity"] * current_price
        return total