# import base64
import csv
import io

# from datetime import date

# from django.core.files.base import ContentFile
# from django.core.files.storage import default_storage
from django.db.models import Sum
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from djoser.views import UserViewSet

from recipes.models import (
    Tag, Ingredient, Recipe, IngredientsInRecipes, Favorites, ShoppingList
)
from users.models import User, Subscribe
from .filters import IngredientFilter, RecipeFilter
from .permissions import IsAuthorOrAdminOrReadOnly
from .serializers import (
    UserSerializer, SubscribeSerializer, UserSubscribeSerializer,
    TagSerializer, IngredientSerializer, ShoppingListSerializer,
    RecipeDetailedSerializer, FullRecipeSerializer, FavoriteSerializer,
    AvatarUploadSerializer, IngredientInRecipeSerializer
)


class UserViewset(UserViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsAuthorOrAdminOrReadOnly,)
    search_fields = ('username', 'email',)
    pagination_class = LimitOffsetPagination

    @action(
        detail=False,
        methods=['GET'],
        permission_classes=[IsAuthenticated],
        url_path='me'
    )
    def me(self, request):
        user = request.user
        serializer = self.get_serializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=['POST', 'DELETE'],
        permission_classes=[permissions.IsAuthenticated],
    )
    def subscribe(self, request, id=None):
        user = request.user
        following_user = get_object_or_404(User, id=id)

        if user == following_user:
            return Response(
                {'error': 'Нельзя подписаться на себя.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        subscription = Subscribe.objects.filter(
            user=user, following_user=following_user)

        if request.method == 'POST':
            if subscription.exists():
                return Response(
                    {'error': 'Вы уже подписаны на этого пользователя.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            serializer = SubscribeSerializer(
                following_user, data=request.data,
                context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            self.create_subscription(user, following_user)
            return Response(
                self.get_subscription_data(following_user),
                status=status.HTTP_201_CREATED
            )

        if not subscription.exists():
            return Response(
                {'error': 'Вы не подписаны на этого пользователя.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        subscription.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def create_subscription(self, user, following_user):
        Subscribe.objects.create(user=user, following_user=following_user)

    def get_subscription_data(self, following_user):
        serializer = SubscribeSerializer(
            following_user, context={'request': self.request}
        )
        return serializer.data

    @action(
        detail=False,
        methods=['GET'],
        url_path='subscriptions',
        permission_classes=[permissions.IsAuthenticated],
    )
    def subscriptions(self, request):
        sub_authors = User.objects.filter(follower__user=request.user)
        paginated_queryset = self.paginate_queryset(sub_authors)
        serializer = UserSubscribeSerializer(
            paginated_queryset, many=True, context={'request': request}
        )
        return self.get_paginated_response(serializer.data)

    @action(
        detail=False,
        methods=['put'],
        permission_classes=[permissions.IsAuthenticated],
        url_path='me/avatar',
    )
    def avatar(self, request, *args, **kwargs):
        request_user = self.request.user
        serializer = AvatarUploadSerializer(instance=request_user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'avatar': request_user.avatar.url})

    @avatar.mapping.delete
    def delete_avatar(self, request, *args, **kwargs):
        user = self.request.user
        user.avatar.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TagViewset(viewsets.ModelViewSet):
    queryset = Tag.objects.all().order_by('id')
    serializer_class = TagSerializer

    def create(self, request, *args, **kwargs):
        return Response(
            {'detail': 'Method not allowed'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def update(self, request, *args, **kwargs):
        return Response(
            {'detail': 'Method not allowed'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def partial_update(self, request, *args, **kwargs):
        return Response(
            {'detail': 'Method not allowed'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {'detail': 'Method not allowed'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class IngredientViewset(viewsets.ModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter


class IngredientsInRecipesViewset(viewsets.ModelViewSet):
    queryset = IngredientsInRecipes.objects.all()
    serializer_class = IngredientInRecipeSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter


class RecipeViewset(viewsets.ModelViewSet):
    queryset = Recipe.objects.prefetch_related('author', 'ingredients', 'tags')
    serializer_class = RecipeDetailedSerializer
    permission_classes = [IsAuthorOrAdminOrReadOnly]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter
    ordering = ('pub_date',)
    http_method_names = ['get', 'post', 'patch', 'delete']
    pk_url_kwarg = 'pk'

    def get_serializer_class(self):
        if self.action in ['shopping_cart', 'download_shopping_cart']:
            return ShoppingListSerializer
        if self.action == 'favorite':
            return FavoriteSerializer
        if self.request.method == 'GET':
            return FullRecipeSerializer
        if self.request.method == 'PATCH':
            return RecipeDetailedSerializer
        return super().get_serializer_class()

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def recipe_post(self):
        request_user = self.request.user
        get_recipe = get_object_or_404(Recipe, pk=self.kwargs[self.pk_url_kwarg])
        serializer = self.get_serializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request_user, recipe=get_recipe)
        get_headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=get_headers)

    def recipe_delete(self, manager):
        request_user = self.request.user
        get_recipe = get_object_or_404(Recipe, pk=self.kwargs[self.pk_url_kwarg])
        recipe = manager.filter(user=request_user, recipe=get_recipe)
        if recipe.exists():
            recipe.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['post'], detail=True)
    def shopping_cart(self, request, pk=None):
        return self.recipe_post()

    @shopping_cart.mapping.delete
    def delete_shopping_cart(self, request, pk=None):
        return self.recipe_delete(ShoppingList.objects)

    @action(methods=['get'], detail=False)
    def download_shopping_cart(self, request, pk=None):
        shop_list = self.get_shop_list(self.request.user)
        response = FileResponse(shop_list, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="shopping_cart.csv"'
        return response

    @action(methods=['post'], detail=True)
    def favorite(self, request, pk=None):
        return self.recipe_post()

    @favorite.mapping.delete
    def delete_favorite(self, request, pk=None):
        return self.recipe_delete(Favorites.objects)

    @action(methods=['get'], detail=True, url_path='get-link')
    def get_link(self, request, pk=None):
        get_recipe = self.get_object()
        base_url = request.get_host()
        short_link = f'https://{base_url}/s/{get_recipe.short_link}'
        return Response({'short-link': short_link})

    def get_shop_list(self, user):
        count_ingredients = {}
        shop_list = io.StringIO()
        writer = csv.writer(shop_list)
        writer.writerow(['Ингредиент', 'Количество'])
        user_shopping_list = user.shopping_users.all()
        ingredient_ids = user_shopping_list.values_list('recipe', flat=True)
        ingredients = IngredientsInRecipes.objects.filter(
            recipe__in=ingredient_ids
        ).values('ingredient__name').annotate(total_amount=Sum('amount'))

        for item in ingredients:
            count_ingredients[item['ingredient__name']] = item['total_amount']
        for key, value in count_ingredients.items():
            writer.writerow([key, value])
        shop_list.seek(0)
        return shop_list


def short_link_for_recipe(request, short_link):
    base_url = request.get_host()
    get_recipe = get_object_or_404(Recipe.objects, short_link=short_link)
    return redirect(f'http://{base_url}/recipes/{get_recipe.pk}')
