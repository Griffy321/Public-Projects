import numpy as np
import time

def return_prices(beta: float = 1, number_of_prices: int = 10):
    prices = {}
    for number in range(number_of_prices):
        time.sleep(0.2)  # Simulate delay
        price = round(np.random.uniform(50, 200), 2) * beta  # Simulate price with 2 decimal places
        prices[number] = price
    return prices


if __name__ == "__main__":
    while True:
        price = return_prices(beta=1, number_of_prices=5)
        print(price)