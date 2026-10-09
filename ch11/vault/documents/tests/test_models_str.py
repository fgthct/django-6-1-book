import pytest

from documents import services
from documents.models import Access, Chunk, Event, Participant

from .conftest import SEQ


@pytest.mark.django_db
def test_every_model_has_a_readable_name(doc, marta, luca):
    services.grant_access(marta, doc, luca, Access.Level.EDIT)
    review = services.send_for_review(marta, doc, [luca], SEQ)
    chunk = Chunk.objects.create(version=doc.current_version, position=1, text="x")
    names = [
        str(doc),
        str(doc.current_version),
        str(Access.objects.get()),
        str(review),
        str(Participant.objects.get()),
        str(Event.objects.first()),
        str(chunk),
    ]
    assert names[0] == "Vacation policy"
    assert all("object (" not in name for name in names), names
