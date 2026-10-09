import json

from compression import zstd

articles = [
    {"id": i, "title": f"Article {i}", "text": "Lorem ipsum dolor sit amet " * 5}
    for i in range(1000)
]
data = json.dumps(articles).encode()

compressed = zstd.compress(data, level=9)
print(f"{len(data)} -> {len(compressed)} bytes")

assert zstd.decompress(compressed) == data
