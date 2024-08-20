from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    UserViewset, TagViewset, IngredientViewset, RecipeViewset
)

app_name = 'api'

router_v1 = DefaultRouter()

router_v1.register('recipes', RecipeViewset, basename='recipes')
router_v1.register('ingredients', IngredientViewset, basename='ingredients')
router_v1.register('tags', TagViewset, basename='tags')
router_v1.register('users', UserViewset, basename='users')

urlpatterns = [
    path('', include(router_v1.urls)),
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.authtoken')),
]
