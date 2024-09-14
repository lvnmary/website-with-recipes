import django_filters
from django.contrib.auth import get_user_model
from django_filters import rest_framework as filters

from recipes.models import Recipe, Tag, Ingredient

User = get_user_model()


class IngredientFilter(filters.FilterSet):
    name = django_filters.CharFilter(
        lookup_expr='istartswith',
    )

    class Meta:
        model = Ingredient
        fields = ('name', 'measurement_unit')


class RecipeFilter(filters.FilterSet):
    author = filters.ModelChoiceFilter(
        queryset=User.objects.all(),
        label='Автор'
    )
    tags = filters.ModelMultipleChoiceFilter(
        field_name='tags__slug',
        queryset=Tag.objects.all(),
        to_field_name='slug',
        label='Теги'
    )
    is_favorited = filters.BooleanFilter(
        method='filter_is_favorited',
        label='В избранном'
    )
    is_in_shopping_cart = filters.BooleanFilter(
        method='filter_is_in_shopping_cart',
        label='В корзине'
    )

    class Meta:
        model = Recipe
        fields = ('author', 'tags', 'is_favorited', 'is_in_shopping_cart')

    def filter_is_favorited(self, queryset, name, value):
        if value:
            return queryset.filter(favorites__user=self.request.user)
        return queryset

    def filter_is_in_shopping_cart(self, queryset, name, value):
        if value:
            return queryset.filter(shoppinglist__user=self.request.user)
        return queryset
