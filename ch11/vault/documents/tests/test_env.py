import pytest
from django.core.exceptions import ImproperlyConfigured

from config import env


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "Yes", " on "])
def test_the_true_spellings(monkeypatch, value):
    monkeypatch.setenv("FLAG", value)
    assert env.boolean("FLAG", False) is True


@pytest.mark.parametrize("value", ["0", "false", "False", "NO", "off"])
def test_the_false_spellings(monkeypatch, value):
    monkeypatch.setenv("FLAG", value)
    assert env.boolean("FLAG", True) is False


def test_a_missing_or_empty_value_uses_the_default(monkeypatch):
    monkeypatch.delenv("FLAG", raising=False)
    assert env.boolean("FLAG", True) is True
    monkeypatch.setenv("FLAG", "   ")
    assert env.boolean("FLAG", False) is False


def test_an_incomprehensible_boolean_stops_everything(monkeypatch):
    monkeypatch.setenv("FLAG", "maybe")
    with pytest.raises(ImproperlyConfigured, match="FLAG='maybe'"):
        env.boolean("FLAG", False)


def test_integers(monkeypatch):
    monkeypatch.setenv("NUMBER", " 42 ")
    assert env.integer("NUMBER", 1) == 42
    monkeypatch.delenv("NUMBER")
    assert env.integer("NUMBER", 1) == 1
    monkeypatch.setenv("NUMBER", "many")
    with pytest.raises(ImproperlyConfigured, match="NUMBER"):
        env.integer("NUMBER", 1)


def test_lists_drop_spaces_and_empty_items(monkeypatch):
    monkeypatch.setenv("ITEMS", " a, b ,,c, ")
    assert env.comma_list("ITEMS") == ["a", "b", "c"]
    monkeypatch.delenv("ITEMS")
    assert env.comma_list("ITEMS", ["x"]) == ["x"]
    assert env.comma_list("ITEMS") == []


def test_a_required_variable_must_exist_and_not_be_empty(monkeypatch):
    monkeypatch.delenv("SECRET", raising=False)
    with pytest.raises(ImproperlyConfigured, match="SECRET is missing"):
        env.required("SECRET")
    monkeypatch.setenv("SECRET", "  ")
    with pytest.raises(ImproperlyConfigured):
        env.required("SECRET")
    monkeypatch.setenv("SECRET", "value")
    assert env.required("SECRET") == "value"
