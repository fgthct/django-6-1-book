from concurrent.futures import InterpreterPoolExecutor


def square(n):
    return n * n


if __name__ == "__main__":
    with InterpreterPoolExecutor(max_workers=2) as executor:
        print(list(executor.map(square, range(5))))
