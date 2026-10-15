from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.core.exceptions import ObjectDoesNotExist
from django.views.generic import ListView, UpdateView, DetailView, CreateView, DeleteView

import actstream.models
from redpanal.utils.helpers import is_ajax
from audio.models import Audio
from .models import create_profile
from .forms import UserProfileForm, DeleteUserForm

def ensure_profile(user):
    try:
        user.userprofile
    except ObjectDoesNotExist:
        create_profile(user)

def user_page(request, username):
    user = get_object_or_404(User, username=username)
    ensure_profile(user)

    return render(request, "users/user_page.html", {
        "user": user,
        "refresh_after_modal": 'refresh',
    })

def profile(request, username):
    """A person on RedPanal: what they play, their works, the parts they gave to others and their sounds."""
    from project.models import Project, Contribution
    person = get_object_or_404(User, username=username)
    ensure_profile(person)
    viewer = request.user
    visible_works = Project.objects.visible_to(viewer)
    contributions = (Contribution.objects
                     .filter(contributor=person, status=Contribution.INCLUDED, project__in=visible_works)
                     .exclude(project__user=person)
                     .select_related("project", "project__user", "audio")
                     .order_by("-created_at"))
    from django.db.models import Q
    from project.models import WorkGroup
    from social.models import Message, visible_messages
    from social.following import following_ids
    # Posts from the profile (nothing attached) and comments on projects and sounds; replies stay in their thread.
    comments = [m for m in visible_messages(Message.objects.filter(user=person, parent__isnull=True), viewer)
                .select_related("content_type").prefetch_related("replies__user").order_by("-created_at")[:15]
                if m.object_id is None or m.content_object is not None]
    if viewer.is_authenticated and comments:
        from social.models import Reaction
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Message)
        mine = {(r.kind, r.object_id) for r in Reaction.objects.filter(user=viewer, content_type=ct,
                                                                         object_id__in=[m.pk for m in comments])}
        for m in comments:
            m.is_favorite = (Reaction.FAVORITE, m.pk) in mine
            m.is_amplified = (Reaction.AMPLIFY, m.pk) in mine
            about = m.content_object
            m.is_public = about is None or getattr(about, "visibility", "public") == "public"
    # Groups are often school classes: only people inside a group see it on someone's profile.
    groups = WorkGroup.objects.filter(Q(owner=person) | Q(members__user=person)).distinct()
    if viewer != person:
        groups = groups.filter(Q(owner=viewer) | Q(members__user=viewer)).distinct() if viewer.is_authenticated \
            else groups.none()
    from project.models import PartRequest, WorkSource
    # People who played in the same projects (owners and included layers), in projects the viewer can see.
    shared = visible_works.filter(Q(user=person) | Q(contributions__contributor=person,
                                                       contributions__status=Contribution.INCLUDED)).distinct()
    played_with = list(User.objects.filter(Q(project__in=shared) | Q(contributions__project__in=shared,
                                                                       contributions__status=Contribution.INCLUDED))
                       .exclude(pk=person.pk).select_related("userprofile").distinct()[:12])
    reused = WorkSource.objects.filter(project__in=visible_works).filter(
        Q(audio__user=person) | Q(source_project__user=person)).count()
    # Collaborations that match what this person plays show in their Comunidad, not here:
    # the profile is how others see them.
    invite_to = (list(Project.objects.filter(user=viewer).exclude(memberships__user=person).order_by("-created_at")[:20])
                 if viewer.is_authenticated and viewer != person else [])
    images = list(person.profile_images.all())
    return render(request, "users/profile.html", {
        "gallery": images,
        "person": person,
        "is_me": viewer == person,
        "played_with": played_with,
        "reused": reused,
        "invite_to": invite_to,
        "works": visible_works.filter(user=person).select_related("user").order_by("-created_at"),
        "contributions": contributions,
        "sounds": (Audio.objects.visible_to(viewer).filter(user=person, contributions__isnull=True)
                   .select_related("user").order_by("-created_at")),
        "comments": comments,
        "groups": groups,
        "following_ids": following_ids(viewer),
    })


def user_tracks(request, username):
    """Old "tracks" tab: the profile now shows works, contributions and sounds."""
    return profile(request, username)


def user_projects(request, username):
    return redirect("user-tracks", username=username)

def user_activities(request, username):
    user = get_object_or_404(User, username=username)
    action_list = actstream.models.actor_stream(user)

    if is_ajax(request):
        template = "social/actions_list.html"
    else:
        template =  "users/user_activities.html"

    return render(request, template, {
        "user": user,
        "action_list": action_list,
        "refresh_after_modal": 'refresh',
    })


def user_interactions(request, username):
    if request.user.is_authenticated:
        user = get_object_or_404(User, username=username)
        if request.user == user:
            if is_ajax(request):
                template = "social/messages_list.html"
            else:
                template = "users/user_interactions.html"
            return render(request, template, {
                "user": user,
            })
        return redirect(user.get_absolute_url())
    else:
        return redirect("/accounts/login/?next=/")


