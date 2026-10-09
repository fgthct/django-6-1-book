from campaigns.models import Campaign, Contact, Delivery
from campaigns.tasks import prepare_deliveries, send_delivery


def test_it_creates_one_delivery_for_every_active_contact(campaign, fake_queue):
    Contact.objects.create(email="a@example.com", name="A")
    Contact.objects.create(email="b@example.com", name="B")
    assert prepare_deliveries.call(campaign_id=campaign.pk) == 2
    assert campaign.deliveries.count() == 2


def test_inactive_contacts_get_nothing(campaign, fake_queue):
    Contact.objects.create(email="a@example.com", name="A")
    Contact.objects.create(email="off@example.com", name="Off", active=False)
    prepare_deliveries.call(campaign_id=campaign.pk)
    assert list(campaign.deliveries.values_list("contact__email", flat=True)) == ["a@example.com"]


def test_it_enqueues_one_send_for_each_delivery(campaign, fake_queue):
    Contact.objects.create(email="a@example.com", name="A")
    Contact.objects.create(email="b@example.com", name="B")
    prepare_deliveries.call(campaign_id=campaign.pk)
    pks = sorted(d.pk for d in campaign.deliveries.all())
    queued = sorted(r.kwargs["delivery_id"] for r in fake_queue.results)
    assert queued == pks
    assert {r.task.func for r in fake_queue.results} == {send_delivery.func}


def test_it_can_run_twice_without_duplicating_anything(campaign, fake_queue):
    Contact.objects.create(email="a@example.com", name="A")
    prepare_deliveries.call(campaign_id=campaign.pk)
    prepare_deliveries.call(campaign_id=campaign.pk)
    assert campaign.deliveries.count() == 1


def test_it_does_not_enqueue_what_is_already_closed(campaign, fake_queue):
    contact = Contact.objects.create(email="a@example.com", name="A")
    Delivery.objects.create(campaign=campaign, contact=contact, status=Delivery.Status.SENT)
    assert prepare_deliveries.call(campaign_id=campaign.pk) == 0
    assert fake_queue.results == []


def test_it_does_nothing_if_the_campaign_is_not_sending(campaign, fake_queue):
    Contact.objects.create(email="a@example.com", name="A")
    Campaign.objects.filter(pk=campaign.pk).update(status=Campaign.Status.DRAFT)
    assert prepare_deliveries.call(campaign_id=campaign.pk) == 0
    assert campaign.deliveries.count() == 0


def test_with_no_active_contacts_the_campaign_is_finished_right_away(campaign, fake_queue):
    prepare_deliveries.call(campaign_id=campaign.pk)
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.COMPLETED
