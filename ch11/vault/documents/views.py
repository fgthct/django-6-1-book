from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import permissions, rag, services
from .forms import AccessForm, ReviewForm, UploadForm
from .models import Document, Participant, Review


def _document(request, pk):
    """A document *the user can see*: the others, for them, don't exist (404, not 403)."""
    visible = Document.objects.visible_to(request.user).select_related("owner", "current_version")
    return get_object_or_404(visible, pk=pk)


@login_required
def document_list(request):
    documents = Document.objects.visible_to(request.user).select_related("owner", "current_version")
    return render(request, "documents/list.html", {"documents": documents, "form": UploadForm()})


def _flow(request, document):
    """Everything the flow panel needs: state, reviewers, buttons."""
    review = document.reviews.filter(status=Review.Status.OPEN).first()
    last = review or document.reviews.first()
    participants = list(last.participants.select_related("user")) if last else []
    level = permissions.level_of(request.user, document)
    can_decide = False
    if review is not None:
        pending = [p for p in participants if p.decision == Participant.Decision.PENDING]
        mine = next((p for p in participants if p.user_id == request.user.pk), None)
        if mine is not None and mine in pending:
            can_decide = review.mode == Review.Mode.FREE or pending[0].pk == mine.pk
    is_owner = level == permissions.OWNER
    return {
        "document": document,
        "review": review,
        "last_review": last,
        "participants": participants,
        "is_owner": is_owner,
        "can_decide": can_decide,
        "review_form": ReviewForm(owner=document.owner)
        if is_owner and document.state == Document.State.DRAFT
        else None,
    }


@login_required
def detail(request, pk):
    document = _document(request, pk)
    context = _flow(request, document)
    level = permissions.level_of(request.user, document)
    context.update(
        notices=list(messages.get_messages(request)),
        versions=document.versions.select_related("author"),
        events=document.events.select_related("user"),
        level=level,
        can_edit=level >= permissions.EDIT,
        upload_form=UploadForm(),
        access_form=AccessForm(owner=document.owner) if level == permissions.OWNER else None,
        accesses=document.accesses.select_related("user") if level == permissions.OWNER else [],
    )
    return render(request, "documents/detail.html", context)


def _flow_response(request, document):
    """After an action: HTMX browsers get just the flow fragment, the others a redirect."""
    if request.headers.get("HX-Request"):
        document = _document(request, document.pk)
        context = _flow(request, document)
        # With HTMX the page isn't reloaded: the messages (errors too!) have to be in the fragment.
        context["notices"] = list(messages.get_messages(request))
        return render(request, "documents/detail.html#flow", context)
    return redirect("detail", pk=document.pk)


def _run(request, document, action, success=""):
    """Run a service, turning a refusal by a rule into a message for the user."""
    try:
        action()
        if success:
            messages.success(request, success)
    except services.DomainError as error:
        messages.error(request, str(error))
    return _flow_response(request, document)


@login_required
@require_POST
def create(request):
    form = UploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Choose a file.")
        return redirect("list")
    try:
        document = services.create_document(
            request.user,
            form.cleaned_data["title"] or request.FILES["file"].name,
            request.FILES["file"],
            form.cleaned_data["note"],
        )
    except services.DomainError as error:
        messages.error(request, str(error))
        return redirect("list")
    return redirect("detail", pk=document.pk)


@login_required
@require_POST
def new_version(request, pk):
    document = _document(request, pk)
    form = UploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Choose a file.")
        return redirect("detail", pk=pk)
    try:
        services.upload_version(request.user, document, request.FILES["file"], form.cleaned_data["note"])
        messages.success(request, "New version uploaded.")
    except services.DomainError as error:
        messages.error(request, str(error))
    return redirect("detail", pk=pk)


@login_required
@require_POST
def send_for_review(request, pk):
    document = _document(request, pk)
    form = ReviewForm(request.POST, owner=document.owner)
    if not form.is_valid():
        messages.error(request, "Choose at least one reviewer.")
        return _flow_response(request, document)
    return _run(
        request,
        document,
        lambda: services.send_for_review(
            request.user, document, form.reviewers(), form.cleaned_data["mode"], form.cleaned_data["message"]
        ),
        "Sent for review.",
    )


@login_required
@require_POST
def decide(request, pk):
    document = _document(request, pk)
    approve = request.POST.get("decision") == "approve"
    return _run(
        request,
        document,
        lambda: services.decide(request.user, document, approve, request.POST.get("comment", "")),
        "Decision recorded.",
    )


@login_required
@require_POST
def cancel_review(request, pk):
    document = _document(request, pk)
    return _run(request, document, lambda: services.cancel_review(request.user, document), "Review cancelled.")


@login_required
@require_POST
def grant_access(request, pk):
    document = _document(request, pk)
    form = AccessForm(request.POST, owner=document.owner)
    if form.is_valid():
        try:
            services.grant_access(request.user, document, form.cleaned_data["user"], form.cleaned_data["level"])
        except services.DomainError as error:
            messages.error(request, str(error))
    return redirect("detail", pk=pk)


@login_required
@require_POST
def revoke_access(request, pk, user_id):
    document = _document(request, pk)
    access = get_object_or_404(document.accesses.select_related("user"), user_id=user_id)
    try:
        services.revoke_access(request.user, document, access.user)
    except services.DomainError as error:
        messages.error(request, str(error))
    return redirect("detail", pk=pk)


@login_required
def download(request, pk, number):
    document = _document(request, pk)
    version = get_object_or_404(document.versions, number=number)
    if version.file:
        return FileResponse(version.file.open("rb"), as_attachment=True, filename=version.file_name)
    # An imported version has no file: we generate it from the text.
    response = HttpResponse(version.text, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{version.file_name}"'
    return response


@login_required
def search_view(request):
    question = request.GET.get("q", "").strip()
    answer = rag.answer(request.user, question) if question else None
    return render(request, "documents/search.html", {"question": question, "answer": answer})
