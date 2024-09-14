import uuid

from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .constants import (
    INGREDIENT_NAME_LENGTH, MEASUREMENT_UNIT_LENGTH,
    MIN_COOKING_TIME, MIN_INGREDIENT_AMOUNT,
    MAX_COOKING_TIME, MAX_INGREDIENT_AMOUNT,
    RECIPE_NAME_LENGTH, RECIPE_SLINK_LENGTH,
    SLUG_LENGTH, TAG_LENGTH
)

User = get_user_model()


class Tag(models.Model):
    name = models.CharField(
        unique=True,
        max_length=TAG_LENGTH,
        verbose_name='Название',
    )
    slug = models.SlugField(
        unique=True,
        max_length=SLUG_LENGTH,
        verbose_name='Слаг',
    )

    class Meta:
        verbose_name = 'Тег'
        verbose_name_plural = 'Теги'
        ordering = ('name',)

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    name = models.CharField(
        max_length=INGREDIENT_NAME_LENGTH,
        verbose_name='Название',
    )
    measurement_unit = models.CharField(
        max_length=MEASUREMENT_UNIT_LENGTH,
        verbose_name='Единица измерения',
    )

    class Meta:
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'
        ordering = ('name',)

    def __str__(self):
        return f'{self.name}, {self.measurement_unit}'


class Recipe(models.Model):
    author = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='recipe',
        verbose_name='Автор',
    )
    name = models.CharField(
        max_length=RECIPE_NAME_LENGTH,
        verbose_name='Название',
    )
    image = models.ImageField(
        upload_to='recipes/images/',
        verbose_name='Картинка',
    )
    text = models.TextField(
        verbose_name='Описание'
    )
    ingredients = models.ManyToManyField(
        Ingredient,
        through='IngredientsInRecipes',
        related_name='recipes',
        verbose_name='Ингредиенты',
    )
    tags = models.ManyToManyField(
        Tag,
        verbose_name='Тег'
    )
    cooking_time = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(
                MIN_COOKING_TIME,
                f'Минимальное время - {MIN_COOKING_TIME} минута'),
            MaxValueValidator(
                MAX_COOKING_TIME,
                f'Максимальное время - {MAX_COOKING_TIME} минут')
        ],
        verbose_name='Время приготовления в минутах'
    )
    pub_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата публикации'
    )
    short_link = models.SlugField(blank=True, unique=True)

    def save(self, *args, **kwargs):
        if not self.short_link:
            self.short_link = str(uuid.uuid4())[:RECIPE_SLINK_LENGTH]
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'
        ordering = ('-pub_date',)

    def __str__(self):
        return self.name


class IngredientsInRecipes(models.Model):
    recipe = models.ForeignKey(
        Recipe, on_delete=models.CASCADE,
        related_name='recipes_ingredients',
        verbose_name='Рецепт',
    )
    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.CASCADE,
        related_name='ingredients_recipes',
        verbose_name='Ингредиент',
    )
    amount = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(
                MIN_INGREDIENT_AMOUNT,
                f'Минимальное количество - {MIN_INGREDIENT_AMOUNT}'),
            MaxValueValidator(
                MAX_INGREDIENT_AMOUNT,
                f'Максимальное количество - {MAX_INGREDIENT_AMOUNT}')
        ],
        verbose_name='Количество'
    )

    class Meta:
        verbose_name = 'Ингредиент в рецепте'
        verbose_name_plural = 'Ингредиенты в рецепте'
        constraints = [
            models.UniqueConstraint(
                fields=['recipe', 'ingredient'],
                name='unique_ingredients_recipes'
            )
        ]

    def __str__(self):
        return f'{self.ingredient} в {self.recipe}'


class BaseUserRecipe(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        verbose_name='Пользователь',
    )
    recipe = models.ForeignKey(
        Recipe, on_delete=models.CASCADE,
        verbose_name='Рецепт',
    )

    class Meta:
        abstract = True
        verbose_name = 'Пользовательский рецепт'
        default_related_name = '%(class)s'


class Favorites(BaseUserRecipe):

    class Meta(BaseUserRecipe.Meta):
        verbose_name = 'Избранный рецепт'
        verbose_name_plural = 'Избранные рецепты'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'recipe'],
                name='unique_favorite_recipe'
            )
        ]


class ShoppingList(BaseUserRecipe):

    class Meta(BaseUserRecipe.Meta):
        verbose_name = 'Список покупок'
        verbose_name_plural = 'Списки покупок'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'recipe'],
                name='unique_shopping_list'
            )
        ]

    def __str__(self):
        return f'{self.recipe} добавлен в список покупок {self.user}'
