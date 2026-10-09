import threading

import pytest
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, connections, transaction

from documents import services
from documents.models import Access, Document, Participant, Review

from .conftest import FREE, SEQ, make_user, text_file


def committed(capture):
    return capture(execute=True)


# --- sending ------------------------------------------------------------------------------------


def test_the_owner_sends_a_draft_for_review(doc, marta, luca, giulia):
    review = services.send_for_review(marta, doc, [luca, giulia], SEQ, "Please read it by Friday.")
    doc.refresh_from_db()
    assert doc.state == Document.State.IN_REVIEW
    assert review.version == doc.current_version
    assert review.status == Review.Status.OPEN
    assert [(p.user, p.order) for p in review.participants.all()] == [(luca, 1), (giulia, 2)]


def test_only_the_owner_chooses_the_reviewers(doc, luca, giulia, grant):
    grant(doc, luca, Access.Level.EDIT)
    with pytest.raises(PermissionDenied):
        services.send_for_review(luca, doc, [giulia], SEQ)


def test_the_owner_cannot_be_a_reviewer(doc, marta, luca):
    with pytest.raises(services.DomainError, match="your own documents"):
        services.send_for_review(marta, doc, [luca, marta], SEQ)


def test_the_same_reviewer_twice_is_refused(doc, marta, luca):
    with pytest.raises(services.DomainError, match="twice"):
        services.send_for_review(marta, doc, [luca, luca], SEQ)


def test_at_least_one_reviewer_is_needed(doc, marta):
    with pytest.raises(services.DomainError, match="at least one"):
        services.send_for_review(marta, doc, [], SEQ)


def test_there_is_a_limit_to_the_number_of_reviewers(doc, marta, settings):
    users = [make_user(f"r{n}", "R", str(n)) for n in range(settings.MAX_REVIEWERS + 1)]
    with pytest.raises(services.DomainError, match="At most"):
        services.send_for_review(marta, doc, users, SEQ)
    services.send_for_review(marta, doc, users[: settings.MAX_REVIEWERS], SEQ)


def test_reviewers_receive_read_access(doc, marta, luca, giulia, paolo):
    services.send_for_review(marta, doc, [luca, giulia], SEQ)
    assert Access.objects.filter(document=doc, user__in=[luca, giulia]).count() == 2
    assert not Access.objects.filter(document=doc, user=paolo).exists()


def test_only_a_draft_can_be_sent(doc, marta, luca, giulia):
    services.send_for_review(marta, doc, [luca], SEQ)
    with pytest.raises(services.DomainError, match="Only a draft"):
        services.send_for_review(marta, doc, [giulia], SEQ)


def test_a_second_open_review_is_impossible_even_skipping_the_services(doc, marta, luca):
    services.send_for_review(marta, doc, [luca], SEQ)
    with pytest.raises(IntegrityError), transaction.atomic():
        Review.objects.create(document=doc, version=doc.current_version)


def test_many_closed_reviews_are_fine(doc, marta, luca):
    for _ in range(3):
        services.send_for_review(marta, doc, [luca], FREE)
        services.decide(luca, doc, False, "no")
    assert doc.reviews.filter(status=Review.Status.SENT_BACK).count() == 3


# --- who is notified ---------------------------------------------------------------------------


def test_in_sequence_only_the_first_reviewer_is_notified_at_the_start(
    doc, marta, luca, giulia, mailoutbox, django_capture_on_commit_callbacks
):
    with committed(django_capture_on_commit_callbacks):
        services.send_for_review(marta, doc, [luca, giulia], SEQ)
    assert [m.to for m in mailoutbox] == [["luca@example.test"]]


def test_in_free_mode_everybody_is_notified_at_the_start(
    doc, marta, luca, giulia, mailoutbox, django_capture_on_commit_callbacks
):
    with committed(django_capture_on_commit_callbacks):
        services.send_for_review(marta, doc, [luca, giulia], FREE)
    assert sorted(m.to[0] for m in mailoutbox) == ["giulia@example.test", "luca@example.test"]


