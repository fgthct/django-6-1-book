import pytest
from django.db import IntegrityError, transaction

from campaigns.models import Delivery


def test_two_deliveries_for_the_same_person_in_the_same_campaign_are_impossible(delivery):
    with pytest.raises(IntegrityError), transaction.atomic():
        Delivery.objects.create(campaign=delivery.campaign, contact=delivery.contact)


def test_the_same_person_can_be_in_two_campaigns(delivery, db):
    from campaigns.models import Campaign

    other = Campaign.objects.create(subject="Other", body="x")
    Delivery.objects.create(campaign=other, contact=delivery.contact)
    assert delivery.contact.deliveries.count() == 2


def test_the_default_status_is_pending(delivery):
    assert delivery.status == Delivery.Status.PENDING
    assert delivery.attempts == 0


def test_the_campaign_is_printed_with_its_subject(campaign):
    assert str(campaign) == "Autumn news"
