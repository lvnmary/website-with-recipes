from django.db.models import Exists, OuterRef
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import (
    LimitOffsetPagination, PageNumberPagination
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from djoser.serializers import SetPasswordSerializer
from djoser.views import UserViewSet

from recipes.models import (
    Favorites, Ingredient, IngredientsInRecipes, Recipe, ShoppingList, Tag
)
from users.models import Subscribe, User

from .filters import IngredientFilter, RecipeFilter
from .permissions import IsAuthorOrAuthenticatedOrReadOnly
from .services import generate_shopping_list, get_ingredients
from .serializers import (
    AvatarUploadSerializer, FavoriteSerializer, IngredientInRecipeSerializer,
    IngredientSerializer, RecipeCreateSerializer, RecipeSerializer,
    ShoppingListSerializer, SubscribeSerializer, TagSerializer, UserSerializer
)


class UserViewset(UserViewSet):
    queryset = User.objects.all()
    filter_backends = [filters.SearchFilter]
    serializer_class = UserSerializer
    permission_classes = (IsAuthorOrAuthenticatedOrReadOnly,)
    search_fields = ('username', 'email',)
    pagination_class = LimitOffsetPagination
    http_method_names = ['get', 'post', 'put', 'delete']
    pk_url_kwarg = 'id'

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return User.objects.all()
        subscribers = user.following.values_list('user', flat=True)
        return User.objects.annotate(is_user_subscribed=Exists(
            Subscribe.objects.filter(user__in=subscribers,
                                     following_user=OuterRef('pk'))))

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated],
        url_path='me'
    )
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated])
    def subscriptions(self, request):
        subscriptions = request.user.follower.all()
        page = self.paginate_queryset(subscriptions)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['put'],
            permission_classes=[IsAuthenticated],
            url_path='me/avatar', )
    def avatar(self, request):
        serializer = AvatarUploadSerializer(
            instance=request.user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'avatar': request.user.avatar.url})

    @avatar.mapping.delete
    def delete_avatar(self, request):
        request.user.avatar.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[IsAuthenticated],
    )
    def subscribe(self, request, *args, **kwargs):
        get_user = get_object_or_404(User, pk=kwargs[self.pk_url_kwarg])
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=self.request.user, following_user=get_user)
        get_headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED,
                        headers=get_headers)

    @subscribe.mapping.delete
    def unsubscribe(self, request, *args, **kwargs):
        get_user = get_object_or_404(User, pk=kwargs[self.pk_url_kwarg])
        subscription = self.request.user.follower.filter(
            following_user=get_user).first()
        if subscription:
            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_400_BAD_REQUEST)

    def get_serializer_class(self):
        if self.action in ['subscriptions', 'subscribe']:
            return SubscribeSerializer
        if self.action == 'set_password':
            return SetPasswordSerializer
        return UserSerializer


class TagViewset(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all().order_by('id')
    serializer_class = TagSerializer
    pagination_class = None


class IngredientViewset(viewsets.ModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter
    pagination_class = None


class IngredientsInRecipesViewset(viewsets.ModelViewSet):
    queryset = IngredientsInRecipes.objects.all()
    serializer_class = IngredientInRecipeSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter
    pagination_class = None


class RecipeViewset(viewsets.ModelViewSet):
    queryset = Recipe.objects.prefetch_related(
        'author', 'ingredients', 'tags'
    )
    serializer_class = RecipeCreateSerializer
    permission_classes = (IsAuthorOrAuthenticatedOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter
    ordering = ('pub_date',)
    http_method_names = ['get', 'post', 'patch', 'delete']
    pk_url_kwarg = 'pk'
    pagination_class = PageNumberPagination

    def get_queryset(self):
        return super().get_queryset()

    def get_serializer_class(self):
        if self.action in ['shopping_cart', 'download_shopping_cart']:
            return ShoppingListSerializer
        if self.action == 'favorite':
            return FavoriteSerializer
        if self.request.method == 'GET':
            return RecipeSerializer
        return RecipeCreateSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def recipe_post(self):
        recipe = get_object_or_404(Recipe, pk=self.kwargs[self.pk_url_kwarg])
        serializer = self.get_serializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=self.request.user, recipe=recipe)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def recipe_delete(self, manager):
        recipe = get_object_or_404(Recipe, pk=self.kwargs[self.pk_url_kwarg])
        instance = manager.filter(user=self.request.user, recipe=recipe)
        if instance.exists():
            instance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['post'], detail=True, )
    def shopping_cart(self, request, pk=None):
        return self.recipe_post()

    @shopping_cart.mapping.delete
    def delete_shopping_cart(self, request, pk=None):
        return self.recipe_delete(ShoppingList.objects)

    @action(methods=['get'], detail=False, )
    def download_shopping_cart(self, request, pk=None):
        ingredients_queryset = get_ingredients(self.request.user)
        shop_list = generate_shopping_list(ingredients_queryset)
        response = FileResponse(iter([shop_list.getvalue()]),
                                content_type='text/csv')
        response[
            'Content-Disposition'] = (
                'attachment; filename="shopping_cart.csv"'
        )
        return response

    @action(methods=['post'], detail=True)
    def favorite(self, request, pk=None):
        return self.recipe_post()

    @favorite.mapping.delete
    def delete_favorite(self, request, pk=None):
        return self.recipe_delete(Favorites.objects)

    @action(methods=['get'], detail=True, url_path='get-link')
    def get_link(self, request, pk=None):
        recipe = self.get_object()
        short_link = f'https://{request.get_host()}/s/{recipe.short_link}'
        return Response({'short-link': short_link})


def short_link_for_recipe(request, short_link):
    base_url = request.get_host()
    get_recipe = get_object_or_404(Recipe.objects, short_link=short_link)
    return redirect(f'http://{base_url}/recipes/{get_recipe.pk}')
