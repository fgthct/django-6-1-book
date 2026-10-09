"""200,000 rows in 40 blocks: serial, threads, processes, subinterpreters."""
import random
import time
from concurrent.futures import (
    InterpreterPoolExecutor, ProcessPoolExecutor, ThreadPoolExecutor,
)

from campaigns.validation import validate_block

if __name__ == "__main__":
    rnd = random.Random(1)
    domains = ["example.com", "bücher.example", "città.example", "mail.example.org"]
    rows = [
        (rnd.choice([f"User{rnd.randrange(10**6)}@{rnd.choice(domains)}", "broken", " X@Y.IT "]),
         rnd.choice(["ana", "  gino   rossi ", ""]))
        for _ in range(200_000)
    ]
    blocks = [rows[i : i + 5000] for i in range(0, len(rows), 5000)]
    print(f"{len(rows)} rows in {len(blocks)} blocks, 2 cores, three runs each\n")

    def serial():
        return [validate_block(b) for b in blocks]

    def with_pool(make):
        def run():
            with make() as pool:
                return list(pool.map(validate_block, blocks))
        return run

    modes = {
        "serial": serial,
        "2 threads": with_pool(lambda: ThreadPoolExecutor(2)),
        "2 processes": with_pool(lambda: ProcessPoolExecutor(2)),
        "2 subinterpreters": with_pool(lambda: InterpreterPoolExecutor(2)),
    }
    expected = serial()
    base = None
    print(f"{'mode':18}{'runs (s)':24}{'best':>8}{'vs serial':>14}")
    for name, fn in modes.items():
        times = []
        for _ in range(3):
            t = time.perf_counter()
            result = fn()
            times.append(time.perf_counter() - t)
            assert result == expected
        best = min(times)
        base = base or best
        print(f"{name:18}{' '.join(f'{x:.2f}' for x in times):24}{best:>7.2f}s{base / best:>13.2f}x")
