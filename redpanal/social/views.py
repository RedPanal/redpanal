from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template import RequestContext
from django.views.decorators.http import require_POST
from django.contrib import messages

from core.analytics import queue_event
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _

from actstream import actions, models
from actstream.views import respond

from redpanal.utils.helpers import is_ajax
from .forms import MessageForm, MessageWithContentForm
from .models import Message

@login_required
@require_POST
def follow_unfollow(request, content_type_id, object_id, do_follow=True, actor_only=True):
    """
    Creates or deletes the follow relationship between ``request.user`` and the
    actor defined by ``content_type_id``, ``object_id``.

    POST with the CSRF token only: another site must not be able to make someone follow anybody.
    """
    ctype = get_object_or_404(ContentType, pk=content_type_id)
    actor = get_object_or_404(ctype.model_class(), pk=object_id)

    if do_follow:
        actions.follow(request.user, actor, send_action=False, actor_only=actor_only)
        queue_event(request, "follow")
        return respond(request, 201)   # CREATED
    actions.unfollow(request.user, actor)
    return respond(request, 204)   # NO CONTENT


@login_required
def person_follow(request, username):
    """Follow or stop following someone: what they publish shows up in Comunidad."""
    from .models import notify
    person = get_object_or_404(User, username=username)
    if request.method != "POST" or person == request.user:
        return redirect(person.get_absolute_url())
    if actions.is_following(request.user, person):
        actions.unfollow(request.user, person)
    else:
        actions.follow(request.user, person, send_action=False, actor_only=True)
        notify(person, request.user, "followed", "", request.user.get_absolute_url())
        queue_event(request, "follow")
    return HttpResponseRedirect(request.POST.get("next") or person.get_absolute_url())


REACTION_TARGETS = ("proyecto", "sonido", "comentario")


def _reaction_target(user, target, pk):
    """The project, sound or comment someone wants to react to, if they can see it. Returns (obj, owner, is_public)."""
    from django.http import Http404
    from audio.models import Audio
    from project.models import Project, VISIBILITY_PUBLIC
    from .models import visible_messages
    if target == "proyecto":
        obj = get_object_or_404(Project.objects.listenable_by(user), pk=pk)
        return obj, obj.user, obj.visibility == VISIBILITY_PUBLIC and not obj.moderation_hidden
    if target == "sonido":
        obj = get_object_or_404(Audio.objects.visible_to(user), pk=pk)
        return obj, obj.user, Audio.objects.visible_to(None).filter(pk=pk).exists()
    if target == "comentario":
        obj = get_object_or_404(visible_messages(Message.objects.all(), user), pk=pk)
        return obj, obj.user, visible_messages(Message.objects.filter(pk=pk), None).exists()
    raise Http404


@login_required
def react(request, kind, target, pk):
    """Favorite or amplify (toggle) anything this person can see.

    Amplifying republishes it in the Comunidad of the people who follow you. Something that isn't
    public reaches only the followers who can see it too, and never the open feeds.
    """
    from django.http import Http404
    from actstream import action
    from actstream.models import Action
    from .models import Reaction, notify
    if request.method != "POST" or kind not in (Reaction.FAVORITE, Reaction.AMPLIFY):
        raise Http404
    obj, owner, is_public = _reaction_target(request.user, target, pk)
    ct = ContentType.objects.get_for_model(obj)
    existing = Reaction.objects.filter(user=request.user, kind=kind, content_type=ct, object_id=obj.pk)
    if existing.exists():
        existing.delete()
        if kind == Reaction.AMPLIFY:
            Action.objects.filter(verb="amplified", actor_object_id=str(request.user.pk),
                                  action_object_content_type=ct, action_object_object_id=str(obj.pk)).delete()
    else:
        Reaction.objects.create(user=request.user, kind=kind, content_type=ct, object_id=obj.pk)
        name = getattr(obj, "name", "") or getattr(obj, "msg", "")[:60]
        url = obj.get_absolute_url() if hasattr(obj, "get_absolute_url") else ""
        if isinstance(obj, Message):
            url = _message_url(obj)
        if kind == Reaction.AMPLIFY:
            action.send(request.user, verb="amplified", action_object=obj, public=is_public)
            notify(owner, request.user, "amplified", name, url)
        else:
            notify(owner, request.user, "favorited", name, url)
            messages.success(request, _("Saved in your favorites: you find them in Estudio."))
    return HttpResponseRedirect(request.POST.get("next") or request.META.get("HTTP_REFERER", "/"))


