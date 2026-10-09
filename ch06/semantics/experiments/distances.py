"""The three pgvector distances, on three vectors made by hand and on the model's vectors."""
import django
import numpy as np

django.setup()

from django.db import connection  # noqa: E402

from sentences.embedder import embed  # noqa: E402

with connection.cursor() as cur:
    cur.execute("SELECT '[3,4]'::vector <-> '[0,0]'::vector")
    print("<->  L2 distance between [3,4] and [0,0]            =", cur.fetchone()[0])
    cur.execute("SELECT '[1,0]'::vector <=> '[0,1]'::vector")
    print("<=>  cosine distance between [1,0] and [0,1]        =", cur.fetchone()[0])
    cur.execute("SELECT '[1,2]'::vector <#> '[3,4]'::vector")
    print("<#>  negative inner product between [1,2] and [3,4] =", cur.fetchone()[0])

    # Three vectors made by hand, in the plane. The question is [1, 0].
    # a points the same way but is short; b is very long and slightly off; c is almost the same.
    print("\nVectors by hand. Question = [1,0]; a = [0.5,0]; b = [10,2]; c = [0.9,0.1]")
    for name, op in {"L2": "<->", "cosine": "<=>", "negative inner product": "<#>"}.items():
        cur.execute(f"""
            SELECT name FROM (VALUES ('a','[0.5,0]'::vector), ('b','[10,2]'::vector), ('c','[0.9,0.1]'::vector))
            AS t(name, v) ORDER BY v {op} '[1,0]'::vector""")
        print(f"{name:<24} nearest to farthest: {[r[0] for r in cur.fetchall()]}")

# And now with the model's real vectors: a question and five texts.
texts = [
    "Why volcanic soil makes such good wine",
    "How to make Sicilian arancini with ragù and peas",
    "Earthquakes and magma: how to read an imminent eruption",
    "How a database index speeds up queries",
    "The Aeolian Islands, born of fire from the depths",
]
question = "the mountain of fire is waking up"
docs = np.array(embed(texts))
q = np.array(embed([question])[0])


def orders(docs, q):
    cosine = 1 - docs @ q / (np.linalg.norm(docs, axis=1) * np.linalg.norm(q))
    l2 = np.linalg.norm(docs - q, axis=1)
    neg_dot = -(docs @ q)
    return {"cosine": cosine, "L2": l2, "inner product (negated)": neg_dot}


print("\nNorm of the model's vectors:", [round(float(n), 3) for n in np.linalg.norm(docs, axis=1)])
for name, d in orders(docs, q).items():
    print(f"{name:<26} order: {[int(i) for i in np.argsort(d)]}")

docs_n = docs / np.linalg.norm(docs, axis=1, keepdims=True)
q_n = q / np.linalg.norm(q)
print("\nAfter normalization (norm = 1):")
res = {}
for name, d in orders(docs_n, q_n).items():
    res[name] = [int(i) for i in np.argsort(d)]
    print(f"{name:<26} order: {res[name]}")
assert len({tuple(v) for v in res.values()}) == 1, "with unit vectors, the three orders must be the same"
