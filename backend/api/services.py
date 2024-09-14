import csv
import io

from django.db.models import Sum

from recipes.models import IngredientsInRecipes


def get_ingredients(user):
    return IngredientsInRecipes.objects.filter(
        recipe__in=user.shoppinglist.values_list('recipe', flat=True)
    ).values('ingredient__name').annotate(
        total_amount=Sum('amount')
    ).order_by('ingredient__name')


def generate_shopping_list(ingredients_queryset):
    shop_list = io.StringIO()
    writer = csv.writer(shop_list)
    writer.writerow(['Ингредиент', 'Количество'])

    for item in ingredients_queryset:
        writer.writerow([item['ingredient__name'], item['total_amount']])

    shop_list.seek(0)
    return shop_list
