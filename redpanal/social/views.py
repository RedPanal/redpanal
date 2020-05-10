from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template import RequestContext
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext_lazy as _

from actstream import actions, models
from actstream.views import respond

from .forms import MessageForm, MessageWithContentForm
from .models import Message

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
        user = get_object_or_404(ctype.model_class(), pk=object_id)
        if request.is_ajax():
           template = "users/users_list.html"
        else:
           template =  "social/followers.html"
        return render(request, template, {'user': user})
    else:
        return redirect("/accounts/login/?next=/")

def following(request, user_id):
    """
    Returns a list of actors that the user identified by ``user_id`` is following (eg who im following).
    """
    if request.user.is_authenticated():
        user = get_object_or_404(User, pk=user_id)
        if request.is_ajax():
           template = "users/users_list.html"
        else:
           template =  "social/following.html"
        return render(request, template, {'user': user})
    else:
        return redirect("/accounts/login/?next=/")

def message_create(request):
    if request.method == "POST" and request.is_ajax():
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = Message(msg=form.cleaned_data["msg"], user=request.user)
            msg.save()
            return render(request, "social/message_form_popup_response.html",
                     {'response': _("Your message has been successfully posted"),
                      'object': msg,
                     })
        else:
            return HttpResponse("sonaste")
    elif request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = Message(msg=form.cleaned_data["msg"], user=request.user)
            msg.save()
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

def message_with_content_create(request):
    if request.method == "POST":
        form = MessageWithContentForm(request.POST)
        if form.is_valid():
            msg = Message(msg=form.cleaned_data["msg"], user=request.user,
                          content_type=form.cleaned_data["content_type"],
                          object_id=form.cleaned_data["object_id"])
            msg.save()
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
