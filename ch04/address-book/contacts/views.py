from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.vary import vary_on_headers

from .forms import ContactForm
from .models import Contact

PAGE_SIZE = 10


def list_context(request, form=None):
    q = request.GET.get("q", "").strip()
    contacts = Contact.objects.all()
    if q:
        contacts = contacts.filter(
            Q(name__icontains=q) | Q(email__icontains=q) | Q(city__icontains=q)
        )
    page = Paginator(contacts, PAGE_SIZE).get_page(request.GET.get("page"))
    return {
        "page": page,
        "q": q,
        "total": Contact.objects.count(),
        "form": form or ContactForm(),
    }


def is_partial_request(request):
    """True if the browser wants only a fragment, not the full page."""
    return bool(request.htmx) and not request.htmx.history_restore_request


@vary_on_headers("HX-Request")
def contact_list(request):
    context = list_context(request)
    if is_partial_request(request):
        return render(request, "contacts/list.html#rows", context)
    return render(request, "contacts/list.html", context)


def count(request):
    return render(request, "contacts/list.html#count", {"total": Contact.objects.count()})


def detail(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    return render(request, "contacts/list.html#detail", {"contact": contact})


def row(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    return render(request, "contacts/list.html#row", {"contact": contact})


@require_http_methods(["GET", "POST"])
def edit(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    if request.method == "POST":
        form = ContactForm(request.POST, instance=contact)
        if form.is_valid():
            contact = form.save()
            return render(request, "contacts/list.html#row", {"contact": contact})
    else:
        form = ContactForm(instance=contact)
    context = {"contact": contact, "form": form}
    return render(request, "contacts/list.html#row_edit", context)


@require_POST
def new(request):
    form = ContactForm(request.POST)
    if not form.is_valid():
        if request.htmx:
            return render(request, "contacts/list.html#new_form", {"form": form})
        return render(request, "contacts/list.html", list_context(request, form))
    contact = form.save()
    if not request.htmx:
        return redirect("contacts:list")
    context = {
        "contact": contact,
        "form": ContactForm(),
        "total": Contact.objects.count(),
    }
    return render(request, "contacts/new_response.html", context)


@require_http_methods(["DELETE"])
def delete(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    contact.delete()
    return HttpResponse("", headers={"HX-Trigger": "contactsChanged"})
