"""What the persistent player needs from the server: tracks as JSON, what to play next, and the
person's collections (favorites, downloads, playlists)."""
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Audio, Download, Playlist, PlaylistItem

NEXT_SIZE = 10


def _cover(audio):
    if not audio.image:
        return ""
    try:
        from easy_thumbnails.files import get_thumbnailer
        return get_thumbnailer(audio.image).get_thumbnail({"size": (112, 112), "crop": True}).url
    except Exception:
        return ""


def track_json(audio):
    """One sound, as the player needs it."""
    from project.templatetags.obra_tags import display_name
    duration = audio.get_duration()
    return {
        "id": audio.pk,
        "title": audio.name,
        "artist": display_name(audio.user),
        "url": audio.get_absolute_url(),
        "src": audio.get_stream_url(),
        "peaks": reverse("audio_peaks_json", args=[audio.pk]),
        "duration": round(duration / 1000, 2) if duration else None,
        "cover": _cover(audio),
    }


def similar_audios(user, seed, exclude=(), limit=NEXT_SIZE):
    """Sounds like `seed` this person can hear: shared hashtags first, then instrument and genre;
    the newest shared sounds fill the rest. Parts of works stay out: they make sense with their work."""
    pool = (Audio.objects.visible_to(user).filter(contributions__isnull=True)
            .exclude(pk__in=list(exclude) + [seed.pk]).select_related("user", "user__userprofile"))
    tags = list(seed.tags.values_list("pk", flat=True))
    related = Q(pk__in=[])
    if tags:
        related |= Q(tags__in=tags)
    if seed.instrument:
        related |= Q(instrument=seed.instrument)
    if seed.genre:
        related |= Q(genre=seed.genre)
    picked = list(pool.filter(related)
                  .annotate(shared=Count("tags", filter=Q(tags__in=tags), distinct=True))
                  .order_by("-shared", "-created_at").distinct()[:limit])
    if len(picked) < limit:
        picked += list(pool.exclude(pk__in=[a.pk for a in picked]).order_by("-created_at")[:limit - len(picked)])
    return picked


def _ids(value, cap=300):
    out = []
    for part in (value or "").split(",")[:cap]:
        if part.strip().isdigit():
            out.append(int(part))
    return out


def next_tracks(request, pk):
    """What plays after a sound: others like it."""
    seed = get_object_or_404(Audio.objects.visible_to(request.user), pk=pk)
    exclude = _ids(request.GET.get("excluir"))
    return JsonResponse({"tracks": [track_json(a) for a in similar_audios(request.user, seed, exclude)]})


def track_detail(request, pk):
    """Everything the expanded player ("Escuchando") shows about a sound: what it is, where it belongs,
    and what this person can do with it."""
    from .views import _can_download
    from social.following import reaction_state
    audio = get_object_or_404(Audio.objects.visible_to(request.user), pk=pk)
    labels = [audio.get_use_type_display().capitalize() if audio.use_type else "",
              "%d BPM" % audio.tempo if audio.tempo else "", audio.musical_key,
              audio.get_instrument_display().capitalize() if audio.instrument else ""]
    work = (audio.contributions.select_related("project").filter(project__in=_listenable_projects(request.user))
            .first())
    favorite, amplified = reaction_state(request.user, audio)
    own = request.user.is_authenticated and request.user == audio.user
    return JsonResponse({
        "id": audio.pk, "labels": [l for l in labels if l],
        "project": {"name": work.project.name, "url": work.project.get_absolute_url()} if work else None,
        "download": reverse("audio-download", args=[audio.pk]) if _can_download(request, audio) else "",
        "can_react": request.user.is_authenticated and not own,
        "favorite": favorite, "amplified": amplified,
        "favorite_url": reverse("react", args=["favorite", "sonido", audio.pk]),
        "amplify_url": reverse("react", args=["amplify", "sonido", audio.pk]),
    })


def _listenable_projects(user):
    from project.models import Project
    return Project.objects.listenable_by(user)


def _visible(user, audios):
    allowed = set(Audio.objects.visible_to(user).filter(pk__in=[a.pk for a in audios]).values_list("pk", flat=True))
    return [a for a in audios if a.pk in allowed]


@login_required
def favorites(request):
    from django.contrib.contenttypes.models import ContentType
    from social.models import Reaction
    ids = list(Reaction.objects.filter(user=request.user, kind=Reaction.FAVORITE,
                                       content_type=ContentType.objects.get_for_model(Audio))
               .order_by("-created_at").values_list("object_id", flat=True)[:200])
    by_id = Audio.objects.in_bulk(ids)
    audios = _visible(request.user, [by_id[i] for i in ids if i in by_id])
    return JsonResponse({"tracks": [track_json(a) for a in audios]})


@login_required
def downloads(request):
    audios = [d.audio for d in Download.objects.filter(user=request.user).select_related("audio", "audio__user")[:200]]
    return JsonResponse({"tracks": [track_json(a) for a in _visible(request.user, audios)]})


@login_required
def playlists(request):
    lists = Playlist.objects.filter(user=request.user).annotate(n=Count("items"))
    return JsonResponse({"playlists": [{"id": p.pk, "name": p.name, "count": p.n} for p in lists]})


def _own_playlist(request, pk):
    return get_object_or_404(Playlist, pk=pk, user=request.user)


@login_required
def playlist_tracks(request, pk):
    playlist = _own_playlist(request, pk)
    audios = [i.audio for i in playlist.items.select_related("audio", "audio__user")]
    return JsonResponse({"id": playlist.pk, "name": playlist.name,
                         "tracks": [track_json(a) for a in _visible(request.user, audios)]})


def _audio_from_post(request):
    pk = request.POST.get("audio", "")
    if not pk.isdigit():
        return None
    audio = Audio.objects.visible_to(request.user).filter(pk=int(pk)).first()
    if audio is None:
        raise Http404
    return audio


@login_required
@require_POST
def playlist_create(request):
    name = request.POST.get("name", "").strip()[:100]
    if not name:
        return JsonResponse({"error": "name"}, status=400)
    audio = _audio_from_post(request)
    playlist = Playlist.objects.create(user=request.user, name=name)
    if audio is not None:
        PlaylistItem.objects.create(playlist=playlist, audio=audio)
    return JsonResponse({"id": playlist.pk, "name": playlist.name, "count": 1 if audio else 0})


@login_required
@require_POST
def playlist_add(request, pk):
    playlist = _own_playlist(request, pk)
    audio = _audio_from_post(request)
    if audio is None:
        return JsonResponse({"error": "audio"}, status=400)
    PlaylistItem.objects.get_or_create(playlist=playlist, audio=audio)
    playlist.save(update_fields=["updated_at"])
    return JsonResponse({"ok": True})


@login_required
@require_POST
def playlist_remove(request, pk):
    playlist = _own_playlist(request, pk)
    audio = _audio_from_post(request)
    if audio is not None:
        PlaylistItem.objects.filter(playlist=playlist, audio=audio).delete()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def playlist_delete(request, pk):
    _own_playlist(request, pk).delete()
    return JsonResponse({"ok": True})
