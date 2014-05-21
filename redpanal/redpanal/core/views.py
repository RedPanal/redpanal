from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse_lazy

from redpanal.audio.models import Audio
from redpanal.project.models import Project
from redpanal.social.models import Message
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
        'following': actstream.models.following(request.user)[::-1],
        'followers': actstream.models.followers(request.user)[::-1]
        })
    else:
        return redirect("/accounts/login/?next=/")

    if request.is_ajax():
        template = "social/actions_list.html"
    else:
        template =  "index.html"
    return render(request, template, context)

def stream(request):
    """
    Index page for authenticated user's activity stream. (Eg: Your feed at
    github.com)
    """
    return render_to_response('activity/actor.html', {
        'ctype': ContentType.objects.get_for_model(User),
        'actor': request.user, 'action_list': models.user_stream(request.user)
    }, context_instance=RequestContext(request))

def hashtaged_list(request, slug):

    #if Tag.objects.filter(slug=slug).count() == 0:
    #   redirect? si no existe tag adonde vamos?

    tag = Tag.objects.get(slug=slug)
    audios = Audio.objects.filter(tags__slug=slug)
    projects = Project.objects.filter(tags__slug=slug)
    messages = Message.objects.filter(tags__slug=slug)
    #users = User.objects.filter(tags__slug=slug).order_by('-created_at') #ToDo !!

    mixed = sorted(
       chain(audios, projects, messages),
       key=lambda instance: instance.created_at)

    if request.is_ajax():
        template = "core/mixed_list.html"
    else:
        template = "core/hashtaged_list.html"

    return render(request, template, {
           "list_type": 'mixed',
           "mixed_objects": mixed,
           "tag": tag,
    })

def hashtaged_list_messages(request, slug):

    tag = Tag.objects.get(slug=slug)
    messages = Message.objects.filter(tags__slug=slug).order_by('-created_at')

    if request.is_ajax():
        template = "core/mixed_list.html"
    else:
        template = "core/hashtaged_list.html"

    return render(request, template, {
           "list_type": 'messages',
           "mixed_objects": messages,
           "tag": tag,
    })

def hashtaged_list_projects(request, slug):

    tag = Tag.objects.get(slug=slug)
    projects = Project.objects.filter(tags__slug=slug).order_by('-created_at')

    if request.is_ajax():
        template = "core/mixed_list.html"
    else:
        template = "core/hashtaged_list.html"

    return render(request, template, {
           "list_type": 'projects',
           "mixed_objects": projects,
           "tag": tag,
    })

def hashtaged_list_audios(request, slug):

    tag = Tag.objects.get(slug=slug)
    audios = Audio.objects.filter(tags__slug=slug).order_by('-created_at')

    if request.is_ajax():
        template = "core/mixed_list.html"
    else:
        template = "core/hashtaged_list.html"

    return render(request, template, {
           "list_type": 'audios',
           "mixed_objects": audios,
           "tag": tag,
    })

