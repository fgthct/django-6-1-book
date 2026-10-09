import pytest
from django.urls import reverse

from campaigns.models import Campaign, Contact, Delivery


@pytest.fixture
def draft(db):
    return Campaign.objects.create(subject="News", body="Hi {name}")


def test_the_index_lists_the_campaigns(client, campaign):
    response = client.get(reverse("index"))
    assert "Autumn news" in response.content.decode()


def test_a_campaign_is_created_as_a_draft(client, db):
    response = client.post(reverse("create"), {"subject": "S", "body": "B {name}"})
    campaign = Campaign.objects.get()
    assert campaign.status == Campaign.Status.DRAFT
    assert response.status_code == 302


def test_start_moves_the_draft_to_sending_and_enqueues_the_preparation(client, draft, fake_queue, django_capture_on_commit_callbacks):
    campaign = draft
    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("start", args=[campaign.pk]))
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.SENDING
    assert campaign.started_at is not None
    (queued,) = fake_queue.results
    assert queued.kwargs == {"campaign_id": campaign.pk}


def test_pressing_start_twice_enqueues_only_once(client, draft, fake_queue, django_capture_on_commit_callbacks):
    campaign = draft
    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("start", args=[campaign.pk]))
        client.post(reverse("start", args=[campaign.pk]))
    assert len(fake_queue.results) == 1


def test_nothing_is_enqueued_before_the_commit(client, draft, fake_queue):
    campaign = draft
    client.post(reverse("start", args=[campaign.pk]))  # callbacks not executed
    assert fake_queue.results == []


def test_start_only_accepts_post(client, draft):
    campaign = draft
    assert client.get(reverse("start", args=[campaign.pk])).status_code == 405


def counts_page(client, campaign):
    return client.get(reverse("progress", args=[campaign.pk])).content.decode()


def test_the_percentage_counts_the_failed_ones_too(client, campaign):
    for i, status in enumerate([Delivery.Status.SENT, Delivery.Status.FAILED, Delivery.Status.PENDING, Delivery.Status.PENDING]):
        c = Contact.objects.create(email=f"u{i}@example.com", name="U")
        Delivery.objects.create(campaign=campaign, contact=c, status=status)
    assert 'value="50"' in counts_page(client, campaign)


def test_the_progress_fragment_shows_the_counts(client, campaign):
    c = Contact.objects.create(email="u@example.com", name="U")
    Delivery.objects.create(campaign=campaign, contact=c, status=Delivery.Status.SENT)
    page = counts_page(client, campaign)
    assert "1 sent · 0 pending · 0 failed" in page
    assert "(of 1)" in page


def test_while_sending_the_fragment_asks_for_its_own_update(client, campaign):
    assert 'hx-trigger="every 2s"' in counts_page(client, campaign)


def test_when_completed_the_polling_disappears(client, campaign):
    Campaign.objects.filter(pk=campaign.pk).update(status=Campaign.Status.COMPLETED)
    page = counts_page(client, campaign)
    assert "hx-trigger" not in page
    assert "Completed" in page


def test_the_fragment_is_not_a_whole_page(client, campaign):
    assert "<html" not in counts_page(client, campaign)
    full = client.get(reverse("detail", args=[campaign.pk])).content.decode()
    assert "<html" in full and 'id="progress"' in full


def test_an_empty_campaign_shows_zero_percent(client, campaign):
    assert 'value="0"' in counts_page(client, campaign)
