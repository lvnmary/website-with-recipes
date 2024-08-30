import csv
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from recipes.models import Ingredient

DATA_ROOT = os.path.join(settings.BASE_DIR, '..', 'data/ingredients.csv')


class Command(BaseCommand):
    def handle(self, *args, **options):
        with open(os.path.join(DATA_ROOT), 'r', encoding='utf-8') as file:
            file_reader = csv.reader(file)
            file.seek(0)

            ingredients = [Ingredient(
                name=row[0], measurement_unit=row[1])for row in file_reader
            ]

        Ingredient.objects.bulk_create(ingredients)

        self.stdout.write(
            self.style.SUCCESS('Импорт произведен')
        )
