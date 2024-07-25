from django.contrib.auth.validators import UnicodeUsernameValidator
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

from .constants import (
    USERNAME_LENGTH, FNAME_LENGTH, LNAME_LENGTH, EMAIL_LENGTH,
    USER, ADMIN, ROLES
)


class User(AbstractUser):
    username = models.CharField(
        verbose_name='Логин',
        max_length=USERNAME_LENGTH,
        validators=(UnicodeUsernameValidator(),),
        unique=True, null=False,
        blank=False
    )
    first_name = models.CharField(
        max_length=FNAME_LENGTH,
        verbose_name='Имя'
    )
    last_name = models.CharField(
        max_length=LNAME_LENGTH,
        verbose_name='Фамилия'
    )
    email = models.EmailField(
        max_length=EMAIL_LENGTH,
        verbose_name='Почта',
        unique=True
    )
    avatar = models.ImageField(
        null=True, blank=True,
        default='avatar-icon.png',
        upload_to='images/'
    )
    role = models.CharField(
        max_length=max(len(role[0]) for role in ROLES),
        verbose_name='Роль',
        choices=ROLES,
        default=USER,
        blank=True
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    @property
    def is_admin(self):
        return self.role == ADMIN

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ('username',)

    def __str__(self):
        return self.username


class Follow(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='followers')
    following = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='following')

    class Meta:
        verbose_name = 'Подписчик'
        verbose_name_plural = 'Подписчики'
