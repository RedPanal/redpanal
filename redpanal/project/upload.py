"""Uploading, as easy as possible: Subir (one file, many, a folder) or Grabar.

1. Each file comes in on its own (audio.ingest), private, with a name and guesses.
2. With several files: are they the same project? With the same length: stems in sync?
3. Complete what's missing (it can wait: Estudio reminds it).
4. Share: open to everyone, with a group, with one person, or keep it private.
"""
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy
from django.views.decorators.http import require_POST
from actstream import action

from audio.ingest import ingest
from audio.models import Audio, Download, INSTRUMENT_CHOICES, TYPE_CHOICES, UPLOAD_TYPES
from audio.uploads import ACCEPTED_EXTENSIONS
from .models import (ATTACHMENT_EXTENSIONS, Contribution, Membership, Project, VISIBILITY_PRIVATE,
                     VISIBILITY_PUBLIC, WorkGroup, guess_alignment)

SAME_LENGTH_TOLERANCE = 0.01  # stems exported from one session last the same, give or take 1 %


def _my_groups(user):
    return WorkGroup.objects.filter(Q(owner=user) | Q(members__user=user)).distinct()


def _context(request):
    """Where the upload starts from: a sound it comes from, a work it's based on, a group."""
    data = request.POST if request.method == "POST" else request.GET
    sound = source = group = None
    if str(data.get("sonido", "")).isdigit():
        # Any file someone can hear, a track of a work included.
        sound = Audio.objects.visible_to(request.user).filter(pk=data["sonido"]).exclude(user=request.user).first()
    if data.get("from"):
        source = Project.objects.listenable_by(request.user).filter(slug=data["from"]).first()
    if str(data.get("grupo", "")).isdigit():
        group = _my_groups(request.user).filter(pk=data["grupo"]).first()
    return {"sound": sound, "source": source, "group": group}


@login_required
def upload_start(request):
    """Subir or Grabar. Everything else comes after the files are in."""
    ctx = _context(request)
    from django.utils import formats
    ctx.update({
        "default_name": _("Project from %s") % formats.date_format(timezone.localdate()),
        "my_projects": Project.objects.filter(user=request.user).order_by("-created_at")[:30],
        "audio_extensions": ACCEPTED_EXTENSIONS, "attachment_extensions": ATTACHMENT_EXTENSIONS,
    })
    return render(request, "project/upload.html", ctx)


@login_required
@require_POST
def upload_file(request):
    """One file at a time, so many files never make one huge request and each shows its progress."""
    f = request.FILES.get("audio")
    if f is None:
        return JsonResponse({"error": _("Couldn't read uploaded file")}, status=400)
    try:
        audio = ingest(request.user, f)
    except ValidationError as e:
        return JsonResponse({"error": " ".join(e.messages)}, status=400)
    duration = audio.get_duration()
    return JsonResponse({"id": audio.pk, "name": audio.name, "instrument": audio.instrument,
                         "type": audio.use_type, "duration": round(duration / 1000, 3) if duration else None})


def _own_audios(user, ids):
    audios = list(Audio.objects.filter(user=user, pk__in=ids))
    if len(audios) != len(set(ids)):
        raise Http404
    return sorted(audios, key=lambda a: ids.index(a.pk))


def _ids(value):
    return [int(x) for x in str(value or "").replace(" ", "").split(",") if x.isdigit()][:200]


def same_length(audios):
    durations = [a.get_duration() for a in audios]
    if len(durations) < 2 or not all(durations):
        return False
    return (max(durations) - min(durations)) <= max(durations) * SAME_LENGTH_TOLERANCE


def add_files(project, user, audios, stems):
    """Put a person's files in their own work: included right away; in sync only if they're stems."""
    now = timezone.now()
    durations = [a.get_duration() for a in audios]
    project.first_version()
    added = []
    for audio in audios:
        alignment = (guess_alignment(project, audio, durations) if stems else Contribution.SEPARATE)
        contribution, created = Contribution.objects.get_or_create(project=project, audio=audio, defaults={
            "contributor": user, "status": Contribution.INCLUDED, "offset_ms": 0,
            "alignment": alignment, "terms_accepted_at": now, "source_filename": audio.name})
        project.audios.add(audio)
        if created:
            added.append(contribution)
    # Adding files is a new version (the first one, for a new work).
    if added:
        project.new_version(user, added)


