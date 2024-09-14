from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_extra_fields.fields import Base64ImageField
from djoser.serializers import UserCreateSerializer
from rest_framework import serializers

from recipes.constants import (MAX_INGREDIENT_AMOUNT, MIN_INGREDIENT_AMOUNT,
                               MAX_COOKING_TIME, MIN_COOKING_TIME)
from recipes.models import (Favorites, Ingredient, IngredientsInRecipes,
                            Recipe, ShoppingList, Tag)
from users.models import Subscribe, User


class UserSerializer(UserCreateSerializer):
    is_subscribed = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'email', 'username', 'first_name',
            'last_name', 'is_subscribed', 'avatar', 'password',
        )
        extra_kwargs = {'password': {'write_only': True}}

    def get_is_subscribed(self, obj):
        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return Subscribe.objects.filter(user=user, following_user=obj).exists()

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class AvatarUploadSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField(required=True)

    class Meta:
        model = User
        fields = ('avatar',)

    def update(self, instance, validated_data):
        instance.avatar.save('image.png', validated_data['avatar'], save=True)
        return instance

    def validate(self, value):
        if not value:
            raise serializers.ValidationError('Изображение не было загружено')
        return value


class UserRecipeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    avatar = Base64ImageField()
    is_subscribed = serializers.BooleanField(default=False)
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta:
        fields = (
            'id', 'username', 'first_name',
            'last_name', 'email', 'is_subscribed',
            'recipes', 'recipes_count', 'avatar',
        )

    def get_recipes(self, obj):
        request = self.context.get('request')
        recipes_limit = request.query_params.get('recipes_limit')
        recipes_qs = obj.recipe.all()
        if recipes_limit:
            recipes_qs = recipes_qs[:int(recipes_limit)]
        return RecipeMiniSerializer(recipes_qs, many=True).data

    def get_recipes_count(self, obj):
        return Recipe.objects.filter(author=obj).count()


class SubscribeSerializer(serializers.ModelSerializer):
    following_user = UserSerializer(read_only=True)

    class Meta:
        model = Subscribe
        fields = ('following_user',)

    def to_representation(self, instance):
        return UserRecipeSerializer(
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
        return data


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
    name = serializers.SerializerMethodField()
    measurement_unit = serializers.SerializerMethodField()
    amount = serializers.IntegerField(
        max_value=MAX_INGREDIENT_AMOUNT,
        min_value=MIN_INGREDIENT_AMOUNT,
        default=None
    )

    class Meta:
        model = IngredientsInRecipes
        fields = (
            'ingredient', 'amount', 'recipe',
            'measurement_unit', 'name', 'id'
        )

    def get_name(self, obj):
        return obj.ingredient.name

    def get_measurement_unit(self, obj):
        return obj.ingredient.measurement_unit


class RecipeMiniSerializer(serializers.ModelSerializer):
    name = serializers.CharField()
    image = Base64ImageField()
    id = serializers.IntegerField()
    cooking_time = serializers.IntegerField()

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class RecipeSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    author = UserSerializer(read_only=True)
    ingredients = IngredientInRecipeSerializer(
        many=True, source='recipes_ingredients', read_only=True)
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients',
            'is_favorited', 'is_in_shopping_cart',
            'name', 'image', 'text', 'cooking_time'
        )

    def get_is_favorited(self, obj):
        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return Favorites.objects.filter(user=user, recipe=obj).exists()

    def get_is_in_shopping_cart(self, obj):
        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return ShoppingList.objects.filter(user=user, recipe=obj).exists()


class RecipeCreateSerializer(RecipeSerializer):
    image = Base64ImageField(required=True)
    cooking_time = serializers.IntegerField(
        required=True,
        max_value=MAX_COOKING_TIME,
        min_value=MIN_COOKING_TIME
    )
    is_favorited = serializers.BooleanField(default=False)
    is_in_shopping_cart = serializers.BooleanField(default=False)

    def validate_tags(self, value):
        if not value:
            raise serializers.ValidationError('Обязательное поле')
        tags = set()
        for tag_id in value:
            if tag_id in tags:
                raise serializers.ValidationError('Тег уже добавлен')
            if not Tag.objects.filter(pk=tag_id).exists():
                raise serializers.ValidationError('Тег не существует')
            tag = Tag.objects.get(pk=tag_id)
            tags.add(tag)
        return tags

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError('Обязательное поле')
        ingredients = set()
        ingredients_data = []
        for ingredient in value:
            if int(ingredient['amount']) <= 0:
                raise serializers.ValidationError(
                    'Количество не может быть меньше 1'
                )
            if ingredient['id'] in ingredients:
                raise serializers.ValidationError('Ингредиент уже добавлен')
            if not Ingredient.objects.filter(pk=ingredient['id']).exists():
                raise serializers.ValidationError('Ингредиент не существует')
            ingredient_obj = Ingredient.objects.get(pk=ingredient['id'])
            ingredients_data.append({
                'ingredient': ingredient_obj,
                'amount': ingredient['amount']
            })
            ingredients.add(ingredient['id'])
        return ingredients_data

    def validate(self, data):
        data = super().validate(data)
        data['tags'] = self.validate_tags(
            self.context['request'].data.get('tags')
        )
        data['ingredients'] = self.validate_ingredients(
            self.context['request'].data.get('ingredients')
        )
        return data

    def validate_image(self, value):
        if not value:
            raise serializers.ValidationError('Обязательное поле')
        return value

    @staticmethod
    def create_ingredients(ingredients_data, recipe):
        IngredientsInRecipes.objects.bulk_create(
            [IngredientsInRecipes(recipe=recipe, **ingredient)
             for ingredient in ingredients_data],
        )

    @transaction.atomic
    def create(self, validated_data):
        tags = validated_data.pop('tags')
        ingredients = validated_data.pop('ingredients')
        validated_data.pop('is_favorited', None)
        validated_data.pop('is_in_shopping_cart', None)
        recipe = Recipe.objects.create(**validated_data)
        recipe.tags.set(tags)
        self.create_ingredients(ingredients, recipe)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        tags = validated_data.pop('tags')
        ingredients = validated_data.pop('ingredients')
        instance.ingredients.clear()
        instance.tags.set(tags)
        self.create_ingredients(ingredients, instance)
        return super().update(instance, validated_data)


class ShoppingListSerializer(serializers.ModelSerializer):
    recipe = RecipeSerializer(read_only=True)

    class Meta:
        model = ShoppingList
        fields = ('recipe',)
        read_only_fields = ('user', 'recipe')

    def validate(self, data):
        request = self.context['request']
        recipe_id = self.context['view'].kwargs.get('pk')
        recipe = get_object_or_404(Recipe, pk=recipe_id)
        if request.method == 'POST' and ShoppingList.objects.filter(
                user=request.user, recipe=recipe).exists():
            raise serializers.ValidationError(
                'Рецепт уже есть в списке покупок'
            )
        return data


class FavoriteSerializer(ShoppingListSerializer):

    class Meta:
        model = Favorites
        fields = ('recipe',)
        read_only_fields = ('user', 'recipe')

    def validate(self, data):
        request = self.context['request']
        recipe_id = self.context['view'].kwargs.get('pk')
        recipe = get_object_or_404(Recipe, pk=recipe_id)
        if request.method == 'POST' and request.user.favorites.filter(
                recipe=recipe).exists():
            raise serializers.ValidationError('Рецепт уже есть в избранном')

        return data
