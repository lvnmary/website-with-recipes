from django.contrib.auth.validators import UnicodeUsernameValidator
from rest_framework import serializers

from .models import User, Subscribe
from .constants import USERNAME_LENGTH


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
            'username', 'email', 'first_name',
            'last_name', 'role', 'is_subcribed',
            'password',
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


class SubscribeSerializer(serializers.ModelSerializer):

    class Meta:
        model = Subscribe
        fields = ('id', 'user', 'following_user',)
        read_only_fields = '__all__'


class UserSubscribeSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = (
            'id', 'username', 'first_name',
            'last_name', 'email', 'is_subcribed',
        )
