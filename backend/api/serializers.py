# import base64

from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from django.db import transaction
from drf_extra_fields.fields import Base64ImageField
from rest_framework import serializers

from users.models import User, Subscribe
from users.constants import USERNAME_LENGTH
from recipes.models import (
    Tag, Ingredient, Recipe, IngredientsInRecipes, Favorites, ShoppingList
)


class UserSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        required=True,
        max_length=USERNAME_LENGTH,
        validators=[UnicodeUsernameValidator(),]
    )
    is_subscribed = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'email', 'username', 'first_name',
            'last_name', 'is_subscribed', 'avatar',
        )

    def validate(self, data):
        user_by_username = User.objects.filter(
            username=data['username']
        ).first()
        user_by_email = User.objects.filter(email=data['email']).first()

        if user_by_username or user_by_email:
            errors = {}
            if user_by_username:
                errors['username'] = 'Это имя пользователя уже используется'
            if user_by_email:
                errors['email'] = 'Данная почта уже зарегистрирована'
            raise serializers.ValidationError(errors)
        return data

    def create(self, validated_data):
        user = User(**validated_data)
        user.set_password(validated_data['password'])
        user.save()
        return user

    def get_is_subscribed(self, obj):
        return getattr(obj, 'is_subscribed', False)


class AvatarUploadSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField(required=True)

    def update(self, instance, validated_data):
        avatar_data = validated_data.get('avatar', None)
        file_avatar = ContentFile(avatar_data.read())
        instance.avatar.save('image.png', file_avatar, save=True)
        return instance

    def validate(self, data):
        if not data.get('avatar'):
            raise serializers.ValidationError('Изображение не было загружено')
        return data

    class Meta:
        model = User
        fields = ('avatar',)


class SubscribeSerializer(serializers.ModelSerializer):
    following_user = UserSerializer(read_only=True)

    class Meta:
        model = Subscribe
        fields = ('user', 'following_user')
        read_only_fields = ('following_user',)

    def to_representation(self, instance):
        return UserSubscribeSerializer(
            instance.following_user, context=self.context
        ).data

    def validate(self, data):
        request = self.context['request']
        user_id = self.context['view'].kwargs.get('id')
        user = get_object_or_404(User, pk=user_id)
        if request.user == user:
            raise serializers.ValidationError('Нельзя подписаться на себя')
        if request.user.follower.filter(following_user=user).exists():
            raise serializers.ValidationError(
                'Вы уже подписаны на этого пользователя'
            )
        data['user'] = request.user
        data['following_user'] = user
        return data


class UserSubscribeSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'first_name',
            'last_name', 'email', 'is_subscribed',
            'recipes', 'recipes_count', 'avatar',
        )

    def get_is_subscribed(self, obj):
        return getattr(obj, 'is_subscribed', False)

    def get_recipes(self, obj):
        request = self.context.get('request')
        recipes_limit = request.query_params.get('recipes_limit')
        recipes_qs = Recipe.objects.filter(author=obj)
        if recipes_limit:
            recipes_qs = recipes_qs[:int(recipes_limit)]
        return RecipeSerializer(recipes_qs, many=True).data

    def get_recipes_count(self, obj):
        return Recipe.objects.filter(author=obj).count()


class TagSerializer(serializers.ModelSerializer):

    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')


class IngredientSerializer(serializers.ModelSerializer):

    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')
        read_only_fields = ('id', 'name', 'measurement_unit')


class IngredientInRecipeSerializer(serializers.ModelSerializer):
    ingredient = IngredientSerializer(read_only=True)
    amount = serializers.IntegerField(required=True)

    class Meta:
        model = IngredientsInRecipes
        fields = ('ingredient', 'amount')


# class Base64ImageField(serializers.ImageField):
#     def to_internal_value(self, data):
#         if isinstance(data, str) and data.startswith('data:image'):
#             format, imgstr = data.split(';base64,')
#             ext = format.split('/')[-1]
#             data = ContentFile(base64.b64decode(imgstr), name='temp.' + ext)
#         return super().to_internal_value(data)


