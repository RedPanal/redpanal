from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse_lazy
from django.views.generic import ListView, UpdateView, DetailView, CreateView, DeleteView

import actstream.models
from redpanal.audio.models import Audio

def user_page(request, slug):
    user = get_object_or_404(User, username=slug)
    audios = Audio.objects.filter(user=user)
    action_list = actstream.models.user_stream(user)
    return render(request, "users/user_page.html", {
        "user": user,
        "audios": audios,
        "action_list": action_list,
    })

def user_interactions(request, slug):
    user = get_object_or_404(User, username=slug)
    return render(request, "users/user_interactions.html", {
        "user": user,
    })

@login_required
def user_profile(request):
    return render(request, "users/user_profile.html", {})


def user_list(request):
    users = User.objects.all()
    return render(request, "users/user_list.html", {
        "users": users,
    })
