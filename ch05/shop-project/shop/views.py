from django.core.paginator import AsyncPaginator
from django.db import transaction
from django.db.models import F, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.decorators.vary import vary_on_headers
from django_htmx.http import HttpResponseClientRedirect, trigger_client_event

from .cart import CART_KEY, Cart
from .forms import OrderForm, QuantityForm
from .models import Category, Order, OrderLine, Product

PAGE_SIZE = 6


def is_partial_request(request):
    return bool(request.htmx) and not request.htmx.history_restore_request


@vary_on_headers("HX-Request")
async def catalog(request):
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    products = Product.objects.select_related("category")
    if q:
        products = products.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if category.isdigit():
        products = products.filter(category_id=int(category))

    page = await AsyncPaginator(products, PAGE_SIZE).aget_page(request.GET.get("page"))
    items = await page.aget_object_list()
    context = {
        "products": items,
        "page": page,
        "previous": await page.aprevious_page_number() if await page.ahas_previous() else None,
        "next": await page.anext_page_number() if await page.ahas_next() else None,
        "total": await page.paginator.acount(),
        "q": q,
        "category": category,
        "categories": [c async for c in Category.objects.all()],
        "cart": await Cart.from_session_async(request.session),
    }
    template = "shop/catalog.html#grid" if is_partial_request(request) else "shop/catalog.html"
    return render(request, template, context)


@require_POST
def add(request, pk):
    product = get_object_or_404(Product, pk=pk)
    c = Cart.from_session(request.session)
    if c.quantity(pk) + 1 > product.stock:
        response = render(request, "shop/base.html#badge", {"cart": c})
        return trigger_client_event(response, "message", {"text": f"No more “{product.name}” available in that quantity."})
    c.set(pk, c.quantity(pk) + 1)
    c.save(request.session)
    response = render(request, "shop/base.html#badge", {"cart": c})
    return trigger_client_event(response, "message", {"text": f"“{product.name}” added to the cart."})


def cart_context(request, c, error=""):
    lines = c.lines()
    return {
        "lines": lines,
        "total": c.total(lines),
        "cart": c,
        "error": error,
        "form": OrderForm(),
    }


def cart_response(request, c, error=""):
    context = cart_context(request, c, error) | {"oob": True}
    return render(request, "shop/cart.html#content", context)


def cart(request):
    c = Cart.from_session(request.session)
    return render(request, "shop/cart.html", cart_context(request, c))


@require_POST
def set_quantity(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = QuantityForm(request.POST)
    c = Cart.from_session(request.session)
    error = ""
    if form.is_valid():
        quantity = form.cleaned_data["quantity"]
        if quantity > product.stock:
            quantity = product.stock
            error = f"Only {product.stock} left of “{product.name}”."
        c.set(pk, quantity)
        c.save(request.session)
    else:
        error = "Invalid quantity."
    return cart_response(request, c, error)


class InsufficientStock(Exception):
    def __init__(self, product):
        self.product = product


@require_POST
def place_order(request):
    c = Cart.from_session(request.session)
    form = OrderForm(request.POST)
    lines = c.lines()
    if not lines:
        return cart_response(request, c, "The cart is empty.")
    if not form.is_valid():
        context = cart_context(request, c) | {"form": form, "oob": True}
        return render(request, "shop/cart.html#content", context)
    try:
        with transaction.atomic():
            order = Order.objects.create(email=form.cleaned_data["email"])
            for r in lines:
                product, quantity = r["product"], r["quantity"]
                # The conditional update is atomic: no negative stock,
                # even if two customers buy the last item at the same instant.
                updated = Product.objects.filter(pk=product.pk, stock__gte=quantity).update(
                    stock=F("stock") - quantity
                )
                if not updated:
                    raise InsufficientStock(product)
                OrderLine.objects.create(order=order, product=product, quantity=quantity,
                                         unit_price=product.price)
    except InsufficientStock as e:
        return cart_response(request, c, f"“{e.product.name}” is no longer available in the requested quantity.")
    request.session.pop(CART_KEY, None)
    destination = reverse("shop:thanks", args=[order.pk])
    if request.htmx:
        return HttpResponseClientRedirect(destination)
    return redirect(destination)


def thanks(request, pk):
    order = get_object_or_404(Order, pk=pk)
    lines = order.lines.select_related("product")
    total = sum(l.unit_price * l.quantity for l in lines)
    return render(request, "shop/thanks.html", {"order": order, "lines": lines, "total": total})
