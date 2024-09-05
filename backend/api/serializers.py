import base64

from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.files.base import ContentFile
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
        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return Subscribe.objects.filter(user=user, following_user=obj).exists()

    def get_avatar(self, obj):
        return obj.avatar.url if obj.avatar else ''


class SubscribeSerializer(serializers.ModelSerializer):
    user = serializers.SlugRelatedField(
        slug_field='username',
        read_only=True,
        default=serializers.CurrentUserDefault()
    )
    following_user = serializers.SlugRelatedField(
        slug_field='username',
        queryset=User.objects.all(),
        default=serializers.CurrentUserDefault()
    )

    class Meta:
        model = Subscribe
        fields = ('user', 'following_user',)

    def to_representation(self, instance):
        request = self.context.get('request')
        context = {'request': request}
        return UserSubscribeSerializer(
            instance.following_user, context=context
        ).data


class UserSubscribeSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'first_name',
            'last_name', 'email', 'is_subscribed',
            'recipes', 'recipes_count',
        )

    def get_is_subscribed(self, obj):
        return getattr(obj, 'is_subscribed', False)

    def get_recipes(self, obj):
        request = self.context.get('request')
        limit = request.GET.get('recipes_limit')
        recipes = Recipe.objects.filter(author=obj)
        if limit:
            recipes = recipes[:int(limit)]
        serializer = RecipeSerializer(recipes, many=True)
        return serializer.data

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


class IngredientInRecipeSerializer(serializers.ModelSerializer):
    ingredient = IngredientSerializer(read_only=True)
    amount = serializers.IntegerField(required=True)

    class Meta:
        model = IngredientsInRecipes
        fields = ('ingredient', 'amount')


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name='temp.' + ext)
        return super().to_internal_value(data)


class RecipeSerializer(serializers.ModelSerializer):
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class RecipeDetailedSerializer(serializers.ModelSerializer):
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True
    )
    author = UserSerializer(read_only=True)
    ingredients = serializers.ListField(child=serializers.DictField())
    image = Base64ImageField(required=True)

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients',
            'name', 'image', 'text', 'cooking_time',
        )

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
        for ingredient_data in ingredients:
            IngredientsInRecipes.objects.create(
                recipe=recipe,
                ingredient_id=ingredient_data['id'],
                amount=ingredient_data['amount']
            )

    def create(self, validated_data):
        tags = validated_data.pop('tags')
        ingredients = validated_data.pop('ingredients')
        recipe = Recipe.objects.create(**validated_data)
        recipe.tags.set(tags)
        self.create_ingredients(ingredients, recipe)
        return recipe

    def update(self, instance, validated_data):
        tags = validated_data.pop('tags', None)
        ingredients = validated_data.pop('ingredients', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if tags is not None:
            instance.tags.set(tags)

        if ingredients is not None:
            instance.ingredients_recipes.all().delete()
            self.create_ingredients(ingredients, instance)

        instance.save()
        return instance

    def to_representation(self, instance):
        return FullRecipeSerializer(instance, context=self.context).data


class FullRecipeSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    author = UserSerializer(read_only=True)
    ingredients = serializers.SerializerMethodField()
    image = Base64ImageField()
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients',
            'is_favorited', 'is_in_shopping_cart',
            'name', 'image', 'text', 'cooking_time'
        )

    def get_ingredients(self, obj):
        ingredients = IngredientInRecipeSerializer(
            obj.recipes_ingredients.all(), many=True,
        ).data
        for ingredient in ingredients:
            if ingredient['amount'] <= 1:
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
