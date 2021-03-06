from django.shortcuts import render, get_object_or_404, redirect, reverse
from .models import (Genre, Video, Watchlist, Likelist,
                     Dislikelist, Watched, Watching)
from django.contrib.auth.decorators import login_required
from django.urls import resolve
from django.contrib import messages
from utils.video import get_video_url
from accounts.models import Subscriber
from itertools import chain
from taggit.models import Tag
from collections import Counter
import random


@login_required
def content_view(request):
    """ Display all video content by genre"""
    subscriber = Subscriber.objects.filter(user=request.user.id)
    if subscriber:
        # Get Featured Content
        try:
            featured_vid = Video.objects.get(featured=True)
        except Video.DoesNotExist:
            # If featured isnt set grab random
            # https://stackoverflow.com/questions/22816704/django-get-a-random-object/22816927
            videos = Video.objects.all()
            featured_vid = random.choice(videos)

        genres = Genre.objects.all()
        all_videos = Video.objects.none()
        watched_list = get_watched_list(request)
        watching_list = get_watching_list(request)
        liked_videos = get_likelist(request)
        popular = get_popular_videos()
        final_video_list = []

        # Grab random liked video for suggestion
        try:
            liked_video = random.choice(liked_videos)
            liked_video_list = get_suggested_by_video(liked_video, 20)

        except TypeError:
            liked_video = None
            liked_video_list = None

        # Get 20 videos from each genre and combine queryset
        for genre in genres:

            videos = Video.objects.filter(genre=genre)[:20]

            if all_videos is None:
                all_videos = videos
            else:
                # https://stackoverflow.com/questions/38967599/joining-two-querysets-in-django
                final_video_list = list(chain(videos, final_video_list))

        context = {
            "videos": final_video_list,
            "genres": genres,
            "watched_list": watched_list,
            "most_popular": popular,
            "watching_list": watching_list,
            "liked_video": liked_video,
            "liked_video_list": liked_video_list,
            "video_url": get_video_url(featured_vid.youtube_link),
            "video_title": featured_vid.title,
            "video_desc": featured_vid.description,
            "video_img": featured_vid.image_landscape,
            "video_link": featured_vid.slug,
        }

        return render(request, 'home.html', context)
    else:
        return redirect(reverse('plans'))


@login_required
def video_view(request, slug):
    """ Display single video content """

    subscriber = Subscriber.objects.filter(user=request.user.id)
    if subscriber:
        video = get_object_or_404(Video, slug=slug)
        watching_list = get_watching_list(request)

        # Add view to video
        curr_views = video.views
        Video.objects.filter(pk=video.pk).update(
            views=curr_views + 1)

        # https://stackoverflow.com/questions/11321906/in-django-taggit-how-to-get-tags-for-objects-that-are-associated-with-a-specifi
        tags = Tag.objects.filter(video__title=video.title)

        # Get suggested videos
        videos = get_suggested_by_video(video, 3)

        # Check if in watching list
        # if there add start time
        start_time = None
        if watching_list is not None:
            for item in watching_list:
                if item.slug == slug:
                    v = Watching.objects.get(slug=item.slug)
                    start_time = v.time

        content = {
            "curr_video": video,
            "start_time": start_time,
            "tags": tags,
            "youtube_link": get_video_url(video.youtube_link),
            "videos": videos
        }

        return render(request, 'video.html', content)
    else:
        return redirect(reverse('plans'))


@login_required
def add_to_watching_list(request, slug):
    """ Add video to currently watching list """
    try:
        time = int(request.GET.get('t'))
        duration = int(request.GET.get('d'))
    except ValueError:
        return redirect(reverse('index'))

    # Check if already exists then add/update
    try:
        video = Watching.objects.get(slug=slug)
        Watching.objects.filter(slug=slug).update(
            time=time,
            duration=duration,
        )
    except Watching.DoesNotExist:
        video = Video.objects.get(slug=slug)

        Watching.objects.get_or_create(
                item=video,
                slug=video.slug,
                time=time,
                duration=duration,
                user=request.user,
            )

    return redirect(reverse('index'))


def get_popular_videos():
    """ Get most popular videos """
    videos = Video.objects.all().order_by("-views")[:10]

    return videos


@login_required
def remove_from_watching_list(request, slug):
    """ Remove video from currently watching and add
        to watched list """

    # Check if already exists if not add.
    try:
        video = Watched.objects.get(slug=slug)
        return redirect(reverse('index'))
    except Watched.DoesNotExist:
        # Remove from watching
        try:
            video = Watching.objects.get(slug=slug)
            video.delete()
        except Watching.DoesNotExist:
            pass

        video = Video.objects.get(slug=slug)
        Watched.objects.get_or_create(
                item=video,
                slug=video.slug,
                user=request.user,
            )

    return redirect(reverse('index'))


@login_required
def watchlist_view(request):
    """ Get User Watch List videos """
    videos = get_watchlist(request)

    context = {
        'videos': videos,
    }

    return render(request, 'watch-list.html', context)


