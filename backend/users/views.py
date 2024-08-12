from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.pagination import LimitOffsetPagination
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from djoser.conf import settings
from djoser.views import UserViewSet

from .models import User, Subscribe
from .serializers import UserSerializer, SubscribeSerializer
from .permissions import IsAdmin


class UserViewset(UserViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsAdmin,)
    search_fields = ('username',)
    pagination_class = LimitOffsetPagination

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

    # @action(
    #     detail=False,
    #     methods=['GET'],
    #     url_path='subscriptions',
    #     permission_classes=[permissions.IsAuthenticated],
    # )
    # def subscriptions(self, request):
    #     """Возвращает список подписок текущего пользователя."""
    #     authors = User.objects.filter(sub_author__user=request.user)
    #     paginated_authors = self.paginate_queryset(authors)
    #     serializer = SubscriptionsSerializer(
    #         paginated_authors, many=True, context={'request': request}
    #     )
    #     return self.get_paginated_response(serializer.data)
