from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter

from .views import (
    UserViewset, TagViewset, IngredientViewset, RecipeViewset,
    FavoriteViewSet, ShoppingListViewSet, short_link_for_recipe
)

app_name = 'api'

router_v1 = DefaultRouter()

router_v1.register(r'recipes', RecipeViewset, basename='recipes')
router_v1.register(r'ingredients', IngredientViewset, basename='ingredients')
router_v1.register(r'tags', TagViewset, basename='tags')
router_v1.register(r'users', UserViewset, basename='users')

urlpatterns = [
    path('', include(router_v1.urls)),
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.authtoken')),
    path('recipes/<int:id>/favorite/', FavoriteViewSet.as_view(
        {
            'post': 'add_to_favorites',
            'delete': 'delete_from_favorites',
        }
    ), name='favorite_create_delete'),

    path('recipes/<int:id>/shopping_cart/', ShoppingListViewSet.as_view(
        {
            'post': 'add_to_shopping_list',
            'delete': 'delete_from_shopping_list',
        }
    ), name='shop_list_create_delete'),
    re_path(r'^s/(?P<short_link>[а-яёА-ЯЁa-z-]+)/$', short_link_for_recipe),
]
