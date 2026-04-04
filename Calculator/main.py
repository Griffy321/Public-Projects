import operations as f
import decimal
import pandas as pd
import history as h 

def main():
    print("Welcome to the calculator!")
    operation_string = ""
    value = None
    last_operation = None
    last_input_type = None
    is_numeric = False
    operations = {
        "+": f.add_nums,
        "-": f.subtract_nums,
        "*": f.multiply_nums,
        "/": f.divide_nums}
    while True:
        user_input = input("Enter a number or an operator (+, -, *, /) to calculate: ")
        if user_input in operations:
            if last_input_type == "operator":
                print("Cannot enter two operators in a row. Please enter a number.")
                continue
            last_operation = user_input # update last_operation after validating input and making sure it's an operator 
            last_input_type = "operator"
            
        if user_input == "clear":
            operation_string = ""
            value = None
            last_operation = None
            last_input_type = None
            print("Calculator cleared.")
            h.log_operation("clear", "Calculator cleared")
            continue

        if f.is_decimal(user_input) == True and last_input_type != "number":
            user_input = decimal.Decimal(user_input)
            is_numeric = True
            last_input_type = "number"

        elif not f.is_operator(user_input) and last_input_type == "number":
            print("Cannot enter two numbers in a row. Please enter an operator.")
            continue
        print(f"user_input: {user_input}")

        if value is None:
            value = user_input
            operation_string += f"{value}"
        elif value is not None and user_input in operations:
            operation_string += f"{user_input}"
        elif value is not None and is_numeric:
            operation_string += f"{user_input}"
        print(operation_string)
        
        if user_input in operations.keys(): 
            try:
                decimal.Decimal(user_input)
                pass # skip if it's just a number
            except decimal.InvalidOperation:
                pass # skip if it's just an operator
        elif last_operation in operations.keys() and user_input not in operations.keys():
            value = operations[last_operation](value, user_input)
            print(f"value: {value}")
            h.log_operation(operation_string, value)

if __name__ == "__main__":
    main()