class RecipeSerializer(serializers.ModelSerializer):
    name = serializers.CharField()
    image = Base64ImageField()
    id = serializers.IntegerField()
    cooking_time = serializers.IntegerField()

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class FullRecipeSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    author = UserSerializer(read_only=True)
    ingredients = serializers.SerializerMethodField()
    image = Base64ImageField()
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_list = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients',
            'is_favorited', 'is_in_shopping_list',
            'name', 'image', 'text', 'cooking_time'
        )

    def get_ingredients(self, obj):
        ingredients = IngredientInRecipeSerializer(
            obj.recipes_ingredients.all(), many=True,
        ).data
        for ingredient in ingredients:
            if ingredient['amount'] < 1:
                raise serializers.ValidationError(
                    'Минимальное колличество ингредиента - 1'
                )
        return ingredients

    def get_is_favorited(self, obj):
        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return Favorites.objects.filter(user=user, recipe=obj).exists()

    def get_is_in_shopping_list(self, obj):
        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return ShoppingList.objects.filter(user=user, recipe=obj).exists()


class RecipeDetailedSerializer(FullRecipeSerializer):
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True
    )
    author = UserSerializer(read_only=True)
    image = Base64ImageField(required=True)
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_list = serializers.SerializerMethodField()
    cooking_time = serializers.IntegerField(required=True)

    def validate_tags(self, tags):
        if not tags:
            raise serializers.ValidationError('Выберите тег')
        unique_tags = set()
        for tag in tags:
            if not Tag.objects.filter(id=tag).exists():
                raise serializers.ValidationError(f'Тег {tag} не существует')
            unique_tags.add(tag)
        if len(tags) != len(unique_tags):
            raise serializers.ValidationError('Теги должны быть уникальными')
        return tags

    def validate_ingredients(self, ingredients):
        if not ingredients:
            raise serializers.ValidationError('Выберите ингредиент')
        seen_ingredients = set()
        for ingredient_data in ingredients:
            ingredient_id = ingredient_data.get('id')
            if not Ingredient.objects.filter(id=ingredient_id).exists():
                raise serializers.ValidationError(
                    f'Ингредиент с id {ingredient_id} не существует'
                )
            if ingredient_id in seen_ingredients:
                raise serializers.ValidationError(
                    'Этот ингредиент уже добавлен'
                )
            seen_ingredients.add(ingredient_id)
        return ingredients

    def create_ingredients(self, ingredients, recipe):
        ingredients_data = [{'ingredient': ingredient_data['ingredient'],
                             'amount': ingredient_data['amount']}
                            for ingredient_data in ingredients
                            ]
        IngredientsInRecipes.objects.bulk_create(
            [IngredientsInRecipes(recipe=recipe, **ingredient_data)
             for ingredient_data in ingredients_data],
        )

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop('is_favorited')
        validated_data.pop('is_in_shopping_list')
        recipe = Recipe.objects.create(**validated_data)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        instance.ingredients.clear()
        validated_data['is_favorited'] = self.get_is_favorited(instance)
        return super().update(instance, validated_data)


class ShoppingListSerializer(serializers.ModelSerializer):
    recipes = FullRecipeSerializer()

    class Meta:
        model = ShoppingList
        fields = ('recipes',)
        read_only_fields = ('user', 'recipes')

    def to_representation(self, instance):
        return RecipeSerializer(instance.recipes, context=self.context).data

    def validate(self, data):
        request = self.context['request']
        recipe_id = self.context['view'].kwargs.get('pk')
        recipe = get_object_or_404(Recipe, pk=recipe_id)
        if request.method == 'POST' and request.user.shopping_users.filter(
                recipes=recipe).exists():
            raise serializers.ValidationError(
                'Рецепт уже есть в списке покупок'
            )
        return data


class FavoriteSerializer(ShoppingListSerializer):
    def validate(self, data):
        request = self.context['request']
        recipe_id = self.context['view'].kwargs.get('pk')
        if not Recipe.objects.filter(pk=recipe_id).exists():
            raise serializers.ValidationError('Такого рецепта нет')
        if request.method == 'POST' and request.user.favorites_users.filter(
                recipe__id=recipe_id).exists():
            raise serializers.ValidationError(
                'Рецепт уже есть в избранном'
            )
        return data

    class Meta:
        model = Favorites
        fields = ('recipe',)
        read_only_fields = ('user', 'recipe')