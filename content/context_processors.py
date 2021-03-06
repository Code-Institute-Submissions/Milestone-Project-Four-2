from .models import Genre
from django.conf import settings
from content.views import (get_dislikelist, get_likelist,
                           get_watchlist, get_random_quote)

# https://stackoverflow.com/questions/34902707/how-can-i-pass-data-to-django-layouts-like-base-html-without-having-to-provi/34903331


def add_global_lists_to_context(request):

    random_quote = get_random_quote

    if request.user.is_authenticated:
        genres = Genre.objects.all().order_by('name')
        watch_list = get_watchlist(request)
        like_list = get_likelist(request)
        dislike_list = get_dislikelist(request)
        MEDIA_URL = getattr(settings, "MEDIA_URL")

        context = {
            "MEDIA_URL": MEDIA_URL,
            "genres": genres,
            "watch_list": watch_list,
            "like_list": like_list,
            "dislike_list": dislike_list,
            "random_quote": random_quote,
        }
    else:
        context = {
            "random_quote": random_quote,
        }

    return context
