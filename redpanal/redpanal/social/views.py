from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType


from actstream import actions, models
from actstream.views import respond

@login_required
@csrf_exempt
def follow_unfollow(request, content_type_id, object_id, do_follow=True, actor_only=True):
    """
    Creates or deletes the follow relationship between ``request.user`` and the
    actor defined by ``content_type_id``, ``object_id``.
    """
    ctype = get_object_or_404(ContentType, pk=content_type_id)
    actor = get_object_or_404(ctype.model_class(), pk=object_id)

    if do_follow:
        actions.follow(request.user, actor, send_action=False, actor_only=actor_only)
        return respond(request, 201)   # CREATED
    actions.unfollow(request.user, actor)
    return respond(request, 204)   # NO CONTENT


def followers(request, content_type_id, object_id):
    """
    Creates a listing of ``User``s that follow the actor defined by
    ``content_type_id``, ``object_id``.
    """
    if request.user.is_authenticated():
        ctype = get_object_or_404(ContentType, pk=content_type_id)
        actor = get_object_or_404(ctype.model_class(), pk=object_id)
        return render_to_response('social/followers.html', {
            'followers': models.followers(actor)[::-1],
            'following': models.following(actor)[::-1],
            'actor': actor
        }, context_instance=RequestContext(request))
    else:
        return redirect("/accounts/login/?next=/")

def following(request, user_id):
    """
    Returns a list of actors that the user identified by ``user_id`` is following (eg who im following).
    """
    if request.user.is_authenticated():
        user = get_object_or_404(User, pk=user_id)
        return render_to_response('social/following.html', {
            'following': models.following(user)[::-1],
            'followers': models.followers(user)[::-1],
            'user': user
        }, context_instance=RequestContext(request))
    else:
        return redirect("/accounts/login/?next=/")

from forms import MessageForm
from models import Message

def message_create(request):
    if request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            # TODO: content_object
            msg = Message(msg=form.cleaned_data["msg"], user=request.user)
            msg.save()
    return HttpResponseRedirect("/")

