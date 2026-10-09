"""The same 40 titles and the same 3 questions, given to two different models."""
import numpy as np
from fastembed import TextEmbedding

from sentences.corpus import CORPUS

QUESTIONS = [
    "fried rice dish with meat sauce",
    "the mountain of fire is waking up",
    "how much does a mortgage cost",
]
MODELS = [
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
]

rows = [(topic, text) for topic, texts in CORPUS.items() for text in texts]
for name in MODELS:
    model = TextEmbedding(name, cache_dir=".models")
    docs = np.array(list(model.embed([t for _, t in rows])))
    print(f"\n{name.split('/')[1]}  ({docs.shape[1]} dimensions)")
    for q in QUESTIONS:
        v = np.array(list(model.embed([q]))[0])
        cos = 1 - (docs @ v) / (np.linalg.norm(docs, axis=1) * np.linalg.norm(v))
        print(f"  «{q}»")
        for i in np.argsort(cos)[:3]:
            print(f"    {cos[i]:.3f}  [{rows[i][0]}] {rows[i][1]}")
