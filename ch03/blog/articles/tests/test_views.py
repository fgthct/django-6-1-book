from django.urls import reverse

from articles.models import Comment

from .helpers import make_article


def test_list_shows_only_published_articles(client, articles):
    html = client.get(reverse("articles:list")).content.decode()
    assert "Climbing Etna" in html
    assert "Draft notes" not in html


def test_list_newest_first(client, articles):
    page = client.get(reverse("articles:list")).context["object_list"]
    assert [a.slug for a in page][:2] == ["cannolo", "castle"]


def test_search_with_highlighting(client, articles):
    html = client.get(reverse("articles:list"), {"q": "ricotta"}).content.decode()
    assert "<mark>ricotta</mark>" in html


def test_search_does_not_show_drafts(client, articles):
    html = client.get(reverse("articles:list"), {"q": "cannolo"}).content.decode()
    assert "Draft notes" not in html


def test_highlighting_does_not_allow_injected_html(client, db):
    # an unclosed tag survives ts_headline: only escaping protects us
    make_article("xss", "Title", "Text with <img src=x onerror=alert(1) and the word cannolo.")
    response = client.get(reverse("articles:list"), {"q": "cannolo"})
    html = response.content.decode()
    assert "<img src=x" not in html
    assert "&lt;img src=x onerror=alert(1)" in html
    assert "<mark>cannolo</mark>" in html


def test_tag_filter(client, articles):
    page = client.get(reverse("articles:list"), {"tag": "food"}).context["object_list"]
    assert {a.slug for a in page} == {"arancino", "cannolo"}


def test_category_filter(client, articles):
    page = client.get(reverse("articles:list"), {"category": "food"}).context["object_list"]
    assert {a.slug for a in page} == {"arancino", "cannolo"}


def test_detail_of_a_draft_does_not_exist(client, articles):
    response = client.get(reverse("articles:detail", args=["draft"]))
    assert response.status_code == 404


def test_comment(client, articles):
    url = reverse("articles:comment", args=["etna"])
    response = client.post(url, {"author": "Ann", "body": "Great!"})
    assert response.status_code == 302
    assert Comment.objects.filter(article=articles["etna"], author="Ann").exists()


def test_comment_on_a_draft_is_rejected(client, articles):
    url = reverse("articles:comment", args=["draft"])
    response = client.post(url, {"author": "Ann", "body": "Hi"})
    assert response.status_code == 404
    assert Comment.objects.count() == 0


def test_list_has_a_fixed_number_of_queries(client, articles, django_assert_num_queries):
    with django_assert_num_queries(3):  # count, page, categories
        response = client.get(reverse("articles:list"))
    assert response.status_code == 200


def test_pagination_does_not_repeat_or_lose_articles(client, db):
    for i in range(14):
        make_article(f"a{i}", f"Article {i}", "text", day=i % 3)
    seen = []
    for page in (1, 2, 3):
        response = client.get(reverse("articles:list"), {"page": page})
        seen += [a.slug for a in response.context["object_list"]]
    assert sorted(seen) == sorted(f"a{i}" for i in range(14))
    assert len(seen) == len(set(seen))


def test_search_list_has_a_deterministic_ordering(client, articles):
    response = client.get(reverse("articles:list"), {"q": "etna"})
    assert response.context["paginator"].object_list.totally_ordered is True