def get_watchlist(request):
    """ Get videos in user watch list """
    items = Watchlist.objects.filter(user=request.user)
    videos = Video.objects.none()

    for item in items:
        videos = Video.objects.filter(title=item) | videos

    if len(videos) == 0:
        videos = None

    return videos


@login_required
def add_to_watchlist(request, slug):
    """ Add items to user watch list """
    # https://stackoverflow.com/questions/56580696/how-to-implement-add-to-wishlist-for-a-product-in-django
    # Check if item exist, if so remove
    try:
        item = Watchlist.objects.get(slug=slug)
        item.delete()
        messages.info(request, 'The item was removed from your watchlist')

    except Watchlist.DoesNotExist:

        video = get_object_or_404(Video, slug=slug)

        Watchlist.objects.get_or_create(
            item=video,
            slug=video.slug,
            user=request.user,
        )

    return redirect(reverse('watch-list'))


@login_required
def like_dislike_video(request, slug):
    """ Add items to user like/dislike lists """
    # https://stackoverflow.com/questions/54945781/django-how-to-get-url-path
    current_url = resolve(request.path_info).url_name
    video = get_object_or_404(Video, slug=slug)

    if current_url == 'like':
        # Check if item is disliked
        try:
            # Check if item is in dislike list
            # if so remove and add to likes
            item = Dislikelist.objects.get(slug=slug)
            item.delete()

        except Dislikelist.DoesNotExist:
            pass

        # check if already in likes, then remove
        try:
            item = Likelist.objects.get(slug=slug)
            item.delete()

        except Likelist.DoesNotExist:
            # If not add to likes
            Likelist.objects.get_or_create(
                item=video,
                slug=video.slug,
                user=request.user,
            )

    elif current_url == 'dislike':
        try:
            item = Likelist.objects.get(slug=slug)
            item.delete()

        except Likelist.DoesNotExist:
            pass

        try:
            item = Dislikelist.objects.get(slug=slug)
            item.delete()

        except Dislikelist.DoesNotExist:
            """ If not add to dislikes """
            Dislikelist.objects.get_or_create(
                item=video,
                slug=video.slug,
                user=request.user,
            )

    return redirect(reverse('index'))


def get_likelist(request):
    """ Get videos in user watch list """
    items = Likelist.objects.filter(user=request.user)
    videos = Video.objects.none()

    for item in items:
        videos = Video.objects.filter(title=item) | videos

    if len(videos) == 0:
        videos = None

    return videos


def get_dislikelist(request):
    """ Get videos in user watch list """
    items = Dislikelist.objects.filter(user=request.user)
    videos = Video.objects.none()

    for item in items:
        videos = Video.objects.filter(title=item) | videos

    if len(videos) == 0:
        videos = None

    return videos


def get_watched_list(request):
    """ Get videos in user watched list """
    items = Watched.objects.filter(user=request.user)
    videos = Video.objects.none()

    for item in items:
        videos = Video.objects.filter(title=item) | videos

    if len(videos) == 0:
        videos = None

    return videos


def get_watching_list(request):
    """ Get videos in user watching list """
    items = Watching.objects.filter(user=request.user)
    videos = Video.objects.none()

    for item in items:
        videos = Video.objects.filter(title=item) | videos

    if len(videos) == 0:
        videos = None

    return videos


def get_suggested_by_likes(request, num):
    """ Get videos based on users likes """
    videos = Video.objects.none()
    tag_list = []
    temp_tag_list = []

    # Get lists
    like_list = get_likelist(request)

    # Most common tags from likes
    for video in like_list:
        tags = Tag.objects.filter(video__title=video)

        # Add tags to temp list
        for tag in tags:
            temp_tag_list.append(tag.name)

    # Count duplicates
    count = Counter(temp_tag_list)
    for item in count:
        if count[item] > 1:
            tag_list.append(item)

    # Get videos based on tags
    # https://django-taggit.readthedocs.io/en/latest/api.html#filtering
    videos = Video.objects.filter(tags__name__in=tag_list)[:num]

    return videos


def get_suggested_by_video(video, num):
    """ Return videos based on tags/genre """
    videos = video.tags.similar_objects()[:num]
    return videos


def get_random_quote():
    """ Get random qoute for 404 page """
    quotes = [
        "\"Houston, we have a problem.\" - Apollo 13",
        "\"My precious.\" - The Lord of the Rings: The Two Towers",
        "\"Say 'hello' to my little friend!\" - Scarface",
        "\"E.T. phone home.\" - E.T. the Extra-Terrestrial",
        "\"Go ahead, make my day.\" - Sudden Impact",
        "\"Toto, I've a feeling we're \
            not in Kansas anymore.\" - The Wizard of Oz",
        "\"These aren't the droids you're looking for\" - Star Wars"
    ]

    return random.choice(quotes)
