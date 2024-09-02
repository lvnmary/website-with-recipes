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
router_v1.register(r'recipes/(?P<id>\d+)/favorite', FavoriteViewSet, basename='favorite')
router_v1.register(r'recipes/(?P<id>\d+)/shopping_list', ShoppingListViewSet, basename='shoppinglist')

urlpatterns = [
    path('', include(router_v1.urls)),
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.authtoken')),
    re_path(r'^s/(?P<short_link>[а-яёА-ЯЁa-z-]+)/$', short_link_for_recipe),
]
