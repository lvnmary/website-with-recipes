# FOODGRAM



## Описание:
Foodgram — это веб-сервис для настоящих гурманов и тех, кто любит готовить. Здесь вы можете делиться своими рецептами с фотографиями, добавлять к ним ингредиенты и распределять рецепты по тегам. Пользователи могут сохранять понравившиеся рецепты в избранное, подписываться на других авторов, и легко сохранять список ингредиентов прямо в корзину покупок. Сервис «Список покупок» позволяет быстро сформировать список продуктов, необходимых для приготовления выбранных блюд.

## Стек технологий:
- Python
- Django
- API
- Nginx
- Djoser
- Gunicorn 

## Ознакомиться с проектом можно по ссылке:
foodgramlvnmary.ddns.net

## Как запустить проект:
Клонировать репозиторий и перейти в него в командной строке

```
git@github.com:lvnmary/foodgram.git
```

Перейти в корневую директорию
```
cd foodgram
```

Создать файл .evn для хранения ключей

Запустить docker-compose.production

```
docker compose -f docker-compose.production.yml up
```

Выполнить миграции, сбор статики

```
docker compose -f docker-compose.production.yml exec backend python manage.py migrate
docker compose -f docker-compose.production.yml exec backend python manage.py collectstatic
docker compose -f docker-compose.production.yml exec backend cp -r /app/collected_static/. /static/static/

```

Создать суперпользователя

```
docker compose -f docker-compose.production.yml exec backend python manage.py createsuperuser
```

## Автор:
Левина Мария 
https://github.com/lvnmary

