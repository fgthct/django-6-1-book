from decimal import Decimal

from django.core.management.base import BaseCommand

from shop.models import Category, Product

CATALOG = {
    "Sweets": [
        ("Bronte Pistachios, 7 oz", "Roasted green pistachios from the slopes of Mount Etna.", "14.00", 3),
        ("Cannoli Shells", "Crisp shells, ready to fill with ricotta.", "9.50", 12),
        ("Marzipan Fruit Box", "Almond paste shaped and painted like fruit.", "18.00", 8),
        ("Almond Brittle", "Caramelized almonds, the way they are sold at festivals.", "6.50", 15),
        ("Almond Torrone", "Soft nougat with Sicilian almonds.", "8.00", 10),
        ("Candied Orange Peel", "Strips of blood orange peel in sugar.", "7.25", 9),
        ("Cassata Baking Kit", "Sponge, ricotta cream, and marzipan, in a box.", "22.00", 0),
    ],
    "Pantry": [
        ("Extra Virgin Olive Oil, 17 oz", "Cold-pressed Nocellara olives.", "16.50", 20),
        ("Trapani Sea Salt, 1 lb", "Coarse salt from the salt pans.", "5.00", 30),
        ("Busiate Pasta, 1 lb", "Hand-twisted pasta from Trapani.", "6.00", 25),
        ("Salina Capers, 3.5 oz", "Salt-packed capers.", "7.50", 14),
        ("Wild Oregano, 1 oz", "Dried mountain oregano.", "4.50", 18),
        ("Caponata, 12 oz", "Sweet and sour eggplant relish.", "9.00", 11),
    ],
    "Preserves": [
        ("Blood Orange Marmalade", "Made with Tarocco oranges.", "8.50", 13),
        ("Strattu Tomato Concentrate", "Sun-dried tomato paste.", "10.00", 7),
        ("Sun-Dried Tomatoes in Oil", "Plump tomatoes from Pachino.", "9.25", 16),
        ("Lemon Jam", "Bright jam from Syracuse lemons.", "7.00", 12),
    ],
    "Drinks": [
        ("Bitter Orange Soda", "A bittersweet soda served ice cold.", "3.50", 40),
        ("Lemon Soda", "Sparkling lemon soda.", "3.25", 35),
        ("Etna Rosso, 750 ml", "Red wine from the volcano's slopes.", "24.00", 6),
        ("Marsala Superiore, 500 ml", "Fortified wine for desserts.", "19.00", 8),
        ("Almond Syrup, 8 oz", "For granita and cold drinks.", "11.00", 10),
    ],
}


class Command(BaseCommand):
    help = "Create the categories and 22 sample products."

    def handle(self, *args, **options):
        created = 0
        for category_name, products in CATALOG.items():
            category, _ = Category.objects.get_or_create(name=category_name)
            for name, description, price, stock in products:
                _, was_created = Product.objects.get_or_create(
                    name=name,
                    defaults={"category": category, "description": description,
                              "price": Decimal(price), "stock": stock},
                )
                created += was_created
        total = Product.objects.count()
        self.stdout.write(f"{created} products created, {total} in total.")
