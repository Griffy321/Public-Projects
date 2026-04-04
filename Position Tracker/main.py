import sim_prices
import portfolio_class as pc

portfolio = pc.PortfolioActions(initial_cash=10000)

while True:
    prices = sim_prices.return_prices(beta=1, number_of_prices=5)
    portfolio.update_current_prices(prices)

    print("Latest prices:", prices)
    print("Portfolio value:", portfolio.total_value())
    print("Cash available:", portfolio.cash)
    print("Holdings:", portfolio.holdings)

    # user can make buy/sell decisions here based on the latest prices
    user_input = input("Enter either buy/sell/or press Enter to skip: ").strip().lower()

    if user_input == "buy":
        try:
            stock_number = int(input("Enter stock number to buy: "))
        except ValueError:
            print("Invalid stock number. Please enter a valid number.")
            continue
        try:
            amount = float(input("Enter amount to invest: "))
        except ValueError:
            print("Invalid amount. Please enter a number.")
            continue
        portfolio.buy_stock(stock_number, amount)
    
    if user_input == "sell":
        stock_number = int(input("Enter stock number to sell: "))
        quantity = input("Enter quantity to sell: ")

        if quantity == "all":
            quantity = portfolio.holdings.get(stock_number, {}).get("quantity", 0)
            portfolio.sell_stock(stock_number, quantity)
        else:
            portfolio.sell_stock(stock_number, quantity)

    if user_input == "end":
        print("Simulation ended")
        print("Final Portfolio Value:", portfolio.total_value())
        print("Transaction History:")
        print(portfolio.transaction_hist)
        break

    