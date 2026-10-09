import pytest

from campaigns.validation import validate_block


def one(email, name="Ana"):
    return validate_block([(email, name)])[0]


def test_a_valid_row_comes_back_normalized():
    assert one("  Ana@Example.COM ", "  ana   rossi ") == ("ana@example.com", "Ana Rossi", None)


def test_unicode_compatibility_forms_are_normalized_in_the_email():
    # the full-width "ａ" (U+FF41) becomes a plain "a" with NFKC
    assert one("ａna@example.com")[0] == "ana@example.com"


def test_an_international_domain_becomes_punycode():
    assert one("ana@bücher.example")[0] == "ana@xn--bcher-kva.example"


@pytest.mark.parametrize("email", ["broken", "ana@", "@example.com", "ana@example", "a b@example.com"])
def test_an_invalid_address_is_rejected(email):
    assert one(email)[::2] == (None, "invalid address")


def test_an_invalid_domain_is_rejected():
    assert one("ana@" + "a" * 70 + ".example")[::2] == (None, "invalid domain")


def test_a_missing_name_is_rejected():
    assert one("ana@example.com", "   ")[::2] == (None, "missing name")


def test_the_name_is_cleaned_even_when_the_row_is_rejected():
    assert one("broken", "  gino  ROSSI")[1] == "Gino Rossi"


def test_the_function_works_on_a_whole_block_and_keeps_the_order():
    rows = [("a@example.com", "A"), ("bad", "B"), ("c@example.com", "C")]
    assert [o[0] for o in validate_block(rows)] == ["a@example.com", None, "c@example.com"]
