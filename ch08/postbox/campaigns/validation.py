"""Pure Python, no Django: it has to run inside a subinterpreter where
Django is not configured."""

import re
import unicodedata

_EMAIL = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9-]+(\.[a-z0-9-]+)+$")


def validate_block(rows: list[tuple[str, str]]) -> list[tuple[str | None, str, str | None]]:
    """For each (email, name) row returns (normalized email, name, error).

    If the row is not valid the email is `None` and the error says why.
    """
    outcomes = []
    for email, name in rows:
        clean_name = " ".join(unicodedata.normalize("NFKC", name).split()).title()
        raw = unicodedata.normalize("NFKC", email).strip().lower()
        local, _, domain = raw.rpartition("@")
        try:
            # International domains (e.g. "bücher.example") travel as punycode.
            ascii_domain = domain.encode("idna").decode("ascii")
        except UnicodeError:
            outcomes.append((None, clean_name, "invalid domain"))
            continue
        normalized = f"{local}@{ascii_domain}"
        if not _EMAIL.match(normalized):
            outcomes.append((None, clean_name, "invalid address"))
        elif not clean_name:
            outcomes.append((None, clean_name, "missing name"))
        else:
            outcomes.append((normalized, clean_name, None))
    return outcomes