@login_required
@require_POST
def upload_organize(request):
    """After the files are in: one work with them, or sounds on their own."""
    from .views import _declare_sources
    ctx = _context(request)
    audios = _own_audios(request.user, _ids(request.POST.get("ids")))
    if not audios:
        raise Http404
    together = request.POST.get("together") == "1"
    stems = request.POST.get("stems") == "1"
    with transaction.atomic():
        if together:
            project = None
            if request.POST.get("project"):
                project = get_object_or_404(Project, slug=request.POST["project"], user=request.user)
            if project is None:
                name = (request.POST.get("name") or "").strip()[:100] or audios[0].name
                project = Project.objects.create(name=name, user=request.user, status="in_progress",
                                                 visibility=VISIBILITY_PRIVATE, version_of=ctx["source"])
                _declare_sources(request.user, project, ctx["source"], [ctx["sound"]] if ctx["sound"] else [])
            add_files(project, request.user, audios, stems)
            if ctx["group"] is not None:
                project.shared_groups.add(ctx["group"])
            project.refresh_preview()
            project.reindex_search()
            nxt = "%s?proyecto=%s" % (reverse("upload-complete"), project.slug)
        else:
            for audio in audios:
                if ctx["sound"] is not None and audio.source_audio_id is None:
                    audio.source_audio = ctx["sound"]
                    audio.save(update_fields=["source_audio"])
                if ctx["group"] is not None:
                    audio.shared_groups.add(ctx["group"])
            nxt = "%s?ids=%s" % (reverse("upload-complete"), ",".join(str(a.pk) for a in audios))
    return JsonResponse({"next": nxt, "project": project.slug if together else None})


@login_required
@require_POST
def upload_new_project(request):
    """Just a name, to go on later: a work made from a sound (or based on another) with no file yet."""
    from .views import _declare_sources
    ctx = _context(request)
    name = (request.POST.get("name") or "").strip()[:100]
    if not name:
        messages.error(request, _("Give the project a name."))
        return redirect(request.META.get("HTTP_REFERER") or reverse("create"))
    with transaction.atomic():
        project = Project.objects.create(name=name, user=request.user, status="idea",
                                         visibility=VISIBILITY_PRIVATE, version_of=ctx["source"])
        _declare_sources(request.user, project, ctx["source"], [ctx["sound"]] if ctx["sound"] else [])
        if ctx["group"] is not None:
            project.shared_groups.add(ctx["group"])
    messages.success(request, _("«%s» is created. Add tracks whenever you want.") % project.name)
    return redirect(project)


@login_required
@require_POST
def upload_attachment(request, slug):
    """Session files that came in the same folder travel with the work."""
    from .models import Attachment, attachment_kind
    from django.conf import settings
    from audio.ingest import file_sha256
    from redpanal.utils.helpers import get_file_extension
    project = get_object_or_404(Project, slug=slug, user=request.user)
    f = request.FILES.get("file")
    if f is None or get_file_extension(f.name) not in ATTACHMENT_EXTENSIONS:
        return JsonResponse({"error": _("«%s» is not an audio or session file RedPanal knows.") % getattr(f, "name", "")},
                            status=400)
    if f.size > settings.RP_ATTACHMENT_MAX_MB * 1024 * 1024:
        return JsonResponse({"error": _("«%(name)s» is bigger than %(mb)d MB.") % {
            "name": f.name, "mb": settings.RP_ATTACHMENT_MAX_MB}}, status=400)
    digest = file_sha256(f)
    if not project.attachments.filter(replaced=False, sha256=digest).exists():
        Attachment.objects.create(project=project, uploaded_by=request.user, file=f, name=f.name,
                                  kind=attachment_kind(f.name), size=f.size, sha256=digest)
    return JsonResponse({"ok": True})


