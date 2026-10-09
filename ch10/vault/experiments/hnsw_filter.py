"""The HNSW index and a very selective filter: 30,000 vectors, 100 users, each with 1% of them.

    DB_PORT=5432 uv run python experiments/hnsw_filter.py
"""
import os
import random
import time

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

DIMENSIONS, ROWS, USERS = 32, 30_000, 100

conn = psycopg.connect(
    dbname="vault", user="vault", password="vault", host="localhost", port=os.environ.get("DB_PORT", "5432"), autocommit=True
)
register_vector(conn)
rng = np.random.default_rng(7)

conn.execute("DROP TABLE IF EXISTS filter_test")
conn.execute(f"CREATE TABLE filter_test (id serial PRIMARY KEY, owner int NOT NULL, v vector({DIMENSIONS}))")
vectors = rng.normal(size=(ROWS, DIMENSIONS)).astype(np.float32)
vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
owners = [i % USERS for i in range(ROWS)]
with conn.cursor().copy("COPY filter_test (owner, v) FROM STDIN WITH (FORMAT BINARY)") as copy:
    copy.set_types(["int4", "vector"])
    for owner, vec in zip(owners, vectors):
        copy.write_row((owner, vec))
conn.execute("CREATE INDEX filter_test_v_idx ON filter_test USING hnsw (v vector_cosine_ops)")
conn.execute("CREATE INDEX filter_test_owner_idx ON filter_test (owner)")
conn.execute("ANALYZE filter_test")

QUERY = "SELECT id FROM filter_test WHERE owner = %s ORDER BY v <=> %s LIMIT 10"
user = 7
q = vectors[random.Random(3).randrange(ROWS)] + 0.3 * rng.normal(size=DIMENSIONS).astype(np.float32)
q = (q / np.linalg.norm(q)).astype(np.float32)

# 1. What does the planner do? It has to really use the HNSW index, or the experiment shows nothing.
plan = [r[0] for r in conn.execute("EXPLAIN " + QUERY, (user, q)).fetchall()]
print("plan chosen by the planner:", " / ".join(p.strip().removeprefix("->  ").split("  (")[0].split(": (")[0] for p in plan[:3]))

# 2. The exact answers, with the index switched off.
conn.execute("SET enable_indexscan = off")
exact = {r[0] for r in conn.execute(QUERY, (user, q)).fetchall()}
conn.execute("RESET enable_indexscan")
print(f"exact answers (no index):          {len(exact)}")


def run(label, setting=None):
    conn.execute("SET hnsw.iterative_scan = " + (setting or "off"))
    got = [r[0] for r in conn.execute(QUERY, (user, q)).fetchall()]
    print(f"{label} {len(got):2d} answers, {len(set(got) & exact)} correct")
    return got


run("with the index, factory settings:  ")
run("with iterative_scan = strict_order :", "strict_order")
run("with iterative_scan = relaxed_order:", "relaxed_order")

# 3. The same, over every user: how many of them get a full page of 10?
def full_pages(setting):
    conn.execute("SET hnsw.iterative_scan = " + setting)
    start = time.perf_counter()
    full = sum(len(conn.execute(QUERY, (u, vectors[u * 7])).fetchall()) == 10 for u in range(USERS))
    return full, (time.perf_counter() - start) / USERS * 1000


print()
for setting in ("off", "strict_order", "relaxed_order"):
    full, ms = full_pages(setting)
    print(f"iterative_scan = {setting:14s}: {full:3d} users out of {USERS} get their 10 answers ({ms:.1f} ms per query)")
conn.execute("DROP TABLE filter_test")