@login_required
def user_profile(request):
    ensure_profile(request.user)

    from social.models import Notification
    avatar_error = None
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user.userprofile)
        if "avatar" in request.FILES:
            avatar_error = _save_avatar(request)
        avatar_error = avatar_error or _save_gallery(request)
        if form.is_valid() and not avatar_error:
            profile = form.save(commit=False)
            wanted = set(request.POST.getlist("notify"))
            profile.notify_off = [k for k, _label in Notification.PREFERENCES if k not in wanted]
            _choose_language_and_colors(request, profile)
            profile.save()
            return _with_language(redirect(request.user.get_absolute_url()), profile.language)
    else:
        form = UserProfileForm(instance=request.user.userprofile)
    off = set(request.user.userprofile.notify_off or [])
    from .models import PROFILE_IMAGES_MAX, PALETTE_CHOICES
    gallery = list(request.user.profile_images.all())
    return render(request, "users/user_profile.html", {
        "form": form, "avatar_error": avatar_error,
        "gallery": gallery, "gallery_left": PROFILE_IMAGES_MAX - len(gallery), "gallery_max": PROFILE_IMAGES_MAX,
        "notify_choices": [(k, label, k not in off) for k, label in Notification.PREFERENCES],
        "palettes": PALETTE_CHOICES,
    })


def _choose_language_and_colors(request, profile):
    from django.conf import settings
    from .models import PALETTE_CHOICES
    if "language" in request.POST:
        lang = request.POST["language"]
        profile.language = lang if lang in dict(settings.LANGUAGES) else ""
    if request.POST.get("palette") in dict(PALETTE_CHOICES):
        profile.palette = request.POST["palette"]


def _with_language(response, lang):
    """The chosen language right away, also in the cookie; none chosen: back to the browser's."""
    from django.conf import settings
    if lang:
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang, max_age=365 * 24 * 3600, samesite="Lax")
    else:
        response.delete_cookie(settings.LANGUAGE_COOKIE_NAME)
    return response


@require_POST
def set_language(request):
    """The language menu at the bottom of every page: for everyone; with an account, it's also saved."""
    from django.conf import settings
    from django.utils.http import url_has_allowed_host_and_scheme
    lang = request.POST.get("language", "")
    if lang not in dict(settings.LANGUAGES):
        lang = ""
    if request.user.is_authenticated:
        ensure_profile(request.user)
        request.user.userprofile.language = lang
        request.user.userprofile.save(update_fields=["language"])
    back = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        back = "/"
    return _with_language(redirect(back), lang)

def _save_gallery(request):
    """The profile's pictures: remove the ones marked, add new ones up to ten. Returns an error or None."""
    from django import forms
    from django.core.exceptions import ValidationError
    from .models import ProfileImage, PROFILE_IMAGES_MAX
    remove = [int(pk) for pk in request.POST.getlist("gallery-remove") if pk.isdigit()]
    if remove:
        ProfileImage.objects.filter(user=request.user, pk__in=remove).delete()
    files = request.FILES.getlist("gallery")
    room = PROFILE_IMAGES_MAX - ProfileImage.objects.filter(user=request.user).count()
    checker = forms.ImageField()
    for f in files[:max(0, room)]:
        try:
            checker.clean(f)
        except ValidationError:
            return _("«%s» is not an image.") % f.name
        ProfileImage.objects.create(user=request.user, image=f)
    if len(files) > room:
        return _("Up to %d pictures: the rest were left out.") % PROFILE_IMAGES_MAX
    return None


def _save_avatar(request):
    """The picture that represents you, uploaded from the profile itself. Returns an error or None."""
    from avatar.forms import UploadAvatarForm
    from avatar.models import Avatar
    from avatar.signals import avatar_updated
    upload = UploadAvatarForm(request.POST, request.FILES, user=request.user)
    if not upload.is_valid():
        return " ".join(str(e) for errors in upload.errors.values() for e in errors)
    avatar = Avatar(user=request.user, primary=True)
    image = request.FILES["avatar"]
    avatar.avatar.save(image.name, image)
    avatar.save()
    avatar_updated.send(sender=Avatar, user=request.user, avatar=avatar)
    return None


def all_people(request):
    users = User.objects.order_by("-date_joined", "-pk")  # a fixed order, so pages don't repeat or skip people
    if is_ajax(request):
       template = "users/users_list_full.html"
    else:
       template =  "users/all_people.html"  
    return render(request, template, {
        "users": users,
    })

@login_required
def delete_account(request):
    if request.method == 'POST':
        form = DeleteUserForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['delete']:
                request.user.delete()
        return redirect('index')
    else:
        form = DeleteUserForm()
    return render(request, "users/delete_account.html", {"form": form})
