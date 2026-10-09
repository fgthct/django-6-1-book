from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

START = "⟦"
END = "⟧"


@register.filter
def highlight(text):
    """Convert SearchHeadline placeholders into <mark>, after escaping."""
    safe = escape(text).replace(START, "<mark>").replace(END, "</mark>")
    return mark_safe(safe)
