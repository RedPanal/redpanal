from django import template

register = template.Library()


@register.filter
def display_name(user):
    """The name a person chose, or their username."""
    profile = getattr(user, "userprofile", None)
    if profile is not None and profile.realname:
        return profile.realname
    return user.username


def _thumb(image):
    if not image:
        return ""
    try:
        from easy_thumbnails.files import get_thumbnailer
        return get_thumbnailer(image).get_thumbnail({"size": (112, 112), "crop": True}).url
    except Exception:
        return ""


def _work_item(work, audio=None):
    """What the persistent player shows for a work: its name, who started it, its cover."""
    return {"id": audio.pk if audio is not None else "", "title": work.name, "artist": display_name(work.user),
            "url": work.get_absolute_url(), "cover": _thumb(work.image)}


@register.inclusion_tag("project/_mini_player.html", takes_context=True)
def work_player(context, work):
    """Listen to a work without leaving the page: its aligned parts, or the preview of an open call.

    A single file plays in the persistent player; several parts in sync play here, with Web Audio.
    """
    from django.urls import reverse
    request = context.get("request")
    user = getattr(request, "user", None)
    tracks, mode, item = [], "work", None
    if work.can_listen(user, request):
        parts = list(work.aligned_parts())
        tracks = [{"src": c.audio.get_stream_url(), "peaks": reverse("audio_peaks_json", args=[c.audio_id]),
                   "offset": c.offset_ms, "duration": c.audio.get_duration() or ""} for c in parts]
        if len(parts) == 1:
            item = _work_item(work, parts[0].audio)
    elif work.preview:
        tracks, mode = [{"src": work.preview.url, "peaks": work.preview_peaks_url(), "offset": 0}], "preview"
        item = _work_item(work)
    return {"tracks": tracks, "mode": mode, "label": work.name, "item": item}


def file_row(work, contribution):
    """One file of a work, ready for the compact player: what it is, who made it, what the player shows."""
    from django.urls import reverse
    audio = contribution.audio
    caption, who = part_role(audio), display_name(contribution.contributor)
    return {
        "tracks": [{"src": audio.get_stream_url(), "peaks": reverse("audio_peaks_json", args=[audio.pk]), "offset": 0,
                    "duration": audio.get_duration() or ""}],
        "mode": "audio", "label": "%s · %s" % (caption, work.name), "caption": caption, "caption_sub": who,
        # Every track has its own page, like any file.
        "caption_url": audio.get_absolute_url(),
        "item": {"id": audio.pk, "title": "%s · %s" % (caption, work.name), "artist": who,
                 "url": audio.get_absolute_url(), "cover": _thumb(work.image)},
    }


@register.inclusion_tag("project/_work_files.html", takes_context=True)
def work_files(context, work):
    """Every file of a work, each one with its own play: works are rarely in sync, so there is no
    "play the work". Clicking one plays it and then the others. An open call shows its preview."""
    request = context.get("request")
    user = getattr(request, "user", None)
    if work.can_listen(user, request):
        parts = [c for c in work.parts().select_related("audio", "audio__user", "contributor__userprofile")
                 if not c.audio.moderation_hidden or c.audio.user == user]
        return {"rows": [file_row(work, c) for c in parts]}
    if work.preview:
        return {"rows": [{"tracks": [{"src": work.preview.url, "peaks": work.preview_peaks_url(), "offset": 0}],
                          "mode": "preview", "label": work.name, "item": _work_item(work)}]}
    return {"rows": []}


@register.inclusion_tag("project/_mini_player.html")
def contribution_player(work, contribution, grouped=False):
    """One file of a work, on its page. Under an instrument heading (`grouped`), the row names only who played it."""
    row = file_row(work, contribution)
    if grouped:
        row["caption"], row["caption_sub"] = row["caption_sub"], ""
    return row


@register.inclusion_tag("project/_mini_player.html")
def preview_player(work, size="small"):
    """The short preview of an open call, as people outside the work hear it."""
    tracks = [{"src": work.preview.url, "peaks": work.preview_peaks_url(), "offset": 0}] if work.preview else []
    return {"tracks": tracks, "mode": "preview", "label": work.name, "size": size, "item": _work_item(work)}


@register.inclusion_tag("project/_mini_player.html", takes_context=True)
def audio_player(context, audio, size="small"):
    """The same player for a single audio: loose sounds, loose parts of a work, older pages."""
    from django.urls import reverse
    request = context.get("request")
    user = getattr(request, "user", None)
    tracks, item = [], None
    if audio.can_listen(user, request):
        tracks = [{"src": audio.get_stream_url(), "peaks": reverse("audio_peaks_json", args=[audio.pk]), "offset": 0,
                   "duration": audio.get_duration() or ""}]
        item = {"id": audio.pk, "title": audio.name, "artist": display_name(audio.user),
                "url": audio.get_absolute_url(), "cover": _thumb(audio.image)}
    return {"tracks": tracks, "mode": "audio", "label": audio.name, "size": size, "tempo": audio.tempo, "item": item}


@register.simple_tag(takes_context=True)
def visible_count(context, owner, kind):
    """How many audios or works of `owner` the person looking can see."""
    from audio.models import Audio
    from project.models import Project
    request = context.get("request")
    viewer = getattr(request, "user", None)
    if kind == "audios":
        return Audio.objects.visible_to(viewer).filter(user=owner).count()
    return Project.objects.visible_to(viewer).filter(user=owner).count()


@register.filter
def is_moderator(user):
    from moderation.models import is_moderator as check
    return check(user)


@register.filter
def mmss(ms):
    """Milliseconds as m:ss."""
    try:
        seconds = int(ms) // 1000
    except (TypeError, ValueError):
        return ""
    return "%d:%02d" % (seconds // 60, seconds % 60)


@register.filter
def part_role(audio):
    """What a part is: its instrument, or its name when it has none."""
    if audio.instrument:
        return audio.get_instrument_display().capitalize()
    return audio.name
