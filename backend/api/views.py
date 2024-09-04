import base64

from datetime import date

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import Sum
from django.http import HttpResponse
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
from .permissions import IsAdminOrReadOnly, IsAuthorOrAdminOrReadOnly
from .serializers import (
    UserSerializer, SubscribeSerializer, UserSubscribeSerializer,
    TagSerializer, IngredientSerializer, RecipeSerializer,
    RecipeDetailedSerializer, FullRecipeSerializer
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
        methods=['put', 'delete'],
        permission_classes=[permissions.IsAuthenticated],
        url_path='me/avatar'
    )
    def avatar(self, request, *args, **kwargs):
        user = request.user

        if request.method in ['PUT', 'PATCH']:
            return self.handle_avatar_upload(request, user)

        if request.method == 'DELETE':
            return self.handle_avatar_deletion(user)

        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def handle_avatar_upload(self, request, user):
        avatar_base64 = request.data.get('avatar')
        if not avatar_base64:
            return Response(
                {'error': 'Аватар не загружен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            format, imgstr = avatar_base64.split(';base64,')
            ext = format.split('/')[-1]
            data = base64.b64decode(imgstr)

            file_name = f"{user.id}_avatar.{ext}"
            file = ContentFile(data, file_name)

            user.avatar = file
            user.save()
            return Response(
                {'avatar': user.avatar.url},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {'error': 'Некорректные данные base64', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def handle_avatar_deletion(self, user):
        if user.avatar:
            if default_storage.exists(user.avatar.name):
                default_storage.delete(user.avatar.name)
            user.avatar = ''
            user.save()
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
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = (IngredientFilter,)
    search_fields = ('^name',)


class RecipeViewset(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    permission_classes = [IsAuthorOrAdminOrReadOnly]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter
    ordering = ('pub_date',)

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update'):
            return RecipeDetailedSerializer
        return FullRecipeSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_update(self, serializer):
        serializer.save(author=self.request.user)

    @action(
        detail=True, methods=['POST', 'DELETE'],
        permission_classes=[permissions.IsAuthenticated],
    )
    def favorite(self, request, pk=None):
        user = request.user
        recipe = get_object_or_404(Recipe, pk=pk)
        instance = Favorites.objects.filter(user=user, recipe=recipe)
        if request.method == 'POST':
            if instance.exists():
                return Response({'errors': 'Рецепт уже есть в избранном'},
                                status=status.HTTP_400_BAD_REQUEST)
            Favorites.objects.create(user=user, recipe=recipe)
            serializer = RecipeSerializer(recipe)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if not instance.exists():
            return Response(
                {'errors': 'Рецепт не добавлен в избранное или был удален'},
                status=status.HTTP_400_BAD_REQUEST
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True, methods=['POST', 'DELETE'],
        permission_classes=[permissions.IsAuthenticated],
    )
    def shopping_cart(self, request, pk=None):
        user = request.user
        recipe = get_object_or_404(Recipe, pk=pk)
        instance = ShoppingList.objects.filter(user=user, recipe=recipe)
        if request.method == 'POST':
            if instance.exists():
                return Response({'errors': 'Рецепт уже есть в списке покупок'},
                                status=status.HTTP_400_BAD_REQUEST)
            ShoppingList.objects.create(user=user, recipe=recipe)
            serializer = RecipeSerializer(recipe)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == 'DELETE':
            if not instance.exists():
                return Response(
                    {'errors': 'Рецепт не добавлен в список покупок'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            instance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response({'errors': 'Неизвестный запрос'},
                        status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=False, methods=['GET'],
        permission_classes=[permissions.IsAuthenticated],
    )
    def download_shopping_cart(self, request):
        user = request.user
        ingredients = IngredientsInRecipes.objects.filter(
            recipe__shopping_list__user=user
        ).values(
            'ingredient__name', 'ingredient__measurement_unit'
        ).order_by(
            'ingredient__name'
        ).annotate(
            ingredient_amount=Sum('amount')
        )

        today = date.today()
        shopping_list = [f'{today}\nСписок покупок:\n']
        for ingredient in ingredients:
            name = ingredient['ingredient__name']
            unit = ingredient['ingredient__measurement_unit']
            amount = ingredient['ingredient_amount']
            shopping_list.append(f'\n{name} ({unit}) - {amount}')

        filename = 'shopping_list.txt'
        response = HttpResponse(shopping_list, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename={filename}'
        return response

    @action(methods=['get'], detail=True, url_path='get-link')
    def get_link(self, request, pk=None):
        get_recipe = self.get_object()
        base_url = request.get_host()
        short_link = f'https://{base_url}/s/{get_recipe.short_link}'
        return Response({'short-link': short_link})


def short_link_for_recipe(request, short_link):
    base_url = request.get_host()
    get_recipe = get_object_or_404(Recipe.objects, short_link=short_link)
    return redirect(f'http://{base_url}/recipes/{get_recipe.pk}')
