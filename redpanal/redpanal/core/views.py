from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse_lazy

from redpanal.audio.models import Audio
from redpanal.project.models import Project
from redpanal.social.models import Message

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

    audios = Audio.objects.filter(tags__slug=slug)
    projects = Project.objects.filter(tags__slug=slug)
    messages = Message.objects.filter(tags__slug=slug)

    return render(request, "core/hashtaged_list.html", {
        "audios": audios,
        "projects": projects,
        "messages": messages,
        "tag": slug,
    })