def _batch(request):
    """The files the next steps are about: a work's, a list of sounds, or everything still incomplete."""
    data = request.POST if request.method == "POST" else request.GET
    project = None
    if data.get("proyecto"):
        project = get_object_or_404(Project, slug=data["proyecto"], user=request.user)
        audios = [c.audio for c in project.parts().select_related("audio").filter(audio__user=request.user)]
    elif data.get("pendientes"):
        audios = list(Audio.objects.filter(user=request.user, needs_details=True).order_by("created_at")[:100])
    else:
        audios = _own_audios(request.user, _ids(data.get("ids")))
    return project, audios


def _query(project, audios):
    return "proyecto=%s" % project.slug if project else "ids=%s" % ",".join(str(a.pk) for a in audios)


def _origin_choices(user, project):
    """What a batch may come from: your works (a new version of…) and sounds you downloaded (it uses…)."""
    choices = []
    if project is not None:
        for p in Project.objects.filter(user=user).exclude(pk=project.pk).order_by("-created_at")[:10]:
            choices.append(("p:%s" % p.slug, _("A new version of «%s»") % p.name))
    since = timezone.now() - datetime.timedelta(days=60)
    for d in (Download.objects.filter(user=user, created_at__gte=since).exclude(audio__user=user)
              .select_related("audio")[:15]):
        choices.append(("a:%d" % d.audio_id, _("Uses «%s»") % d.audio.name))
    return choices


# What each type is, in a few words (the ? next to "Type").
TYPE_HELP = {
    "master": gettext_lazy("the finished version, ready to listen"),
    "mix": gettext_lazy("several tracks together, still being adjusted"),
    "track": gettext_lazy("one instrument or voice on its own"),
    "loop": gettext_lazy("a fragment made to repeat"),
    "sample": gettext_lazy("a short sound to use: a hit, a note, an effect"),
    "demo": gettext_lazy("a quick sketch of an idea"),
    "field": gettext_lazy("the sound of a place or an environment"),
    "song": gettext_lazy("a whole song"),
    "other": gettext_lazy("anything else"),
}


def instrument_value(text):
    """The instrument as typed: one of the known ones (by code or name) keeps its code, so it matches requests
    and profiles; anything else is kept as written."""
    text = (text or "").strip()[:30]
    for code, label in INSTRUMENT_CHOICES:
        if text.lower() in (code.lower(), str(label).lower()):
            return code
    return text


def parse_tags(text, limit=10):
    """Hashtags as typed: separated by commas or spaces, with or without #."""
    import re
    tags = []
    for word in re.split(r"[,\s]+", text or ""):
        word = word.strip().lstrip("#").lower()[:50]
        if word and word not in tags:
            tags.append(word)
    return tags[:limit]


