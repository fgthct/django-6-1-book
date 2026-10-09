import inspect

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from shop import views
from shop.models import Category, Product

from .conftest import HTMX, add_to_cart


def test_full_page_and_fragment(client, catalog):
    full = client.get(reverse("shop:catalog"))
    fragment = client.get(reverse("shop:catalog"), **HTMX)
    assert "<html" in full.text and "<html" not in fragment.text
    assert "Almond Brittle" in fragment.text
    assert "HX-Request" in full["Vary"]


def test_async_pagination_splits_into_pages(client, catalog):
    page1 = client.get(reverse("shop:catalog"))
    assert page1.text.count("<h2>") == 6 and "Pistachio Cream" in page1.text
    assert "Torrone" not in page1.text
    page2 = client.get(reverse("shop:catalog"), {"page": 2})
    assert page2.text.count("<h2>") == 1 and "Torrone" in page2.text


def test_out_of_range_page_shows_the_last(client, catalog):
    r = client.get(reverse("shop:catalog"), {"page": 99})
    assert "Page 2" in r.text
    r = client.get(reverse("shop:catalog"), {"page": "abc"})
    assert "Page 1" in r.text


def test_filters_combine(client, catalog):
    sweets = Category.objects.get(name="Sweets")
    r = client.get(reverse("shop:catalog"), {"q": "almond", "category": sweets.pk})
    assert "Almond Brittle" in r.text and "Marzipan Fruit" in r.text
    assert "Bitter Orange Soda" not in r.text and "Cannoli" not in r.text
    r = client.get(reverse("shop:catalog"), {"q": "almond", "category": Category.objects.get(name="Drinks").pk})
    assert "No products found." in r.text


def test_pagination_links_work_without_htmx(client, catalog):
    r = client.get(reverse("shop:catalog"), {"q": ""})
    assert 'href="?q=&category=&page=2"' in r.text


def test_the_number_of_queries_does_not_depend_on_the_number_of_products(client, catalog):
    def count(query):
        with CaptureQueriesContext(connection) as q:
            assert client.get(reverse("shop:catalog"), query).status_code == 200
        return len(q)

    assert count({}) == count({"q": "soda"})  # 6 products versus 1


def test_total_ordering(db):
    assert Product.objects.all().totally_ordered


def test_a_visitor_with_a_session_sees_their_cart_in_the_catalog(client, catalog):
    # The "session read synchronously" defect only shows up when the session
    # already exists: a brand-new visitor would not bring it out.
    add_to_cart(client, catalog[0])
    r = client.get(reverse("shop:catalog"))
    assert r.status_code == 200 and "Cart (1)" in r.text


def test_the_catalog_view_is_really_async():
    assert inspect.iscoroutinefunction(views.catalog)
