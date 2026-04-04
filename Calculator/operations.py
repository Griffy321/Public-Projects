from decimal import Decimal

def add_nums(a=None, b=None):
    a=Decimal(a)
    b=Decimal(b)
    if a is None or b is None:
        raise ValueError("Both a and b must be provided")
    return a + b

def subtract_nums(a=None, b=None):
    a=Decimal(a)
    b=Decimal(b)
    if a is None or b is None:
        raise ValueError("Both a and b must be provided")
    return a - b

def multiply_nums(a=None, b=None):
    a=Decimal(a)
    b=Decimal(b)
    if a is None or b is None:
        raise ValueError("Both a and b must be provided")
    return a * b

def divide_nums(a=None, b=None):
    a=Decimal(a)
    b=Decimal(b)
    if a is None or b is None:
        raise ValueError("Both a and b must be provided")
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

def is_decimal(value):
    import decimal 
    try:
        Decimal(value)
        return True
    except decimal.InvalidOperation:
        return False
    
def is_operator(value):
    if value in ["+", "-", "*", "/"]:
        return True
    return False


