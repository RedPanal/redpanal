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
    ensure_profile(user)

    return render(request, "users/user_page.html", {
        "user": user,
    })

def user_tracks(request, slug):
    user = get_object_or_404(User, username=slug)
    audios = Audio.objects.filter(user=user)

    if request.is_ajax():
        template = "audio/audios_list.html"
    else:
        template =  "users/user_tracks.html"

    return render(request, template, {
        "user": user,
        "audios": audios,
    })

def user_projects(request, slug):
    user = get_object_or_404(User, username=slug)
    projects = user.project_set.all

    if request.is_ajax():
        template = "projects/projects_list.html"
    else:
        template =  "users/user_projects.html"

    return render(request, template, {
        "user": user,
        "projects": projects,
    })

def user_activities(request, slug):
    user = get_object_or_404(User, username=slug)
    action_list = actstream.models.actor_stream(user)

    if request.is_ajax():
        template = "social/actions_list.html"
    else:
        template =  "users/user_activities.html"

    return render(request, template, {
        "user": user,
        "action_list": action_list,
    })

def user_interactions(request, slug):
    if request.user.is_authenticated():
       user = get_object_or_404(User, username=slug)
       if request.user == user:
          if request.is_ajax():
             template = "social/messages_list.html"
          else:
             template =  "users/user_interactions.html"        
          return render(request, template, {
              "user": user,
          })
       return redirect(user.get_absolute_url())
    else:
       return redirect("/accounts/login/?next=/")

@login_required
def user_profile(request):
    ensure_profile(request.user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user.userprofile)
        if form.is_valid():
            form.save()
            return redirect(request.user.get_absolute_url())
    else:
        form = UserProfileForm(instance=request.user.userprofile)
    return render(request, "users/user_profile.html", {"form":form})


def all_people(request):
    users = User.objects.all()
    if request.is_ajax():
       template = "users/users_list_full.html"
    else:
       template =  "users/all_people.html"  
    return render(request, template, {
        "users": users,
    })
