import random
from concurrent.futures import ThreadPoolExecutor
from io import StringIO

import pytest
from django.core.management import call_command

from campaigns.importer import ImportResult, import_csv, import_contacts
from campaigns.models import Contact
from campaigns.validation import validate_block

from .helpers import write_csv


def serial_pool():
    return ThreadPoolExecutor(1)


def test_a_small_file_is_imported(tmp_path, db):
    f = write_csv(tmp_path / "c.csv", [("ana@example.com", "ana"), ("bruno@example.com", "bruno")])
    result = import_csv(f, executor=serial_pool)
    assert result.new == 2
    assert set(Contact.objects.values_list("email", "name")) == {("ana@example.com", "Ana"), ("bruno@example.com", "Bruno")}


def test_rejected_rows_are_counted_and_the_first_five_are_shown(tmp_path, db):
    f = write_csv(tmp_path / "c.csv", [(f"bad{i}", "x") for i in range(8)] + [("ok@example.com", "Ok")])
    result = import_csv(f, executor=serial_pool)
    assert result.rejected == 8
    assert len(result.rejected_examples) == 5
    assert result.rejected_examples[0] == "'bad0': invalid address"
    assert result.new == 1


def test_duplicates_across_two_blocks_are_detected(tmp_path, db):
    rows = [("same@example.com", "S")] + [(f"u{i}@example.com", "U") for i in range(5)] + [("SAME@example.com", "S")]
    f = write_csv(tmp_path / "c.csv", rows)
    result = import_csv(f, executor=serial_pool, block_size=3)
    assert result.duplicates_in_file == 1
    assert result.new == 6


def test_people_already_in_the_database_are_not_counted_as_new(tmp_path, db):
    Contact.objects.create(email="ana@example.com", name="Ana")
    f = write_csv(tmp_path / "c.csv", [("ana@example.com", "Ana"), ("bruno@example.com", "Bruno")])
    result = import_csv(f, executor=serial_pool)
    assert (result.new, result.already_present) == (1, 1)
    assert Contact.objects.count() == 2


def test_importing_twice_creates_nothing_the_second_time(tmp_path, db):
    f = write_csv(tmp_path / "c.csv", [("ana@example.com", "Ana")])
    import_csv(f, executor=serial_pool)
    second = import_csv(f, executor=serial_pool)
    assert (second.new, second.already_present) == (0, 1)


def test_the_subinterpreters_give_the_same_result_as_the_serial_run(tmp_path, db):
    """The property that matters: parallelizing does not change the answer."""
    chance = random.Random(7)
    dom = ["example.com", "bücher.example", "città.example"]
    rows = [
        (chance.choice([f"u{chance.randrange(300)}@{chance.choice(dom)}", "broken", " X@Y.IT "]), chance.choice(["ana", " ", "Gino  rossi"]))
        for _ in range(600)
    ]
    f = write_csv(tmp_path / "c.csv", rows)
    parallel = import_csv(f, block_size=50)  # default executor: subinterpreters
    Contact.objects.all().delete()
    in_thread = import_csv(f, executor=lambda: ThreadPoolExecutor(1), block_size=50)
    assert parallel == in_thread
    expected = [e for e in validate_block(rows)]
    assert parallel.rejected + parallel.duplicates_in_file + parallel.new == len(rows)
    assert parallel.rejected == sum(1 for e in expected if e[2])


def test_the_command_prints_a_summary(tmp_path, db):
    f = write_csv(tmp_path / "c.csv", [("ana@example.com", "Ana"), ("bad", "X")])
    out = StringIO()
    call_command("import_contacts", str(f), stdout=out)
    text = out.getvalue()
    assert "1 new" in text and "1 rejected" in text
    assert "rejected: 'bad': invalid address" in text


def test_the_import_task_returns_a_summary(tmp_path, db):
    f = write_csv(tmp_path / "c.csv", [("ana@example.com", "Ana")])
    assert import_contacts.call(path=str(f)) == "1 new, 0 already present, 0 rejected"
