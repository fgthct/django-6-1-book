import pytest

from articles.models import Category

from .helpers import make_article


@pytest.fixture
def categories(db):
    return {
        "food": Category.objects.create(name="Food", slug="food"),
        "nature": Category.objects.create(name="Nature", slug="nature"),
    }


@pytest.fixture
def articles(categories):
    return {
        "etna": make_article(
            "etna", "Climbing Etna",
            "We climbed the volcano by cable car. Sicily is beautiful.",
            tags=["etna", "hiking"], category=categories["nature"], day=0,
        ),
        "arancino": make_article(
            "arancino", "Arancino or arancina",
            "Sicilian rice balls from Catania, in the shadow of Etna.",
            tags=["food"], category=categories["food"], day=1,
        ),
        "theater": make_article(
            "theater", "Taormina and its Greek theater",
            "Etna smokes above the Greek theater.",
            tags=["taormina"], category=categories["nature"], day=2,
        ),
        "castle": make_article(
            "castle", "Ursino Castle",
            "Lava from Etna surrounded the castle.",
            tags=["catania"], category=categories["nature"], day=3,
        ),
        "cannolo": make_article(
            "cannolo", "The cannolo", "Crisp shell and ricotta cream.",
            tags=["food"], category=categories["food"], day=4,
        ),
        "draft": make_article(
            "draft", "Draft notes", "Remember the cannolo in Lipari.",
            published=False,
        ),
    }
