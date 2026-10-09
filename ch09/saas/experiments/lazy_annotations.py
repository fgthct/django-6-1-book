"""Lazy annotations: TicketOut uses MemberOut, which is defined AFTER it."""
import annotationlib

import django

django.setup()
from helpdesk.api import MemberOut, TicketOut  # noqa

print("field 'assigned' of TicketOut :", TicketOut.__pydantic_fields__["assigned"].annotation)
raw = annotationlib.get_annotations(TicketOut, format=annotationlib.Format.FORWARDREF)
print("raw annotations (FORWARDREF):", {"assigned": raw["assigned"]})
print("TicketOut is defined before MemberOut in the file, and yet:", TicketOut.model_json_schema()["properties"]["assigned"])
