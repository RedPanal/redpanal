from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse_lazy

from redpanal.audio.models import Audio
from redpanal.project.models import Project
from redpanal.social.models import Message
from redpanal.users.models import UserProfile
from taggit.models import Tag
from itertools import chain
import actstream.models

def index(request):
    context = {}
    if request.user.is_authenticated():
        context.update({
        'ctype': ContentType.objects.get_for_model(User),
        'actor': request.user,
        'action_list': actstream.models.user_stream(request.user),
        })
    else:
        return redirect("/accounts/login/?next=/")

    if request.is_ajax():
        template = "social/actions_list.html"
    else:
        template =  "index.html"
    return render(request, template, context)

def hashtaged_list(request, slug, filters='all'):
    tag = get_object_or_404(Tag, slug=slug)

    audios = Audio.objects.filter(tags__slug=slug).order_by('-created_at') if filters == 'all' or filters == 'audios' else [] 
    projects = Project.objects.filter(tags__slug=slug).order_by('-created_at') if filters == 'all' or filters == 'projects' else []
    messages = Message.objects.filter(tags__slug=slug).order_by('-created_at') if filters == 'all' or filters == 'messages' else []
    users = User.objects.filter(userprofile__tags__slug=slug) if filters == 'all' or filters == 'users' else []

    mixed = sorted(chain(audios, projects, messages, users), key=lambda instance: instance.created_at)

    if request.is_ajax():
        template = "core/mixed_list.html"
    else:
        template = "core/hashtaged_list.html"

    return render(request, template, {
           "list_type": 'mixed',
           "mixed_objects": mixed,
           "tag": tag,
    })
