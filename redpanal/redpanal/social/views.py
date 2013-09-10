from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from actstream import actions, models

def followers(request, content_type_id, object_id):
    """
    Creates a listing of ``User``s that follow the actor defined by
    ``content_type_id``, ``object_id``.
    """
    ctype = get_object_or_404(ContentType, pk=content_type_id)
    actor = get_object_or_404(ctype.model_class(), pk=object_id)
    return render_to_response('social/followers.html', {
        'followers': models.followers(actor), 'actor': actor
    }, context_instance=RequestContext(request))


def following(request, user_id):
    """
    Returns a list of actors that the user identified by ``user_id`` is following (eg who im following).
    """
    user = get_object_or_404(User, pk=user_id)
    return render_to_response('social/following.html', {
        'following': models.following(user), 'user': user
    }, context_instance=RequestContext(request))


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

