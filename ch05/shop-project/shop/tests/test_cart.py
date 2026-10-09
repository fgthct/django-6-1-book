from decimal import Decimal

from django.test import Client
from django.urls import reverse

from shop.models import Order, OrderLine, Product

from .conftest import HTMX, add_to_cart


def test_add_updates_the_badge_and_sends_a_message(client, catalog):
    r = client.post(reverse("shop:add", args=[catalog[0].pk]), **HTMX)
    assert r.status_code == 200
    assert "Cart (1)" in r.text
    assert "added to the cart" in r["HX-Trigger"]


def test_you_cannot_exceed_the_stock(client, catalog):
    product = catalog[3]  # stock 3
    add_to_cart(client, product, times=4)
    assert client.session["cart"][str(product.pk)] == 3


def test_a_sold_out_product_cannot_be_added(client, catalog):
    r = client.post(reverse("shop:add", args=[catalog[5].pk]), **HTMX)
    assert "Cart (0)" in r.text
    assert "cart" not in client.session or not client.session["cart"]


def test_set_limits_to_stock_and_reports_the_error(client, catalog):
    product = catalog[3]
    add_to_cart(client, product)
    r = client.post(reverse("shop:set_quantity", args=[product.pk]), {"quantity": 9}, **HTMX)
    assert r.status_code == 200
    assert "Only 3 left" in r.text
    assert client.session["cart"][str(product.pk)] == 3


def test_invalid_quantity_is_a_visible_error_with_200(client, catalog):
    add_to_cart(client, catalog[0])
    r = client.post(reverse("shop:set_quantity", args=[catalog[0].pk]), {"quantity": "abc"}, **HTMX)
    # HTMX 2 never swaps 4xx responses: the user must see the error with a 200
    assert r.status_code == 200 and "Invalid quantity." in r.text


def test_quantity_zero_removes_the_row(client, catalog):
    add_to_cart(client, catalog[0])
    r = client.post(reverse("shop:set_quantity", args=[catalog[0].pk]), {"quantity": 0}, **HTMX)
    assert "Your cart is empty." in r.text
    assert client.session["cart"] == {}


def test_the_total_uses_database_prices(client, catalog):
    add_to_cart(client, catalog[0], times=2)
    # a price sent by the browser is simply ignored
    r = client.post(reverse("shop:set_quantity", args=[catalog[0].pk]),
                    {"quantity": 2, "price": "0.01"}, **HTMX)
    assert "Total: $12.00" in r.text
    Product.objects.filter(pk=catalog[0].pk).update(price=Decimal("7.00"))
    assert "Total: $14.00" in client.get(reverse("shop:cart")).text


def test_the_cart_ignores_vanished_products(client, catalog):
    session = client.session
    session["cart"] = {"999999": 2}
    session.save()
    r = client.get(reverse("shop:cart"))
    assert r.status_code == 200 and "Your cart is empty." in r.text


def test_successful_order(client, catalog):
    add_to_cart(client, catalog[0], times=2)
    r = client.post(reverse("shop:place_order"), {"email": "a@example.com"}, **HTMX)
    assert r.status_code == 200 and "HX-Redirect" in r
    assert Order.objects.count() == 1 and OrderLine.objects.count() == 1
    catalog[0].refresh_from_db()
    assert catalog[0].stock == 3
    assert "cart" not in client.session


def test_the_order_price_stays_even_if_the_price_list_changes(client, catalog):
    add_to_cart(client, catalog[0])
    client.post(reverse("shop:place_order"), {"email": "a@example.com"}, **HTMX)
    Product.objects.filter(pk=catalog[0].pk).update(price=Decimal("99.00"))
    assert OrderLine.objects.get().unit_price == Decimal("6.00")


def test_order_without_htmx_redirects(client, catalog):
    add_to_cart(client, catalog[0])
    r = client.post(reverse("shop:place_order"), {"email": "a@example.com"})
    assert r.status_code == 302 and r["Location"].startswith("/thanks/")


def test_order_is_atomic_if_a_line_is_unavailable(client, catalog):
    add_to_cart(client, catalog[0]); add_to_cart(client, catalog[1]); add_to_cart(client, catalog[1])
    # meanwhile another customer buys almost all of the second product
    Product.objects.filter(pk=catalog[1].pk).update(stock=1)
    r = client.post(reverse("shop:place_order"), {"email": "a@example.com"}, **HTMX)
    assert r.status_code == 200 and "is no longer available" in r.text
    assert Order.objects.count() == 0
    catalog[0].refresh_from_db()
    assert catalog[0].stock == 5  # the first line, already deducted, was rolled back
    assert client.session["cart"]  # the cart is not lost


def test_order_with_empty_cart(client, catalog):
    r = client.post(reverse("shop:place_order"), {"email": "a@example.com"}, **HTMX)
    assert r.status_code == 200 and "The cart is empty." in r.text
    assert Order.objects.count() == 0


def test_order_with_invalid_email(client, catalog):
    add_to_cart(client, catalog[0])
    r = client.post(reverse("shop:place_order"), {"email": "not-an-email"}, **HTMX)
    assert r.status_code == 200 and "errorlist" in r.text
    assert Order.objects.count() == 0


def test_changes_require_the_csrf_token(catalog):
    c = Client(enforce_csrf_checks=True)
    r = c.post(reverse("shop:add", args=[catalog[0].pk]), **HTMX)
    assert r.status_code == 403
