def convert(value):
    try:
        return int(value)
    except ValueError, TypeError:  # PEP 758: no parentheses
        return None


print(convert("12"), convert("x"), convert(None))