@login_required
def upload_complete(request):
    """Name, type and instrument, already guessed: the person only corrects what's wrong."""
    from .views import _declare_sources
    project, audios = _batch(request)
    if request.method == "POST":
        from django import forms as dj_forms
        checker = dj_forms.ImageField(required=False)

        def picture(name):
            """An uploaded image, if it is one."""
            f = request.FILES.get(name)
            if f is None:
                return None
            try:
                return checker.clean(f)
            except ValidationError:
                messages.warning(request, _("«%s» is not an image.") % f.name)
                return None

        if project is not None:
            image = picture("project_image")
            if image is not None:
                project.image = image
                project.save(update_fields=["image"])
        for audio in audios:
            prefix = "f%d-" % audio.pk
            image = picture(prefix + "image")
            if image is not None:
                audio.image = image
            audio.name = (request.POST.get(prefix + "name") or audio.name).strip()[:100]
            kind = request.POST.get(prefix + "type")
            if kind in dict(TYPE_CHOICES):
                audio.use_type = kind
            if prefix + "instrument" in request.POST:
                audio.instrument = instrument_value(request.POST[prefix + "instrument"])
            lat, lng = request.POST.get(prefix + "lat"), request.POST.get(prefix + "lng")
            if lat and lng:
                try:
                    audio.position_lat, audio.position_long = round(float(lat), 5), round(float(lng), 5)
                except ValueError:
                    pass
            audio.needs_details = False
            audio.save()
            if prefix + "tags" in request.POST:
                audio.tags.set(parse_tags(request.POST[prefix + "tags"]))
        if project is not None and request.POST.get("project_name", "").strip():
            project.name = request.POST["project_name"].strip()[:100]
            project.save(update_fields=["name"])
        origin = request.POST.get("origin", "")
        if origin.startswith("p:") and project is not None:
            base = Project.objects.filter(user=request.user, slug=origin[2:]).exclude(pk=project.pk).first()
            if base is not None and project.version_of_id is None:
                project.version_of = base
                project.save(update_fields=["version_of"])
                _declare_sources(request.user, project, base, [])
        elif origin.startswith("a:") and origin[2:].isdigit():
            sound = Audio.objects.visible_to(request.user).filter(pk=origin[2:]).first()
            if sound is not None:
                if project is not None:
                    _declare_sources(request.user, project, None, [sound])
                else:
                    for audio in audios:
                        if audio.source_audio_id is None:
                            audio.source_audio = sound
                            audio.save(update_fields=["source_audio"])
        return redirect("%s?%s" % (reverse("upload-share"), _query(project, audios)))
    types = [(code, label) for code, label in TYPE_CHOICES if code in UPLOAD_TYPES]
    types_help = "\n".join("%s: %s" % (str(label).capitalize(), TYPE_HELP[code]) for code, label in types if code in TYPE_HELP)
    return render(request, "project/upload_complete.html", {
        "project": project, "audios": audios, "types": types, "types_help": types_help,
        "instruments": INSTRUMENT_CHOICES,
        "origins": _origin_choices(request.user, project), "query": _query(project, audios),
    })


@login_required
def upload_share(request):
    """Open to everyone, with a group, with one person — or private, which is how it already is."""
    from .views import _display_name
    from social.models import notify
    project, audios = _batch(request)
    groups = _my_groups(request.user)
    if request.method == "POST":
        how = request.POST.get("how", "private")
        target_url = project.get_absolute_url() if project else (
            audios[0].get_absolute_url() if len(audios) == 1 else reverse("my-stuff") + "#sonidos")
        if how == "public":
            if not request.POST.get("accept_license"):
                messages.error(request, _("To publish it, accept the free license."))
                return redirect("%s?%s" % (reverse("upload-share"), _query(project, audios)))
            if project is not None:
                project.set_visibility(VISIBILITY_PUBLIC)
            else:
                for audio in audios:
                    audio.publish()
            messages.success(request, _("Published: anyone can listen to it now."))
        elif how == "group":
            group = groups.filter(pk=request.POST.get("group") or 0).first()
            if group is None:
                messages.error(request, _("Choose one of your groups."))
                return redirect("%s?%s" % (reverse("upload-share"), _query(project, audios)))
            if project is not None:
                project.shared_groups.add(group)
            else:
                for audio in audios:
                    audio.shared_groups.add(group)
            messages.success(request, _("Shared with «%s».") % group.name)
        elif how == "person":
            username = request.POST.get("username", "").strip().lstrip("@")
            person = User.objects.filter(username__iexact=username, is_active=True).exclude(pk=request.user.pk).first()
            if person is None:
                messages.error(request, _("There's no one called @%s.") % username)
                return redirect("%s?%s" % (reverse("upload-share"), _query(project, audios)))
            if project is not None:
                membership, _created = Membership.objects.get_or_create(project=project, user=person)
                if membership.status != Membership.ACTIVE:
                    membership.status = Membership.ACTIVE
                    membership.decided_at = timezone.now()
                    membership.save()
                action.send(request.user, verb='member_added', action_object=membership, target=project, public=False)
            else:
                for audio in audios:
                    audio.shared_with.add(person)
                notify(person, request.user, "shared", audios[0].name if len(audios) == 1 else
                       _("%d sounds") % len(audios), target_url)
            messages.success(request, _("%s can listen to it now.") % _display_name(person))
        else:
            messages.info(request, _("It stays private: only you can listen to it. You can share it later."))
        return redirect(target_url)
    return render(request, "project/upload_share.html", {
        "project": project, "audios": audios, "groups": groups, "query": _query(project, audios),
    })
