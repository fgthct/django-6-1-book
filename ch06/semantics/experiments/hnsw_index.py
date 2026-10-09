"""20,000 synthetic vectors: how fast and how precise is an HNSW index?"""
import time

import django
import numpy as np

django.setup()

from django.conf import settings  # noqa: E402
from django.db import connection  # noqa: E402

from sentences.models import SamplePoint  # noqa: E402

N, DIM, GROUPS, QUERIES, K = 20_000, settings.EMBEDDING_DIMENSIONS, 40, 100, 10
rng = np.random.default_rng(42)  # fixed seed: the experiment is repeatable

# Forty "groups" of nearby points: forty centers, and points scattered around them.
centers = rng.normal(size=(GROUPS, DIM))
group = rng.integers(0, GROUPS, size=N)
data = centers[group] + 0.6 * rng.normal(size=(N, DIM))
data /= np.linalg.norm(data, axis=1, keepdims=True)
qgroup = rng.integers(0, GROUPS, size=QUERIES)
queries = centers[qgroup] + 0.6 * rng.normal(size=(QUERIES, DIM))
queries /= np.linalg.norm(queries, axis=1, keepdims=True)


def vec(v):
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


table = SamplePoint._meta.db_table
with connection.cursor() as cur:
    # Load first, index after: that is the recommended order. TRUNCATE really empties the table.
    cur.execute("DROP INDEX IF EXISTS samplepoint_hnsw")
    cur.execute(f"TRUNCATE {table} RESTART IDENTITY")
    t = time.perf_counter()
    with cur.copy(f'COPY {table} ("group", embedding) FROM STDIN') as copy:
        for g, v in zip(group, data):
            copy.write_row((int(g), vec(v)))
    print(f"Inserted {N} rows of {DIM} dimensions in {time.perf_counter() - t:.1f} s")
    cur.execute(f"VACUUM ANALYZE {table}")
    cur.execute(f"SELECT pg_size_pretty(pg_table_size('{table}')), pg_column_size(embedding) FROM {table} LIMIT 1")
    size, col = cur.fetchone()
    print(f"Table (no index): {size}; one vector takes {col} bytes")

    t = time.perf_counter()
    cur.execute(
        f"CREATE INDEX samplepoint_hnsw ON {table} USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
    print(f"HNSW index built in {time.perf_counter() - t:.1f} s")
    cur.execute("SELECT pg_size_pretty(pg_relation_size('samplepoint_hnsw'))")
    print(f"Index size: {cur.fetchone()[0]}")

    print("\nExecution plan:")
    cur.execute(f"EXPLAIN SELECT id FROM {table} ORDER BY embedding <=> %s::vector LIMIT 10", [vec(queries[0])])
    for (line,) in cur.fetchall():
        print("  " + line[:110] + ("…" if len(line) > 110 else ""))

    # The exact answer, computed apart with numpy (ids start from 1 after RESTART IDENTITY).
    exact = [set((np.argsort(1 - data @ q)[:K] + 1).tolist()) for q in queries]

    def measure(label, setup, use_index=True):
        cur.execute("SET enable_indexscan = " + ("on" if use_index else "off"))
        cur.execute("SET enable_seqscan = " + ("off" if use_index else "on"))
        for stmt in setup:
            cur.execute(stmt)
        recall, elapsed = [], 0.0
        for q, truth in zip(queries, exact):
            t = time.perf_counter()
            cur.execute(f"SELECT id FROM {table} ORDER BY embedding <=> %s::vector LIMIT {K}", [vec(q)])
            ids = {r[0] for r in cur.fetchall()}
            elapsed += time.perf_counter() - t
            recall.append(len(ids & truth) / K)
        print(f"{label:<36} {np.mean(recall):>9.3f} {1000 * elapsed / QUERIES:>11.1f}")

    print(f"\n{'setting':<36} {'recall@10':>9} {'ms/search':>11}")
    measure("full scan (exact)", [], use_index=False)
    for ef in (10, 40, 100, 200):
        label = f"HNSW, ef_search = {ef}" + (" (default)" if ef == 40 else "")
        measure(label, [f"SET hnsw.ef_search = {ef}"])
    cur.execute("RESET hnsw.ef_search")
