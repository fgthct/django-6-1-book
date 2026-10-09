from articles.archive import read_archive, write_archive


def test_archive_round_trip(articles, tmp_path):
    path = tmp_path / "archive.json.zst"
    count = write_archive(path)
    data = read_archive(path)
    assert count == len(data) == 5
    assert {a["slug"] for a in data} == {"etna", "arancino", "theater", "castle", "cannolo"}