def test_the_owners_message_reaches_the_reviewers(doc, marta, luca, mailoutbox, django_capture_on_commit_callbacks):
    with committed(django_capture_on_commit_callbacks):
        services.send_for_review(marta, doc, [luca], SEQ, "Mind the third paragraph.")
    assert "Mind the third paragraph." in mailoutbox[0].body
    assert "Vacation policy" in mailoutbox[0].subject


def test_each_reviewer_gets_a_separate_message(
    doc, marta, luca, giulia, mailoutbox, django_capture_on_commit_callbacks
):
    with committed(django_capture_on_commit_callbacks):
        services.send_for_review(marta, doc, [luca, giulia], FREE)
    assert len(mailoutbox) == 2
    assert all(len(m.to) == 1 for m in mailoutbox)


def test_nothing_is_sent_before_the_commit(doc, marta, luca, mailoutbox, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        services.send_for_review(marta, doc, [luca], SEQ)
    assert mailoutbox == []
    assert len(callbacks) == 1


def test_a_rolled_back_transaction_notifies_nobody(doc, marta, luca, mailoutbox, django_capture_on_commit_callbacks):
    with (
        django_capture_on_commit_callbacks(execute=True) as callbacks,
        pytest.raises(RuntimeError),
        transaction.atomic(),
    ):
        services.send_for_review(marta, doc, [luca], SEQ)
        raise RuntimeError("the transaction fails after the notification was prepared")
    assert callbacks == []
    assert mailoutbox == []


def test_a_user_without_an_email_is_skipped_silently(doc, marta, luca, django_capture_on_commit_callbacks):
    from documents.tasks import send_notice

    luca.email = ""
    luca.save()
    assert send_notice.call(user_ids=[luca.pk, marta.pk], subject="s", body="b") == 1


# --- decisions ---------------------------------------------------------------------------------


def test_in_sequence_the_second_reviewer_cannot_go_first(doc, marta, luca, giulia):
    services.send_for_review(marta, doc, [luca, giulia], SEQ)
    with pytest.raises(services.DomainError, match="not your turn"):
        services.decide(giulia, doc, True)


def test_in_sequence_the_document_is_approved_after_the_last_reviewer(
    doc, marta, luca, giulia, mailoutbox, django_capture_on_commit_callbacks
):
    services.send_for_review(marta, doc, [luca, giulia], SEQ, "Thanks.")
    with committed(django_capture_on_commit_callbacks):
        services.decide(luca, doc, True)
    doc.refresh_from_db()
    assert doc.state == Document.State.IN_REVIEW
    assert [(m.to, m.subject) for m in mailoutbox] == [(["giulia@example.test"], "Your turn: Vacation policy")]
    with committed(django_capture_on_commit_callbacks):
        services.decide(giulia, doc, True)
    doc.refresh_from_db()
    assert doc.state == Document.State.APPROVED
    assert mailoutbox[-1].to == ["marta@example.test"]
    assert doc.reviews.get().status == Review.Status.APPROVED


def test_in_free_mode_the_first_approval_concludes_and_the_others_are_superseded(doc, marta, luca, giulia):
    services.send_for_review(marta, doc, [luca, giulia], FREE)
    services.decide(giulia, doc, True)
    doc.refresh_from_db()
    assert doc.state == Document.State.APPROVED
    luca_row = Participant.objects.get(user=luca)
    assert luca_row.decision == Participant.Decision.SUPERSEDED
    with pytest.raises(services.DomainError, match="no open review"):
        services.decide(luca, doc, True)


def test_sending_back_needs_a_comment(doc, marta, luca):
    services.send_for_review(marta, doc, [luca], SEQ)
    with pytest.raises(services.DomainError, match="comment"):
        services.decide(luca, doc, False, "   ")


def test_sending_back_returns_the_document_to_draft_and_tells_the_owner(
    doc, marta, luca, giulia, mailoutbox, django_capture_on_commit_callbacks
):
    services.send_for_review(marta, doc, [luca, giulia], SEQ)
    with committed(django_capture_on_commit_callbacks):
        services.decide(luca, doc, False, "The numbers don't add up.")
    doc.refresh_from_db()
    assert doc.state == Document.State.DRAFT
    assert doc.reviews.get().status == Review.Status.SENT_BACK
    assert Participant.objects.get(user=giulia).decision == Participant.Decision.SUPERSEDED
    assert mailoutbox[-1].to == ["marta@example.test"]
    assert "The numbers don't add up." in mailoutbox[-1].body


def test_you_cannot_decide_twice(doc, marta, luca, giulia):
    services.send_for_review(marta, doc, [luca, giulia], SEQ)
    services.decide(luca, doc, True)
    with pytest.raises(services.DomainError, match="already decided"):
        services.decide(luca, doc, True)


def test_whoever_is_not_a_reviewer_cannot_decide(doc, marta, luca, paolo):
    services.send_for_review(marta, doc, [luca], SEQ)
    with pytest.raises(PermissionDenied):
        services.decide(paolo, doc, True)


def test_deciding_without_an_open_review_is_refused(doc, luca):
    with pytest.raises(services.DomainError, match="no open review"):
        services.decide(luca, doc, True)


@pytest.mark.django_db(transaction=True)
def test_two_free_reviewers_approving_together_only_one_wins(marta, luca, giulia):
    doc = services.create_document(marta, "Race", text_file("text"))
    services.send_for_review(marta, doc, [luca, giulia], FREE)
    outcomes, barrier = [], threading.Barrier(2)

    def approve(user):
        try:
            barrier.wait()
            services.decide(user, doc, True)
            outcomes.append("ok")
        except services.DomainError as error:
            outcomes.append(str(error))
        finally:
            connections.close_all()

    threads = [threading.Thread(target=approve, args=(u,)) for u in (luca, giulia)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(outcomes)[1] == "ok" and "already been concluded" in sorted(outcomes)[0]
    assert Participant.objects.filter(decision="approved").count() == 1
    doc.refresh_from_db()
    assert doc.state == Document.State.APPROVED


# --- cancelling and accesses -------------------------------------------------------------------


def test_the_owner_cancels_a_review(doc, marta, luca):
    services.send_for_review(marta, doc, [luca], SEQ)
    services.cancel_review(marta, doc)
    doc.refresh_from_db()
    assert doc.state == Document.State.DRAFT
    assert doc.reviews.get().status == Review.Status.CANCELLED
    assert Participant.objects.get().decision == Participant.Decision.SUPERSEDED


def test_nobody_else_can_cancel_a_review(doc, marta, luca, giulia, grant):
    grant(doc, giulia, Access.Level.EDIT)
    services.send_for_review(marta, doc, [luca], SEQ)
    for user in (luca, giulia):
        with pytest.raises(PermissionDenied):
            services.cancel_review(user, doc)


def test_cancelling_without_an_open_review_is_refused(doc, marta):
    with pytest.raises(services.DomainError, match="no open review"):
        services.cancel_review(marta, doc)


def test_you_cannot_revoke_the_access_of_a_reviewer_while_the_review_is_open(doc, marta, luca):
    services.send_for_review(marta, doc, [luca], SEQ)
    with pytest.raises(services.DomainError, match="reviewer"):
        services.revoke_access(marta, doc, luca)
    services.cancel_review(marta, doc)
    services.revoke_access(marta, doc, luca)
    assert not Access.objects.filter(user=luca).exists()


def test_only_the_owner_grants_and_revokes_accesses(doc, marta, luca, giulia, grant):
    grant(doc, luca, Access.Level.EDIT)
    with pytest.raises(PermissionDenied):
        services.grant_access(luca, doc, giulia, Access.Level.READ)
    services.grant_access(marta, doc, giulia, Access.Level.READ)
    with pytest.raises(PermissionDenied):
        services.revoke_access(luca, doc, giulia)
    assert Access.objects.filter(user=giulia).count() == 1
