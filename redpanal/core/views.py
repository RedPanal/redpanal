from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse_lazy

from redpanal.utils.helpers import is_ajax
from audio.models import Audio
from project.models import Project
from social.models import Message, visible_messages
from users.models import UserProfile
from taggit.models import Tag
from itertools import chain

def index(request):
    """Home: what happened in my works, and where I can contribute."""
    from datetime import timedelta
    from django.utils import timezone
    from django.db.models import Count, Q
    from project.models import Contribution, PartRequest, Membership

    listed = Project.objects.listed()
    open_requests = (PartRequest.objects.filter(PartRequest.open_q(), project__in=listed)
                     .select_related("project", "project__user").order_by("-created_at"))
    # Loose sounds (loops, samples) anyone can listen to.
    sounds = (Audio.objects.visible_to(None).filter(contributions__isnull=True)
              .select_related("user").order_by("-created_at"))

    if not request.user.is_authenticated:
        from audio.models import INSTRUMENT_CHOICES
        # A public project with several layers and an open collaboration shows the idea at a glance.
        demo = (Project.objects.filter(visibility="public", moderation_hidden=False)
                .annotate(n_layers=Count("contributions", filter=Q(contributions__status=Contribution.INCLUDED,
                                                                   contributions__alignment=Contribution.ALIGNED)),
                          n_open=Count("requests", filter=Q(requests__is_open=True)))
                .filter(n_layers__gte=2).order_by("-n_open", "-n_layers", "-created_at").first())
        loose_instruments = set(sounds.exclude(instrument="").values_list("instrument", flat=True))
        return render(request, "home_anonymous.html", {
            "demo": demo,
            "demo_layers": list(demo.aligned_parts()[:5]) if demo else [],
            "demo_request": demo.open_requests().first() if demo else None,
            "requests": open_requests.select_related("project__user__userprofile")[:3],
            "recent": listed.exclude(pk=demo.pk if demo else None).select_related("user").order_by("-created_at")[:4],
            "loop_instruments": [(code, label) for code, label in INSTRUMENT_CHOICES if code in loose_instruments],
        })

    # Comunidad: what the people you follow publish. Your own things live in Estudio;
    # what others did with them arrives as notifications.
    from social.following import community_feed, following_ids, mark_reactions, related_content, feed_keys
    user = request.user
    followed = community_feed(user)
    # After what the people you follow publish, more linked to what you play and tag.
    feed = mark_reactions(user, followed + related_content(user, feed_keys(followed)))
    return render(request, "home.html", {
        # The bell carries the notifications; up here only what waits for a decision.
        "notices": list(user.notifications.filter(read_at__isnull=True, kind__in=("contributed", "access_requested"))
                        .select_related("actor", "actor__userprofile")[:2]),
        "feed": feed,
        "following_ids": following_ids(user),
    })


def robots(request):
    """Search engines: the public pages, not each person's own (studio, notices, settings, creating)."""
    from django.http import HttpResponse
    lines = ["User-agent: *"] + ["Disallow: %s" % p for p in (
        "/estudio/", "/avisos/", "/ajustes/", "/crear/", "/reproductor/", "/moderacion/", "/accounts/", "/activity/",
        "/admin/", "/api/")]
    from django.urls import reverse
    lines.append("Sitemap: %s" % request.build_absolute_uri(reverse("sitemap")))
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def service_worker(request):
    """Served from the site root so it can make the whole site installable."""
    from django.urls import reverse
    response = render(request, "core/sw.js", {"offline_url": reverse("offline")},
                      content_type="application/javascript")
    response["Cache-Control"] = "no-cache"
    return response


def offline(request):
    return render(request, "core/offline.html")


def hashtaged_list(request, slug, filters='all'):
    tag = get_object_or_404(Tag, slug=slug)

    audios = Audio.objects.visible_to(request.user).filter(tags__slug=slug).order_by('-created_at') if filters == 'all' or filters == 'audios' else []
    projects = Project.objects.visible_to(request.user).filter(tags__slug=slug).order_by('-created_at') if filters == 'all' or filters == 'projects' else []
    messages = visible_messages(Message.objects.filter(tags__slug=slug), request.user).order_by('-created_at') if filters == 'all' or filters == 'messages' else []
    users = User.objects.filter(userprofile__tags__slug=slug).order_by('-date_joined', '-pk') if filters == 'all' or filters == 'users' else []

    mixed = sorted(chain(audios, projects, messages, users), key=lambda instance: instance.created_at, reverse=True)

    if is_ajax(request):
        template = "core/mixed_list.html"
    else:
        template = "core/hashtaged_list.html"

    return render(request, template, {
           "list_type": 'mixed',
           "mixed_objects": mixed,
           "tag": tag,
           "filters": filters,
    })


def activity_all_iframe(request):

    audios = Audio.objects.visible_to(request.user)
    #projects = Project.objects.visible_to(request.user)
    messages = visible_messages(Message.objects.all(), request.user)

    mixed_list = sorted(chain(messages, audios), key=lambda instance: instance.created_at, reverse=True)

    return render(request, "all_activities_iframe.html", {
        "mixed_objects": mixed_list,
        "refresh_after_modal": 'refresh',
    })
