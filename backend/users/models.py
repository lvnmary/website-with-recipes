from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.db import models

from .constants import (
    ADMIN, EMAIL_LENGTH, FNAME_LENGTH, LNAME_LENGTH,
    PASSWORD_LENGTH, ROLE_LENGTH, ROLES, USER, USERNAME_LENGTH
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
        max_length=ROLE_LENGTH,
        verbose_name='Роль',
        choices=ROLES,
        default=USER,
        blank=True
    )
    password = models.CharField(
        max_length=PASSWORD_LENGTH,
        verbose_name='Пароль'
    )
    is_subscribed = models.BooleanField(
        default=False,
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name', ]

    @property
    def is_admin(self):
        return self.role == ADMIN

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ('username',)

    def __str__(self):
        return self.username


class Subscribe(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='follower')
    following_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='following')

    class Meta:
        verbose_name = 'Подписчик'
        verbose_name_plural = 'Подписчики'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'following_user'],
                name='unique_subscribe'
            ),
            models.CheckConstraint(
                check=~models.Q(user=models.F('following_user')),
                name='prevent_self_follow'
            )
        ]

    def clean(self):
        if self.user == self.following_user:
            raise ValidationError('Нельзя подписаться на самого себя')

    def __str__(self):
        return (
            f'{self.user} подписан на {self.following_user}'
        )
