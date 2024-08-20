import django_filters
from django_filters import rest_framework as filters
from django.contrib.auth import get_user_model
from recipes.models import Recipe, Tag, Ingredient

User = get_user_model()


class IngredientFilter(filters.FilterSet):
    name = django_filters.CharFilter(
        field_name='name',
        lookup_expr='icontains',
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
            return queryset.filter(favorite_recipe__user=self.request.user)
        return queryset

    def filter_is_in_shopping_cart(self, queryset, name, value):
        if value:
            return queryset.filter(shopping_cart__user=self.request.user)
        return queryset

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)

        tags = self.data.get('tags')
        if tags == "__all__":
            return queryset

        if not tags and not self.data.get('author'):
            return Recipe.objects.none()

        return queryset
