from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse_lazy
from django.core.exceptions import ObjectDoesNotExist
from django.views.generic import ListView, UpdateView, DetailView, CreateView, DeleteView

import actstream.models
from redpanal.audio.models import Audio
from models import create_profile
from forms import UserProfileForm

def ensure_profile(user):
    try:
        user.userprofile
    except ObjectDoesNotExist:
        create_profile(user)

def user_page(request, slug):
    user = get_object_or_404(User, username=slug)
    audios = Audio.objects.filter(user=user)
    action_list = actstream.models.actor_stream(user)
    ensure_profile(user)

    if request.is_ajax():
        template = "social/actions_list.html"
    else:
        template =  "users/user_page.html"

    return render(request, template, {
        "user": user,
        "audios": audios,
        "action_list": action_list,
    })

def user_tracks(request, slug):
    user = get_object_or_404(User, username=slug)
    audios = Audio.objects.filter(user=user)

    return render(request, "users/user_tracks.html", {
        "user": user,
        "audios": audios,
    })

def user_interactions(request, slug):
    user = get_object_or_404(User, username=slug)
    return render(request, "users/user_interactions.html", {
        "user": user,
    })

@login_required
def user_profile(request):
    ensure_profile(request.user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user.userprofile)
        if form.is_valid():
            form.save()
    else:
        form = UserProfileForm(instance=request.user.userprofile)
    return render(request, "users/user_profile.html", {"form":form})


def user_list(request):
    users = User.objects.all()
    return render(request, "users/user_list.html", {
        "users": users,
    })
