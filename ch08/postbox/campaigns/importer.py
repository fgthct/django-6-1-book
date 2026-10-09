import csv
import site
from concurrent.futures import InterpreterPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.tasks import task

from .models import Contact
from .validation import validate_block


@dataclass
class ImportResult:
    new: int = 0
    already_present: int = 0
    rejected: int = 0
    duplicates_in_file: int = 0
    rejected_examples: list[str] = field(default_factory=list)


def subinterpreter_pool() -> InterpreterPoolExecutor:
    """A subinterpreter starts with its own `sys.path`, decided when the process starts.

    Inside the tests, or under another server, the project folder might
    not be there, and then `campaigns.validation` can't be found: we tell
    every subinterpreter ourselves, with a standard-library function that knows how.
    """
    return InterpreterPoolExecutor(initializer=site.addsitedir, initargs=(str(settings.BASE_DIR),))


def read_rows(path: Path) -> list[tuple[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = [(r[0], r[1] if len(r) > 1 else "") for r in csv.reader(f) if r]
    if rows and rows[0][0].strip().lower() == "email":
        rows = rows[1:]
    return rows


def import_csv(path, executor=subinterpreter_pool, block_size: int = 5000) -> ImportResult:
    rows = read_rows(Path(path))
    blocks = [rows[i : i + block_size] for i in range(0, len(rows), block_size)]
    result = ImportResult()
    seen: dict[str, str] = {}
    with executor() as pool:
        for block, outcomes in zip(blocks, pool.map(validate_block, blocks)):
            for (raw_email, _), (email, name, error) in zip(block, outcomes):
                if error:
                    result.rejected += 1
                    if len(result.rejected_examples) < 5:
                        result.rejected_examples.append(f"{raw_email!r}: {error}")
                elif email in seen:
                    result.duplicates_in_file += 1
                else:
                    seen[email] = name
    with transaction.atomic():
        present = set(Contact.objects.filter(email__in=seen).values_list("email", flat=True))
        result.already_present = len(present)
        Contact.objects.bulk_create(
            [Contact(email=e, name=n) for e, n in seen.items() if e not in present]
        )
        result.new = len(seen) - len(present)
    return result


@task
def import_contacts(path: str) -> str:
    r = import_csv(path)
    return f"{r.new} new, {r.already_present} already present, {r.rejected} rejected"
