import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from documents import permissions
from documents.models import Access, Document

from .conftest import text_file


def test_the_owner_has_the_owner_level(doc, marta):
    assert permissions.level_of(marta, doc) == permissions.OWNER


def test_without_an_access_the_level_is_none(doc, paolo):
    assert permissions.level_of(paolo, doc) == permissions.NONE


def test_an_access_gives_its_level(doc, luca, giulia, grant):
    grant(doc, luca, Access.Level.READ)
    grant(doc, giulia, Access.Level.EDIT)
    assert permissions.level_of(luca, doc) == permissions.READ
    assert permissions.level_of(giulia, doc) == permissions.EDIT


def test_no_access_can_grant_the_owner_level():
    assert max(Access.Level.values) < permissions.OWNER


def test_a_reader_cannot_edit(doc, luca, grant):
    grant(doc, luca, Access.Level.READ)
    with pytest.raises(PermissionDenied):
        permissions.require(luca, doc, permissions.EDIT)


def test_a_higher_level_satisfies_a_lower_requirement(doc, luca, marta, grant):
    grant(doc, luca, Access.Level.EDIT)
    permissions.require(luca, doc, permissions.READ)
    permissions.require(luca, doc, permissions.EDIT)
    permissions.require(marta, doc, permissions.EDIT)


def test_the_owner_sees_their_own_documents(doc, marta):
    assert list(Document.objects.visible_to(marta)) == [doc]


def test_a_stranger_sees_nothing(doc, paolo):
    assert not Document.objects.visible_to(paolo).exists()


def test_whoever_has_an_access_sees_the_document(doc, luca, grant):
    grant(doc, luca)
    assert list(Document.objects.visible_to(luca)) == [doc]


def test_an_access_to_another_document_does_not_count(doc, luca, marta, grant):
    other = Document.objects.create(title="Other", owner=marta)
    grant(other, luca)
    assert not Document.objects.visible_to(luca).filter(pk=doc.pk).exists()


def test_the_list_only_shows_visible_documents(client, doc, paolo):
    client.force_login(paolo)
    assert doc.title not in client.get(reverse("list")).text


def test_an_invisible_document_is_a_404_not_a_403(client, doc, paolo):
    client.force_login(paolo)
    assert client.get(reverse("detail", args=[doc.pk])).status_code == 404


def test_an_invisible_documents_download_is_a_404(client, doc, paolo):
    client.force_login(paolo)
    assert client.get(reverse("download", args=[doc.pk, 1])).status_code == 404


def test_even_a_post_on_an_invisible_document_is_a_404(client, doc, paolo):
    client.force_login(paolo)
    response = client.post(reverse("new_version", args=[doc.pk]), {"file": text_file("hack")})
    assert response.status_code == 404
    response = client.post(reverse("decide", args=[doc.pk]), {"decision": "approve"})
    assert response.status_code == 404


def test_a_visible_document_with_too_low_a_level_is_a_403(client, doc, luca, grant):
    grant(doc, luca, Access.Level.READ)
    client.force_login(luca)
    response = client.post(reverse("new_version", args=[doc.pk]), {"file": text_file("a different text")})
    assert response.status_code == 403