def _message_url(message):
    return message.get_absolute_url()


@login_required
def reply(request, target, pk):
    """Answer from the feed: a comment on a project or sound, or a reply to a comment (one level)."""
    from django.core.exceptions import PermissionDenied
    from django.http import Http404
    from audio.models import Audio
    from project.models import Project
    from .models import notify
    text = request.POST.get("msg", "").strip()[:1000]
    if request.method != "POST" or not text:
        raise Http404
    obj, owner, _public = _reaction_target(request.user, target, pk)
    if isinstance(obj, Project):
        if not obj.can_contribute(request.user):
            raise PermissionDenied
        Message.objects.create(msg=text, user=request.user, content_object=obj)
    elif isinstance(obj, Audio):
        Message.objects.create(msg=text, user=request.user, content_object=obj)
    else:
        parent = obj.parent or obj  # one level: replies to a reply hang from the same comment
        about = parent.content_object
        if isinstance(about, Project) and not about.can_contribute(request.user):
            raise PermissionDenied
        Message.objects.create(msg=text, user=request.user, parent=parent,
                               content_type=parent.content_type, object_id=parent.object_id)
        about_owner = about if isinstance(about, User) else getattr(about, "user", None)
        # Who wrote the comment and, when answering a reply, who wrote that reply.
        # The owner of the project or sound already hears about every comment.
        for person in {parent.user, obj.user} - {about_owner}:
            notify(person, request.user, "replied", getattr(about, "name", "") or parent.msg[:60],
                   _message_url(parent))
    return HttpResponseRedirect(request.POST.get("next") or request.META.get("HTTP_REFERER", "/"))


@login_required
def notifications(request):
    """What other people did with you and your work. Opening the page marks everything as seen."""
    from django.utils import timezone
    items = list(request.user.notifications.select_related("actor", "actor__userprofile")[:100])
    request.user.notifications.filter(read_at__isnull=True).update(read_at=timezone.now())
    return render(request, "social/notifications.html", {"items": items})


def followers(request, content_type_id, object_id):
    """
    Creates a listing of ``User``s that follow the actor defined by
    ``content_type_id``, ``object_id``.
    """
    if request.user.is_authenticated:
        ctype = get_object_or_404(ContentType, pk=content_type_id)
        user = get_object_or_404(ctype.model_class(), pk=object_id)
        if is_ajax(request):
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
    if request.user.is_authenticated:
        user = get_object_or_404(User, pk=user_id)
        if is_ajax(request):
           template = "users/users_list.html"
        else:
           template =  "social/following.html"
        return render(request, template, {'user': user})
    else:
        return redirect("/accounts/login/?next=/")

@login_required
def message_create(request):
    if request.method == "POST" and is_ajax(request):
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = Message(msg=form.cleaned_data["msg"], user=request.user)
            msg.save()
            queue_event(request, "post")
            return render(request, "social/message_form_popup_response.html",
                     {'response': _("Your message has been successfully posted"),
                      'object': msg,
                     })
        else:
            return HttpResponse("Sonaste, no se pudo enviar el mensaje")
    elif request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = Message(msg=form.cleaned_data["msg"], user=request.user)
            msg.save()
            queue_event(request, "post")
            # Posted from the floating pen on any page: say so, and where it can be seen.
            messages.success(request, _("Posted. It's on your profile and in the Comunidad of the people who follow you."))
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

@login_required
def message_with_content_create(request):
    """A comment on a sound or a project, by someone who may comment there."""
    from django.core.exceptions import PermissionDenied
    from audio.models import Audio
    from project.models import Project
    if request.method == "POST":
        form = MessageWithContentForm(request.POST)
        if form.is_valid():
            model = form.cleaned_data["content_type"].model_class()
            pk = form.cleaned_data["object_id"]
            if model is Audio:
                about = get_object_or_404(Audio.objects.visible_to(request.user), pk=pk)
            elif model is Project:
                about = get_object_or_404(Project, pk=pk)
                if not about.can_contribute(request.user):
                    raise PermissionDenied
            else:
                raise PermissionDenied
            Message.objects.create(msg=form.cleaned_data["msg"], user=request.user, content_object=about)
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
