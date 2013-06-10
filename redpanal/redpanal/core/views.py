from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from redpanal.audio.models import AudioFile

import actstream.models

def index(request):
    context = {}
    if request.user.is_authenticated():
        context.update({
        'ctype': ContentType.objects.get_for_model(User),
        'actor': request.user,
        'action_list': actstream.models.user_stream(request.user)
        })
    return render(request, "index.html", context)

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

    audios = AudioFile.objects.filter(tags__name=slug)

    return render(request, "core/hashtaged_list.html", {
        "audios": audios,
        "tag": slug,
    })

def user_page(request, slug):
    user = get_object_or_404(User, username=slug)
    audios = AudioFile.objects.filter(user=user)
    action_list = actstream.models.user_stream(user)
    return render(request, "core/user_page.html", {
        "user": user,
        "audios": audios,
        "action_list": action_list,
    })

@login_required
def user_profile(request):
    return render(request, "core/user_profile.html", {})
