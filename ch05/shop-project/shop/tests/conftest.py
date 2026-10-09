from decimal import Decimal

import pytest
from django.urls import reverse

from shop.models import Category, Product

HTMX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def catalog(db):
    sweets = Category.objects.create(name="Sweets")
    drinks = Category.objects.create(name="Drinks")
    data = [
        (sweets, "Almond Brittle", "Crunchy almonds", "6.00", 5),
        (sweets, "Pistachio Cream", "Spreadable pistachio", "12.00", 5),
        (sweets, "Cannoli Shells", "Crisp shells", "9.00", 4),
        (sweets, "Marzipan Fruit", "Painted almond paste", "15.00", 3),
        (sweets, "Torrone", "Soft nougat", "8.00", 6),
        (sweets, "Candied Peel", "Orange peel", "7.00", 0),
        (drinks, "Bitter Orange Soda", "Fizzy and bitter", "3.50", 20),
    ]
    return [
        Product.objects.create(category=c, name=n, description=d, price=Decimal(p), stock=s)
        for c, n, d, p, s in data
    ]


def add_to_cart(client, product, times=1):
    for _ in range(times):
        client.post(reverse("shop:add", args=[product.pk]), **HTMX)
