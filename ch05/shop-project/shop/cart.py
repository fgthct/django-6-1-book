from decimal import Decimal

from .models import Product

CART_KEY = "cart"


class Cart:
    """The cart lives in the session as {pk: quantity}. Prices don't: they are read from the database."""

    def __init__(self, data: dict[str, int]):
        self.data = data

    @classmethod
    def from_session(cls, session):
        return cls(session.get(CART_KEY, {}))

    @classmethod
    async def from_session_async(cls, session):
        return cls(await session.aget(CART_KEY, {}))

    def save(self, session):
        session[CART_KEY] = self.data
        session.modified = True

    def set(self, pk: int, quantity: int):
        if quantity > 0:
            self.data[str(pk)] = quantity
        else:
            self.data.pop(str(pk), None)

    def quantity(self, pk: int) -> int:
        return self.data.get(str(pk), 0)

    def count(self) -> int:
        return sum(self.data.values())

    def lines(self):
        products = Product.objects.in_bulk(int(pk) for pk in self.data)
        lines = []
        for pk, quantity in self.data.items():
            product = products.get(int(pk))
            if product is not None:
                lines.append({"product": product, "quantity": quantity,
                              "subtotal": product.price * quantity})
        lines.sort(key=lambda r: (r["product"].name, r["product"].pk))
        return lines

    def total(self, lines=None) -> Decimal:
        return sum((r["subtotal"] for r in (lines if lines is not None else self.lines())), Decimal("0"))
