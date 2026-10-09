from datetime import datetime, timedelta, timezone

from django.core.management.base import BaseCommand

from articles.models import Article, Category

CATEGORIES = [("Food", "food"), ("Nature", "nature"), ("History", "history")]

# (slug, category, title, summary, body, tags, published)
ARTICLES = [
    (
        "arancino-or-arancina", "food", "Arancino or arancina? The great debate",
        "Rice balls, two names, one island-wide argument.",
        "In Palermo they say arancina and shape it round, like an orange. In Catania it is an "
        "arancino, cone-shaped like Etna, the volcano that looms over the city. Both are Sicilian "
        "rice balls, breaded and fried, filled with ragù and peas or with ham and cheese. The "
        "argument has no winner, and whichever word you choose, someone will correct you within "
        "the hour. Order one of each and decide for yourself.",
        ["food", "catania", "palermo"], True,
    ),
    (
        "climbing-mount-etna", "nature", "Climbing Mount Etna",
        "What to know before you climb Europe's most active volcano.",
        "Etna rises more than 3,300 meters above the Ionian coast. You can drive or take the cable "
        "car to about 2,500 meters, then continue on foot with a guide up to the craters. The climb "
        "is steady rather than steep, but the weather changes fast, so bring layers. In the hottest "
        "weeks of the Sicilian summer the early morning is the best time to go. Never walk past the "
        "barriers the guides set: the volcano is alive.",
        ["etna", "hiking", "volcano"], True,
    ),
    (
        "taormina-greek-theater", "history", "Taormina and Its Greek Theater",
        "A theater with the best view in Sicily.",
        "The theater of Taormina was built by the Greeks and rebuilt by the Romans. From the upper "
        "rows you can see the coast curve south toward Catania, with Etna smoking above it. "
        "Concerts are still held here every summer.",
        ["taormina", "ruins"], True,
    ),
    (
        "ursino-castle", "history", "Ursino Castle",
        "A medieval fortress that the sea left behind.",
        "Frederick II built Castello Ursino in the thirteenth century, on a cliff above the water. "
        "In 1669 lava from Etna surrounded it, and the coastline moved a mile to the west, leaving "
        "the castle inland. Today it houses the civic museum of Catania.",
        ["catania", "castle"], True,
    ),
    (
        "lava-stone-in-catanias-architecture", "history", "Lava Stone in Catania's Architecture",
        "Black stone from the volcano built the city.",
        "After the eruption of 1669 and the earthquake of 1693, Catania was rebuilt in black lava "
        "stone and white limestone. The facades of the baroque palaces owe their dark color to the "
        "lava of Etna that once threatened the city. Look at the cathedral square: even the "
        "elephant fountain is carved from lava.",
        ["catania", "architecture", "lava"], True,
    ),
    (
        "alcantara-gorges", "nature", "The Alcantara Gorges",
        "A river canyon carved into ancient basalt.",
        "At the foot of Etna, the river Alcantara runs through a gorge of black basalt, formed when "
        "an old lava flow met cold water and cracked into columns. In summer you can wade upstream "
        "between walls ten meters high. The water is icy even in August.",
        ["etna", "hiking", "river"], True,
    ),
    (
        "pasta-alla-norma", "food", "Pasta alla Norma",
        "Eggplant, tomato, and salted ricotta.",
        "Pasta alla Norma is the dish of Catania: short pasta with fried eggplant, tomato sauce, "
        "basil, and grated ricotta salata. It is named, the story goes, after Bellini's opera. Some "
        "cooks say the eggplant should be as dark as the lava stone of the city and the ricotta as "
        "white as the snow on Etna.",
        ["food", "catania", "pasta"], True,
    ),
    (
        "the-sicilian-cannolo", "food", "The Sicilian Cannolo",
        "Crisp shell, sweet ricotta.",
        "A good cannolo is filled to order, so the shell stays crisp. The cream is sheep's milk "
        "ricotta sweetened with sugar and flavored with candied orange and chocolate chips. Avoid "
        "any pastry shop that fills its cannoli in the morning.",
        ["food", "dessert"], True,
    ),
    (
        "granita-and-brioche", "food", "Granita and Brioche for Breakfast",
        "Summer breakfast, eastern Sicily style.",
        "In summer, breakfast in eastern Sicily is a granita, almond or coffee or lemon, with a "
        "warm brioche to dip into it. Eat the first spoonfuls slowly: the ice melts faster than "
        "you think.",
        ["food", "summer"], True,
    ),
    (
        "valley-of-the-temples", "history", "The Valley of the Temples",
        "Seven Doric temples on a ridge above the sea.",
        "Above the town of Agrigento stand some of the best-preserved Greek temples outside Greece. "
        "Visit at sunset, when the limestone turns gold, and walk the ridge from the temple of "
        "Concordia down to the garden of Kolymbethra.",
        ["agrigento", "ruins"], True,
    ),
    (
        "salt-pans-of-trapani", "nature", "The Salt Pans of Trapani",
        "Windmills, flamingos, and pink water.",
        "Along the western coast, near Trapani, shallow salt pans glitter beneath old windmills. "
        "In spring and autumn flocks of flamingos stop here on their migration, and the salt is "
        "still harvested by hand.",
        ["trapani", "birds"], True,
    ),
    (
        "ortigia", "history", "Ortigia, the Island Heart of Syracuse",
        "A small island with three thousand years of history.",
        "The old city of Syracuse sits on the island of Ortigia, joined to the mainland by a short "
        "bridge. Walk from the temple of Apollo to the spring of Arethusa, and notice the ancient "
        "theater that Greek colonists carved into the hill on the other shore.",
        ["syracuse", "ruins"], True,
    ),
    (
        "aeolian-islands-notes", "nature", "Aeolian Islands: Notes for a Future Post",
        "Draft: not ready to publish.",
        "Stromboli erupts every twenty minutes, like clockwork. Remember to mention the cannolo "
        "in Lipari and the ferry schedule.",
        ["islands"], False,
    ),
]


class Command(BaseCommand):
    help = "Create sample data: 3 categories, 12 articles about Sicily, and 1 draft."

    def handle(self, *args, **options):
        categories = {}
        for name, slug in CATEGORIES:
            categories[slug], _ = Category.objects.get_or_create(name=name, slug=slug)
        start = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        for i, (slug, category, title, summary, body, tags, published) in enumerate(ARTICLES):
            Article.objects.update_or_create(
                slug=slug,
                defaults={
                    "category": categories[category],
                    "title": title,
                    "summary": summary,
                    "body": body,
                    "tags": tags,
                    "published": published,
                    "published_at": start + timedelta(days=i) if published else None,
                },
            )
        self.stdout.write(f"{Article.objects.count()} articles in the database.")
