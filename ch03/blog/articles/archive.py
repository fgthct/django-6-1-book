import json
from pathlib import Path

from compression import zstd

from .models import Article


def write_archive(path: Path) -> int:
    """Save the published articles to a JSON file compressed with Zstandard."""
    articles = Article.objects.filter(published=True).values(
        "title", "slug", "summary", "body", "tags", "published_at"
    )
    data = [
        {**article, "published_at": article["published_at"].isoformat()}
        for article in articles
    ]
    with zstd.open(path, "wt", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False)
    return len(data)


def read_archive(path: Path) -> list[dict]:
    """Read an archive created by write_archive()."""
    with zstd.open(path, "rt", encoding="utf-8") as file:
        return json.load(file)
