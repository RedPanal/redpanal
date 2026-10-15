import os
import tempfile
import zipfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Case, Count, Q, When
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.views.generic import ListView, UpdateView, DeleteView
from actstream import action

from audio.models import Audio
from audio.uploads import prepare_audio_file
from social.models import Message
from social.following import reaction_state
from .models import (Project, PartRequest, Contribution, Version, Membership, WorkGroup, guess_alignment,
                     VISIBILITY_PUBLIC, VISIBILITY_OPEN_CALL, VISIBILITY_PRIVATE, VISIBILITY_CHOICES)
from .forms import (ProjectForm, NewWorkForm, ContributionForm, PartRequestForm,
                    CommentForm, VersionForm, VisibilityForm, InviteForm, AccessRequestForm,
                    FolderWorkForm, SoundForm)
from redpanal.utils.views import LoginRequiredMixin, UserRequiredMixin


def _owner_or_403(request, project):
    if request.user != project.user:
        raise PermissionDenied


def _back(request, project, anchor=""):
    return redirect(project.get_absolute_url() + anchor)


def _viewable(request, slug):
    """The work if this person may see it; a missing page otherwise, so its existence isn't revealed."""
    project = get_object_or_404(Project, slug=slug)
    project.remember_link(request, request.GET.get("k"))
    if not project.can_view(request.user, request):
        raise Http404
    return project


def _listenable(request, slug):
    project = _viewable(request, slug)
    if not project.can_listen(request.user, request):
        raise Http404
    return project


def _downloadable(request, slug):
    project = _listenable(request, slug)
    if not project.can_download(request.user, request):
        raise PermissionDenied
    return project


def _display_name(user):
    profile = getattr(user, "userprofile", None)
    return (profile.realname if profile and profile.realname else user.username)


def project_detail(request, slug):
    project = _viewable(request, slug)
    user = request.user
    if not project.can_listen(user, request):
        return _open_call_detail(request, project)

    is_owner = user == project.user
    ct = ContentType.objects.get_for_model(Project)
    # Listening to another version (?v=3): its files, one click from the author's.
    visible_versions = _visible_versions(project, user)
    current = project.current_version()
    viewing = None
    if str(request.GET.get("v", "")).isdigit():
        viewing = visible_versions.filter(number=request.GET["v"]).first()
        if viewing is not None and current is not None and viewing.pk == current.pk:
            viewing = None  # that's what sounds by default
    shown = viewing.parts() if viewing is not None else project.parts()
    open_requests = list(project.open_requests().annotate(
        n_proposed=Count('contributions', filter=Q(contributions__status=Contribution.PROPOSED))))
    attachments = list(project.attachments.filter(replaced=False).select_related("uploaded_by"))
    from actstream.actions import is_following
    from audio.models import INSTRUMENT_CHOICES
    versions = project.versions_saved.all()
    sound_sources = list(project.sources.filter(audio__in=Audio.objects.visible_to(user))
                         .select_related("audio", "audio__user"))
    derivatives = list(Project.objects.visible_to(user).filter(version_of=project).select_related("user"))
    genealogy_above = [{"name": s.audio.name, "url": s.audio.get_absolute_url(), "who": s.audio.user}
                       for s in sound_sources]
    if project.version_of_id and Project.objects.visible_to(user).filter(pk=project.version_of_id).exists():
        genealogy_above.insert(0, {"name": project.version_of.name, "url": project.version_of.get_absolute_url(),
                                   "who": project.version_of.user})

    return render(request, "project/project_detail.html", {
        "genealogy_above": genealogy_above,
        "genealogy_below": [{"name": d.name, "url": d.get_absolute_url(), "who": d.user} for d in derivatives],
        "object": project,
        "is_owner": is_owner,
        "is_member": project.is_member(user),
        # Every file of the work (or of the version listened to), aligned or not: each one plays on its own.
        "layer_groups": _layer_groups([c for c in shown.select_related("audio", "contributor")
                                       if not c.audio.moderation_hidden or user == c.audio.user],
                                      open_requests if viewing is None else []),
        "viewing": viewing, "current_version": current,
        "version_list": list(visible_versions.order_by("-number")),
        "documents": [a for a in attachments if a.name.lower().rsplit(".", 1)[-1] in DOCUMENT_EXTENSIONS],
        "follows_project": user.is_authenticated and not is_owner and is_following(user, project),
        "reactions": reaction_state(user, project),
        "is_public": project.visibility == "public" and not project.moderation_hidden,
        "latest_version": versions.first(),
        "can_contribute": project.can_contribute(user),
        "can_download": project.can_download(user, request),
        "parts": shown,
        "aligned_parts": shown.filter(alignment=Contribution.ALIGNED, audio__moderation_hidden=False),
        "loose_parts": shown.exclude(alignment=Contribution.ALIGNED),
        "proposed": project.proposed(),
        "alternatives": project.alternatives(),
        "open_requests": open_requests,
        "closed_requests": project.requests.filter(is_open=False) if is_owner else [],
        "versions": visible_versions.order_by("-number"),
        "credits": project.credits(shown),
        # One level of replies, like a conversation thread.
        "comments": (Message.objects.filter(content_type=ct, object_id=project.pk, moderation_hidden=False,
                                            parent__isnull=True)
                     .select_related('user').prefetch_related('replies__user').order_by('created_at')),
        "attachments": [a for a in attachments if a.name.lower().rsplit(".", 1)[-1] not in DOCUMENT_EXTENSIONS],
        "sound_sources": project.sources.filter(audio__in=Audio.objects.visible_to(user))
                                        .select_related("audio", "audio__user"),
        "derivatives": Project.objects.visible_to(user).filter(version_of=project),
        "request_form": PartRequestForm() if is_owner else None,
        "access_requests": project.access_requests() if is_owner else None,
        "can_join_by_link": (user.is_authenticated and not project.is_member(user)
                             and project.has_link(request)),
        "more_to_listen": _more_to_listen(project, user),
    })


@login_required
def project_settings(request, slug):
    """What the author sets once and changes rarely: access, details, proof of authorship, deleting."""
    project = get_object_or_404(Project, slug=slug)
    _owner_or_403(request, project)
    user = request.user
    return render(request, "project/project_settings.html", {
        "object": project,
        "visibility_form": VisibilityForm(initial={"visibility": project.visibility,
                                                   "preview_start_s": project.preview_start_ms // 1000,
                                                   "allow_downloads": project.allow_downloads,
                                                   "preview_watermark": project.preview_watermark}),
        "members": project.memberships.filter(status=Membership.ACTIVE).select_related("user", "user__userprofile"),
        "invite_form": InviteForm(),
        "shared_groups": project.shared_groups.all(),
        "my_groups": (WorkGroup.objects.filter(Q(owner=user) | Q(members__user=user)).distinct()
                      .exclude(pk__in=project.shared_groups.values("pk"))),
        # People whose included parts predate the license agreement: ask them before publishing.
        "without_consent": sorted({c.contributor for c in project.parts()
                                   if c.contributor != project.user and not c.terms_accepted_at},
                                  key=lambda u: u.username),
        "credits": project.credits(),
        "visibility_choices": VISIBILITY_CHOICES,
        "share_url": request.build_absolute_uri(project.get_share_url()),
        # Versions other people made: the author may take one off the page (rarely).
        "others_versions": project.versions_saved.exclude(created_by=user).select_related("created_by", "parent"),
    })


def _to_settings(project):
    return redirect("project-settings", slug=project.slug)


def _more_to_listen(project, user, limit=6):
    """After a work, more paths: works and sounds that share its hashtags or instruments, then
    other works by the same person, then the newest. Mixed, so the page never ends in a dead end."""
    tags = list(project.tags.values_list("pk", flat=True))
    instruments = {c.audio.instrument for c in project.parts().select_related("audio") if c.audio.instrument}
    instruments |= set(project.requests.filter(is_open=True).values_list("instrument", flat=True))
    listed = Project.objects.listed().exclude(pk=project.pk).select_related("user")
    related = Q(pk__in=[])
    if tags:
        related |= Q(tags__in=tags)
    if instruments:
        related |= Q(requests__instrument__in=instruments, requests__is_open=True)
    works = list(listed.filter(related).distinct().order_by("-created_at")[:limit])
    for extra in (listed.filter(user=project.user), listed):
        if len(works) >= limit:
            break
        works += list(extra.exclude(pk__in=[w.pk for w in works]).order_by("-created_at")[:limit - len(works)])
    sound_q = Q(pk__in=[])
    if tags:
        sound_q |= Q(tags__in=tags)
    if instruments:
        sound_q |= Q(instrument__in=instruments)
    loose = Audio.objects.visible_to(user).filter(contributions__isnull=True).select_related("user")
    sounds = list(loose.filter(sound_q).distinct().order_by("-created_at")[:limit])
    if len(sounds) < limit:
        sounds += list(loose.exclude(pk__in=[s.pk for s in sounds]).order_by("-created_at")[:limit - len(sounds)])
    mixed = []
    for i in range(limit):
        for kind, items in (("obra", works), ("sonido", sounds)):
            if i < len(items):
                mixed.append({"kind": kind, "obj": items[i]})
    return mixed[:limit]


DOCUMENT_EXTENSIONS = ("pdf", "txt", "md")  # lyrics, chords, notes: for anyone listening, not only for producing


def _layer_groups(parts, open_requests):
    """Layers grouped by instrument, with the open collaborations as empty slots in their group."""
    from audio.models import INSTRUMENT_CHOICES
    labels = dict(INSTRUMENT_CHOICES)
    groups, index = [], {}

    def group(code, label=None):
        if code not in index:
            index[code] = {"label": label if label is not None else labels.get(code, ""), "layers": [], "wanted": []}
            groups.append(index[code])
        return index[code]
    from audio.models import REFERENCE_TYPES
    # The reference (a master or a mix) comes first, most at hand; then the files by instrument.
    for c in parts:
        if c.audio.use_type in REFERENCE_TYPES:
            group("ref:" + c.audio.use_type, c.audio.get_use_type_display()).get("layers").append(c)
    for c in parts:
        if c.audio.use_type not in REFERENCE_TYPES:
            group(c.audio.instrument or "").get("layers").append(c)
    for r in open_requests:
        group(r.instrument).get("wanted").append(r)
    return groups


def _open_call_detail(request, project):
    """What someone outside the work sees of an open call: what it needs and a preview."""
    membership = project.membership_of(request.user)
    return render(request, "project/project_open_call.html", {
        "object": project,
        "open_requests": project.open_requests(),
        "membership": membership,
        "form": AccessRequestForm(),
    })


@login_required
def work_create(request):
    """Crear: the upload (project/upload.py) — Subir or Grabar, details later.

    A plain form post still creates a work from one file: the way in without JavaScript.
    """
    if request.method != "POST":
        from .upload import upload_start
        return upload_start(request)
    source = None
    if request.GET.get("from"):
        source = _listenable(request, request.GET["from"])
    # A work created for a class: private and shared with the group from the start.
    group = None
    group_id = request.POST.get("grupo") or request.GET.get("grupo")
    if group_id and str(group_id).isdigit():
        group = WorkGroup.objects.filter(pk=group_id, owner=request.user).first()
    # "Use it in a new work" from a loose sound: it comes checked as a source.
    sound = None
    if str(request.GET.get("sonido", "")).isdigit():
        sound = (Audio.objects.visible_to(request.user).filter(pk=request.GET["sonido"], contributions__isnull=True)
                 .exclude(user=request.user).first())

    if request.method == "POST":
        form = NewWorkForm(request.POST, request.FILES, user=request.user, sound=sound)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                audio_file = prepare_audio_file(data["audio"], data.get("trim_start_ms"),
                                                data.get("trim_end_ms"))
                audio = Audio(user=request.user, audio=audio_file,
                              name=data["name"], instrument=data.get("part_instrument") or "",
                              tempo=data.get("tempo"))
                audio._part_of_work = True
                audio.save()
                project = Project(name=data["name"], user=request.user, visibility=data["visibility"],
                                  tempo=data.get("tempo"), version_of=data.get("source"),
                                  image=data.get("image"))
                project.save()
                Contribution.objects.create(project=project, audio=audio,
                                            contributor=request.user,
                                            status=Contribution.INCLUDED,
                                            alignment=Contribution.ALIGNED,  # it sets the timeline
                                            terms_accepted_at=timezone.now())
                project.audios.add(audio)
                for instrument in data["missing"]:
                    PartRequest.objects.create(project=project, instrument=instrument,
                                               description=data["missing_text"])
                _declare_sources(request.user, project, data.get("source"), data.get("sources") or [])
                if group is not None:
                    project.shared_groups.add(group)
            project.refresh_preview()
            project.reindex_search()
            messages.success(request, _("Your work is published."))
            return redirect(project)
    else:
        form = NewWorkForm(user=request.user, sound=sound, initial={
            "visibility": VISIBILITY_PRIVATE if group else VISIBILITY_OPEN_CALL,
            "source": source,
            "name": _("Idea from %s") % _date_label(),
        })
    # "Based on another work": the person's own works first, then recent public ones.
    bases = []
    if source is None and group is None and sound is None:
        mine = list(Project.objects.filter(user=request.user).order_by("-created_at")[:4])
        others = list(Project.objects.listenable_by(request.user).filter(visibility=VISIBILITY_PUBLIC)
                      .exclude(user=request.user).order_by("-created_at")[:4])
        bases = mine + others
    return render(request, "project/work_create.html", {
        "form": form, "source": source, "visibility_choices": VISIBILITY_CHOICES, "group": group,
        "bases": bases, "sound": sound,
    })


@login_required
def work_create_folder(request):
    """A new work from a studio folder: every stem becomes a part, sessions travel as attachments."""
    from .stems import add_stems, classify, usage_bytes, quota_bytes
    from .models import ATTACHMENT_EXTENSIONS
    from audio.uploads import ACCEPTED_EXTENSIONS
    result = None
    if request.method == "POST":
        form = FolderWorkForm(request.POST, request.FILES)
        files = request.FILES.getlist("stems")
        audio_files = classify(files)[0]
        if not audio_files:
            form.add_error(None, _("Choose a folder or files with at least one audio file."))
        if form.is_valid():
            data = form.cleaned_data
            project = Project.objects.create(name=data["name"], user=request.user,
                                             visibility=data["visibility"], tempo=data.get("tempo"),
                                             image=data.get("image"))
            for instrument in data["missing"]:
                PartRequest.objects.create(project=project, instrument=instrument,
                                           description=data["missing_text"])
            result = add_stems(project, request.user, files, instruments=request.POST.getlist("instruments"))
            if result.added:
                for error in result.errors:
                    messages.warning(request, error)
                messages.success(request, _("Your work is published with %(n)d parts.") % {"n": len(result.added)})
                return redirect(project)
            project.delete()  # nothing usable arrived: don't leave an empty work behind
    else:
        form = FolderWorkForm(initial={"visibility": VISIBILITY_OPEN_CALL,
                                       "name": _("Work from %s") % _date_label()})
    from audio.models import INSTRUMENT_CHOICES
    return render(request, "project/work_create_folder.html", {
        "form": form, "result": result, "visibility_choices": VISIBILITY_CHOICES,
        "instrument_choices": INSTRUMENT_CHOICES,
        "audio_extensions": ACCEPTED_EXTENSIONS, "attachment_extensions": ATTACHMENT_EXTENSIONS,
        "usage_mb": usage_bytes(request.user) // (1024 * 1024),
        "quota_mb": quota_bytes() // (1024 * 1024),
    })


@login_required
def sound_create(request):
    """Share a loose sound (loop, sample, field recording) for anyone to use in their works."""
    if request.method == "POST":
        form = SoundForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            audio = Audio(user=request.user, audio=prepare_audio_file(data["audio"]), name=data["name"],
                          use_type=data["use_type"], instrument=data["instrument"], tempo=data.get("tempo"),
                          musical_key=data["musical_key"], description=data["description"],
                          image=data.get("image"))
            audio.save()
            messages.success(request, _("Your sound is shared."))
            return redirect(audio)
    else:
        form = SoundForm(initial={"use_type": "loop"})
    return render(request, "project/sound_create.html", {"form": form})


def _declare_sources(user, project, source_project, audios):
    """Credit what a new work is made from, and let the authors know."""
    from .models import WorkSource
    public = project.visibility == VISIBILITY_PUBLIC
    if source_project is not None:
        WorkSource.objects.create(project=project, source_project=source_project)
        if source_project.user != user:
            action.send(user, verb='used_as_source', action_object=project, target=source_project, public=public)
    for audio in audios:
        WorkSource.objects.create(project=project, audio=audio)
        if audio.user != user:
            action.send(user, verb='used_as_source', action_object=project, target=audio, public=public)


def _date_label():
    from django.utils import formats
    return formats.date_format(timezone.localdate())


class ProjectUpdateView(LoginRequiredMixin, UserRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm


class ProjectDeleteView(LoginRequiredMixin, UserRequiredMixin, DeleteView):
    model = Project
    success_url = reverse_lazy('index')


class ProjectListView(ListView):
    model = Project

    def get_queryset(self):
        return Project.objects.listed()


@login_required
def contribute(request, slug):
    """Propose a part for a work (flow 4). The owner adds parts directly."""
    project = _viewable(request, slug)
    if not project.can_contribute(request.user):
        messages.info(request, _("Ask to join this work to listen to it whole and contribute."))
        return redirect(project)
    is_owner = request.user == project.user
    initial_request = None
    if request.GET.get("pedido"):
        initial_request = project.open_requests().filter(pk=request.GET["pedido"]).first()
    profile = getattr(request.user, "userprofile", None)
    played = (profile.instruments if profile else []) or []
    if initial_request is None and not is_owner and played:
        # A request this person can cover, so they don't have to pick it.
        initial_request = project.open_requests().filter(instrument__in=played).first()
    initial_instrument = (initial_request.instrument if initial_request
                          else (played[0] if played else None))

    # The version this new file builds on: the one being listened to, or what sounds today.
    parent = None
    version_number = request.POST.get("version") or request.GET.get("v")
    if str(version_number or "").isdigit():
        parent = _visible_versions(project, request.user).filter(number=version_number).first()

    if request.method == "POST":
        form = ContributionForm(request.POST, request.FILES, project=project, is_owner=is_owner)
        if form.is_valid():
            data = form.cleaned_data
            # What it is: the collaboration answered, else what the person plays, else the file name.
            from .stems import guess_instrument
            instrument = (data.get("instrument") or (data["request"].instrument if data.get("request") else "")
                          or guess_instrument(data["audio"].name))
            if instrument == "other" and played:
                instrument = played[0]
            labels = dict(form.fields["instrument"].choices)
            from audio.ingest import clean_name
            what = labels.get(instrument) or clean_name(data["audio"].name)
            with transaction.atomic():
                project.first_version()
                audio = Audio(user=request.user, audio=prepare_audio_file(data["audio"]),
                              name="%s · %s" % (project.name, what), instrument=instrument if instrument != "other" else "",
                              tempo=project.tempo, license=project.license)
                audio._part_of_work = True
                audio.save()
                # Lined up while listening to the work (or recorded over it): aligned for sure.
                aligned_by_ear = request.POST.get("aligned_by_ear") == "1"
                contribution = Contribution.objects.create(
                    project=project, audio=audio, contributor=request.user,
                    request=data.get("request"), note=data["note"], offset_ms=data.get("offset_ms") or 0,
                    # Someone else's file goes into the version they make: nobody has to approve it.
                    status=Contribution.INCLUDED if is_owner else Contribution.VERSIONED,
                    alignment=Contribution.ALIGNED if aligned_by_ear else guess_alignment(project, audio),
                    terms_accepted_at=timezone.now())
                if is_owner:
                    project.audios.add(audio)
                version = project.new_version(request.user, [contribution], parent=None if is_owner else parent,
                                              message=data["note"])
            project.reindex_search()
            public = project.visibility == VISIBILITY_PUBLIC
            if is_owner:
                project.refresh_preview()
                action.send(request.user, verb='version_saved', action_object=version, target=project, public=public)
                messages.success(request, _("Added to your work: version %d.") % version.number)
                return redirect(project)
            action.send(request.user, verb='contributed', action_object=contribution, target=project, public=public)
            messages.success(request, _("Your version %(n)d of «%(work)s» is ready. %(who)s will be notified.") % {
                "n": version.number, "work": project.name, "who": _display_name(project.user)})
            return redirect("%s?v=%d" % (project.get_absolute_url(), version.number))
    else:
        form = ContributionForm(project=project, is_owner=is_owner, initial={
            "request": initial_request,
            "instrument": initial_instrument,
            "offset_ms": 0,
        })
    return render(request, "project/contribute.html", {
        "object": project, "form": form, "parts": parent.parts() if parent else project.parts(),
        "initial_request": initial_request, "is_owner": is_owner, "parent": parent,
        "can_download": project.can_download(request.user, request),
    })


def _visible_versions(project, user):
    """Versions on the work's page: the ones its author hid stay for the author and whoever made them."""
    versions = project.versions_saved.select_related("created_by", "parent")
    if user == project.user:
        return versions
    if user is not None and user.is_authenticated:
        return versions.filter(Q(hidden=False) | Q(created_by=user))
    return versions.filter(hidden=False)


@login_required
@require_POST
def contribution_status(request, slug, pk):
    """Include, keep as alternative, undo or withdraw a contribution (flow 2)."""
    project = get_object_or_404(Project, slug=slug)
    contribution = get_object_or_404(Contribution, pk=pk, project=project)
    status = request.POST.get("status")

    if status == Contribution.WITHDRAWN:
        if request.user != contribution.contributor:
            raise PermissionDenied
    elif status in (Contribution.INCLUDED, Contribution.ALTERNATIVE, Contribution.PROPOSED):
        _owner_or_403(request, project)
    else:
        raise Http404

    if status == Contribution.INCLUDED:
        project.first_version()
    contribution.set_status(status)
    if status in (Contribution.INCLUDED, Contribution.ALTERNATIVE):
        from social.models import notify
        notify(contribution.contributor, request.user, status, project.name, project.get_absolute_url())

    if status == Contribution.INCLUDED:
        if contribution.request_id and request.POST.get("close_request"):
            PartRequest.objects.filter(pk=contribution.request_id).update(is_open=False)
        # Adding a file to what sounds is a new version, on its own ("included" already told its author).
        project.new_version(request.user, [contribution])
        return redirect(project)
    if status == Contribution.ALTERNATIVE:
        messages.info(request, _("Saved as an alternative. You can bring it back at any time."))
    elif status == Contribution.WITHDRAWN:
        messages.info(request, _("You withdrew your contribution."))
    return _back(request, project, "#aportes")


@login_required
def contribution_align(request, slug, pk):
    """Line a part up with the rest by ear (with a suggested offset), or mark it as independent."""
    project = _listenable(request, slug)
    contribution = get_object_or_404(Contribution, pk=pk, project=project)
    if request.user not in (project.user, contribution.contributor):
        raise PermissionDenied
    if request.method == "POST":
        decision = request.POST.get("decision")
        if decision == "separate":
            contribution.alignment = Contribution.SEPARATE
            messages.info(request, _("It will play on its own, outside the work's player."))
        elif decision == "aligned":
            try:
                contribution.offset_ms = max(-600000, min(600000, int(request.POST.get("offset_ms", "0"))))
            except ValueError:
                contribution.offset_ms = 0
            contribution.alignment = Contribution.ALIGNED
            messages.success(request, _("Aligned: it now plays together with the rest."))
        else:
            raise Http404
        contribution.save(update_fields=["alignment", "offset_ms"])
        project.refresh_preview()
        return redirect(project.get_absolute_url() + "#partes")
    references = project.aligned_parts().exclude(pk=contribution.pk)
    return render(request, "project/align.html", {
        "object": project, "c": contribution, "references": references,
    })


@login_required
@require_POST
def version_create(request, slug):
    project = get_object_or_404(Project, slug=slug)
    _owner_or_403(request, project)
    form = VersionForm(request.POST)
    message = form.cleaned_data["message"] if form.is_valid() else ""
    version = project.save_version(request.user, message)
    action.send(request.user, verb='version_saved', action_object=version, target=project,
                public=project.visibility == VISIBILITY_PUBLIC)

    if message:
        others = [c["user"] for c in version.credits() if c["user"] != request.user]
        mentions = " ".join("@%s" % u.username for u in others)
        Message.objects.create(msg=("%s %s" % (mentions, message)).strip(), user=request.user,
                               content_type=ContentType.objects.get_for_model(Project),
                               object_id=project.pk)
    messages.success(request, _("Version %d saved.") % version.number)
    return redirect(version)


def version_detail(request, slug, number):
    project = _listenable(request, slug)
    version = get_object_or_404(Version, project=project, number=number)
    parts = version.parts()
    versions = project.versions_saved.all()
    return render(request, "project/version_detail.html", {
        "object": project, "version": version,
        "is_owner": request.user == project.user,
        "can_download": project.can_download(request.user, request),
        "is_current": _version_is_current(version),
        "previous": versions.filter(number__lt=version.number).order_by("-number").first(),
        "next": versions.filter(number__gt=version.number).order_by("number").first(),
        "parts": parts.filter(alignment=Contribution.ALIGNED, audio__moderation_hidden=False),
        "loose_parts": parts.exclude(alignment=Contribution.ALIGNED).filter(audio__moderation_hidden=False),
        "credits": version.credits(),
    })


def _version_is_current(version):
    """The work sounds today exactly as this version: same included parts."""
    return (set(version.contributions.values_list("pk", flat=True))
            == set(version.project.parts().values_list("pk", flat=True)))


@login_required
@require_POST
def version_restore(request, slug, number):
    """Go back to a version: its parts are included again, the rest stay as alternatives (nothing is lost)."""
    project = get_object_or_404(Project, slug=slug)
    _owner_or_403(request, project)
    version = get_object_or_404(Version, project=project, number=number)
    wanted = set(version.contributions.values_list("pk", flat=True))
    withdrawn = []
    with transaction.atomic():
        for c in project.parts().exclude(pk__in=wanted):
            c.set_status(Contribution.ALTERNATIVE)
        for c in version.contributions.exclude(status=Contribution.INCLUDED):
            if c.status == Contribution.WITHDRAWN:
                withdrawn.append(c)  # its author took it back: respect that
                continue
            c.set_status(Contribution.INCLUDED)
    project.refresh_preview()
    if version.created_by != request.user:
        # Adopting someone's version: it's what the work sounds like now. They hear about it.
        from social.models import notify
        notify(version.created_by, request.user, "included", project.name, project.get_absolute_url())
        messages.success(request, _("You adopted v%(n)d: it's what the work sounds like now. Nothing was lost: "
                                    "the files that were not in it stay as alternatives.") % {"n": version.number})
    else:
        messages.success(request, _("The work sounds like v%(n)d again. The parts that were not in it stay as "
                                    "alternatives.") % {"n": version.number})
    if withdrawn:
        messages.warning(request, _("Some parts were withdrawn by their authors and were not brought back."))
    return redirect(project)


@login_required
@require_POST
def version_hide(request, slug, number):
    """Take someone's version off the work's page, or bring it back. It stays for whoever made it."""
    project = get_object_or_404(Project, slug=slug)
    _owner_or_403(request, project)
    version = get_object_or_404(Version, project=project, number=number)
    version.hidden = not version.hidden
    version.save(update_fields=["hidden"])
    return redirect("%s#versiones" % reverse("project-settings", args=[project.slug]))


def version_mix(request, slug, number):
    """Download how a version sounds, as one MP3: built once and kept."""
    import hashlib
    import os
    from django.conf import settings
    from .preview import mix_parts
    project = _downloadable(request, slug)
    version = get_object_or_404(Version, project=project, number=number)
    parts = list(version.parts().filter(alignment=Contribution.ALIGNED, audio__moderation_hidden=False))
    if not parts:
        raise Http404
    # Unguessable name: media files are served without asking who you are.
    key = hashlib.sha256((settings.SECRET_KEY + repr([(p.audio_id, p.offset_ms) for p in parts])).encode()).hexdigest()[:32]
    folder = os.path.join(settings.MEDIA_ROOT, "mixes", str(project.pk))
    path = os.path.join(folder, "v%d-%s.mp3" % (version.number, key))
    if not os.path.exists(path):
        mix, _origin = mix_parts(parts)
        if mix is None:
            raise Http404
        os.makedirs(folder, exist_ok=True)
        mix.export(path, format="mp3", bitrate="192k")
    from django.utils.text import slugify
    return FileResponse(open(path, "rb"), as_attachment=True,
                        filename="%s-v%d.mp3" % (slugify(project.name) or "obra", version.number))


@login_required
@require_POST
def request_create(request, slug):
    project = get_object_or_404(Project, slug=slug)
    _owner_or_403(request, project)
    form = PartRequestForm(request.POST)
    if form.is_valid():
        form.instance.project = project
        form.save()
    return _back(request, project, "#pedidos")


@login_required
@require_POST
def request_toggle(request, slug, pk):
    project = get_object_or_404(Project, slug=slug)
    _owner_or_403(request, project)
    part_request = get_object_or_404(PartRequest, pk=pk, project=project)
    part_request.is_open = not part_request.is_open
    part_request.save(update_fields=["is_open"])
    return _back(request, project, "#pedidos")


@login_required
@require_POST
def comment_create(request, slug):
    project = _viewable(request, slug)
    if not project.can_contribute(request.user):
        raise PermissionDenied
    form = CommentForm(request.POST)
    if form.is_valid():
        ct = ContentType.objects.get_for_model(Project)
        # A reply hangs from a top-level comment of this same project (one level only).
        parent = None
        if str(request.POST.get("parent", "")).isdigit():
            parent = Message.objects.filter(pk=request.POST["parent"], content_type=ct, object_id=project.pk,
                                            parent__isnull=True).first()
        Message.objects.create(msg=form.cleaned_data["msg"], user=request.user, content_type=ct,
                               object_id=project.pk, at_ms=None if parent else form.cleaned_data.get("at_ms"),
                               parent=parent)
    return _back(request, project, "#conversacion")


@login_required
@require_POST
def project_follow(request, slug):
    """Follow a project: its new versions and layers show up in Comunidad."""
    from actstream import actions
    project = _listenable(request, slug)
    if actions.is_following(request.user, project):
        actions.unfollow(request.user, project)
    else:
        actions.follow(request.user, project, send_action=False, actor_only=False)
    return _back(request, project, "")


def credits_export(request, slug):
    """The credits as plain text, to paste in a release, a video or a program."""
    from django.http import HttpResponse
    from .templatetags.obra_tags import display_name
    project = _listenable(request, slug)
    lines = ["%s" % project.name, ""]
    for credit in project.credits():
        lines.append("%s — %s" % (display_name(credit["user"]), ", ".join(str(r) for r in credit["roles"])))
    license = project.get_license()
    lines += ["", "%s (%s)" % (license.plain, license.name), request.build_absolute_uri(project.get_absolute_url())]
    response = HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="%s-creditos.txt"' % (slugify(project.name) or "proyecto")
    return response


def parts_zip(request, slug):
    """Download the included parts, all starting at 0:00, to work on them in a DAW."""
    project = _downloadable(request, slug)
    tmp = tempfile.TemporaryFile()
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as zf:
        for i, part in enumerate(project.parts(), start=1):
            path = part.audio.audio.path
            if not os.path.exists(path):
                continue
            ext = os.path.splitext(path)[1]
            label = slugify("%s %s" % (part.audio.get_instrument_display() or part.audio.name,
                                       part.contributor.username))
            zf.write(path, "%02d-%s%s" % (i, label, ext))
    tmp.seek(0)
    return FileResponse(tmp, as_attachment=True, filename="%s-partes.zip" % project.slug)


def certificate(request, slug):
    """Proof of prior existence: when each part was uploaded and its fingerprint."""
    project = get_object_or_404(Project, slug=slug)
    if not project.is_member(request.user):
        raise Http404
    rows = [(c, c.audio.get_sha256()) for c in
            project.contributions.exclude(status=Contribution.WITHDRAWN)
            .select_related("audio", "contributor").order_by("created_at")]
    return render(request, "project/certificate.html", {
        "object": project, "rows": rows, "now": timezone.now(),
    })


# -- home studio: folders of stems and session files --------------------------

@login_required
def stems_upload(request, slug):
    """Add a studio folder at once: stems become aligned parts, sessions become attachments."""
    from .stems import add_stems, guess_instrument, usage_bytes, quota_bytes
    from .models import ATTACHMENT_EXTENSIONS
    from audio.uploads import ACCEPTED_EXTENSIONS
    project = _viewable(request, slug)
    if not project.can_contribute(request.user):
        messages.info(request, _("Ask to join this work to listen to it whole and contribute."))
        return redirect(project)
    is_owner = request.user == project.user
    result = None
    if request.method == "POST":
        files = request.FILES.getlist("stems")
        if not files:
            messages.error(request, _("Choose at least one file."))
        else:
            result = add_stems(project, request.user, files,
                               instruments=request.POST.getlist("instruments"),
                               note=request.POST.get("note", "")[:500],
                               accept_terms=bool(request.POST.get("accept_terms")))
    from audio.models import INSTRUMENT_CHOICES
    return render(request, "project/stems_upload.html", {
        "object": project, "is_owner": is_owner, "result": result,
        "instrument_choices": INSTRUMENT_CHOICES,
        "audio_extensions": ACCEPTED_EXTENSIONS, "attachment_extensions": ATTACHMENT_EXTENSIONS,
        "usage_mb": usage_bytes(request.user) // (1024 * 1024),
        "quota_mb": quota_bytes() // (1024 * 1024),
        "versions_count": project.versions_saved.count(),
    })


def attachment_download(request, slug, pk):
    from .models import Attachment
    project = _downloadable(request, slug)
    attachment = get_object_or_404(Attachment, pk=pk, project=project)
    return FileResponse(attachment.file.open("rb"), as_attachment=True, filename=attachment.name)


# -- access: visibility, invitations, requests -------------------------------

@login_required
@require_POST
def visibility_update(request, slug):
    project = get_object_or_404(Project, slug=slug)
    _owner_or_403(request, project)
    form = VisibilityForm(request.POST, already_public=project.visibility == VISIBILITY_PUBLIC)
    if not form.is_valid():
        messages.error(request, _("To make the work public, confirm that you understand what it implies."))
        return _to_settings(project)
    visibility = form.cleaned_data["visibility"]
    start = form.cleaned_data.get("preview_start_s")
    if start is not None:
        project.preview_start_ms = start * 1000
    project.allow_downloads = form.cleaned_data["allow_downloads"]
    project.preview_watermark = form.cleaned_data["preview_watermark"]
    project.save(update_fields=["preview_start_ms", "allow_downloads", "preview_watermark"])
    project.set_visibility(visibility)
    messages.success(request, _("Saved: %s.") % dict(VISIBILITY_CHOICES)[visibility])
    return _to_settings(project)


@login_required
@require_POST
def member_invite(request, slug):
    project = get_object_or_404(Project, slug=slug)
    _owner_or_403(request, project)
    form = InviteForm(request.POST)
    if form.is_valid():
        user = form.cleaned_data["username"]
        membership, created = Membership.objects.get_or_create(project=project, user=user)
        if membership.status != Membership.ACTIVE:
            membership.status = Membership.ACTIVE
            membership.decided_at = timezone.now()
            membership.save()
        action.send(request.user, verb='member_added', action_object=membership, target=project, public=False)
        messages.success(request, _("%s can now listen and contribute.") % _display_name(user))
    else:
        messages.error(request, " ".join(form.errors.get("username", [])))
    return _to_settings(project)


@login_required
@require_POST
def member_decide(request, slug, pk):
    """Accept or decline someone who asked to join, or remove a member."""
    project = get_object_or_404(Project, slug=slug)
    _owner_or_403(request, project)
    membership = get_object_or_404(Membership, pk=pk, project=project)
    if request.POST.get("decision") == "accept":
        membership.status = Membership.ACTIVE
        membership.decided_at = timezone.now()
        membership.save()
        action.send(request.user, verb='member_added', action_object=membership, target=project, public=False)
    else:
        membership.delete()
    # Removing someone happens in the settings; answering a request, on the work page.
    if request.POST.get("decision") == "remove":
        return _to_settings(project)
    return _back(request, project)


@login_required
@require_POST
def access_request(request, slug):
    """Someone outside an open call asks to join."""
    project = _viewable(request, slug)
    if project.is_member(request.user):
        return redirect(project)
    form = AccessRequestForm(request.POST)
    message = form.cleaned_data["message"] if form.is_valid() else ""
    membership, created = Membership.objects.get_or_create(
        project=project, user=request.user,
        defaults={"status": Membership.REQUESTED, "message": message})
    if created:
        action.send(request.user, verb='access_requested', action_object=membership, target=project, public=False)
    messages.success(request, _("Request sent. %s will decide.") % _display_name(project.user))
    return redirect(project)


@login_required
@require_POST
def join_by_link(request, slug):
    """Whoever opened the secret link can join, to contribute and find the work again."""
    project = _viewable(request, slug)
    if not project.has_link(request):
        raise PermissionDenied
    Membership.objects.update_or_create(project=project, user=request.user,
                                        defaults={"status": Membership.ACTIVE, "decided_at": timezone.now()})
    messages.success(request, _("You joined «%s».") % project.name)
    return redirect(project)


EXPLORE_SECTIONS = ("pedidos", "obras", "comentarios", "sonidos", "personas")
MIX_SIZE = 24  # items in the "Everything" feed; "See more" adds as many again


def explore(request):
    """Collaborations, projects, comments, sounds and people: all at once, each with "see more".

    One search box for everything; instrument, tags, tempo and the rest live in the advanced search.
    """
    from audio.models import TYPE_CHOICES, GENRE_CHOICES
    from social.models import Message, visible_messages
    from social.following import following_ids
    params = request.GET
    q = params.get("q", "").strip()[:100]
    f = _explore_filters(params)
    listed = Project.objects.listed()
    tab = params.get("ver", "")
    if tab not in EXPLORE_SECTIONS:
        tab = ""

    requests_qs = (PartRequest.objects.filter(PartRequest.open_q(), project__in=listed)
                   .select_related("project", "project__user").order_by("-created_at"))
    works = listed.select_related("user").order_by("-created_at")
    ct_project = ContentType.objects.get_for_model(Project)
    ct_audio = ContentType.objects.get_for_model(Audio)
    comments = (visible_messages(Message.objects.filter(content_type__in=[ct_project, ct_audio]), request.user)
                .filter(Q(content_type=ct_audio) | Q(object_id__in=listed.values("pk")))
                .select_related("user").order_by("-created_at"))
    if q:
        requests_qs = requests_qs.filter(Q(project__name__icontains=q) | Q(description__icontains=q)
                                         | Q(project__description__icontains=q))
        works = works.filter(Q(name__icontains=q) | Q(description__icontains=q) | Q(tags__name__icontains=q)
                             | Q(user__username__icontains=q) | Q(user__userprofile__realname__icontains=q)).distinct()
        comments = comments.filter(Q(msg__icontains=q) | Q(user__username__icontains=q))
    if f["instrument"]:
        requests_qs = requests_qs.filter(instrument=f["instrument"])
        works = works.filter(Q(requests__instrument=f["instrument"], requests__is_open=True)
                             | Q(contributions__audio__instrument=f["instrument"],
                                 contributions__status=Contribution.INCLUDED)).distinct()
    if f["tag"]:
        works = works.filter(tags__name__iexact=f["tag"]).distinct()
        requests_qs = requests_qs.filter(project__tags__name__iexact=f["tag"]).distinct()
        comments = comments.filter(tags__name__iexact=f["tag"]).distinct()
    if f["asks"]:
        works = works.filter(PartRequest.open_q("requests__")).distinct()
    sound_data = _sound_search(request, f)
    people = _people_search(q, f["instrument"], f["tag"])

    # "Everything" is one feed, newest first, with every kind mixed; "See more" makes it longer.
    try:
        shown = min(max(int(params.get("n", MIX_SIZE)), MIX_SIZE), 200)
    except ValueError:
        shown = MIX_SIZE
    size = 60 if tab else shown
    comment_list = [m for m in comments[:size * 2] if m.content_object is not None][:size]
    sections = {
        "pedidos": {"items": requests_qs[:size], "count": requests_qs.count()},
        "obras": {"items": works[:size], "count": works.count()},
        "comentarios": {"items": comment_list, "count": comments.count()},
        "sonidos": {"items": sound_data["sounds"][:size], "count": sound_data["sound_count"]},
        "personas": {"items": people[:size], "count": len(people)},
    }
    mixed, more = [], False
    if not tab:
        dated = ([("pedido", r, r.created_at) for r in sections["pedidos"]["items"]]
                 + [("obra", w, w.created_at) for w in sections["obras"]["items"]]
                 + [("comentario", m, m.created_at) for m in comment_list]
                 + [("sonido", s, s.created_at) for s in sections["sonidos"]["items"]]
                 # People are fewer and found by name: a few among the rest.
                 + [("persona", p, p.date_joined) for p in people[:max(3, shown // 8) + 1]
                    if p != request.user][:max(3, shown // 8)])
        dated.sort(key=lambda d: d[2], reverse=True)
        mixed = [{"kind": kind, "obj": obj} for kind, obj, _when in dated[:shown]]
        more = len(dated) > shown or any(s["count"] > shown for s in sections.values())
    keys = (Audio.objects.visible_to(request.user).exclude(musical_key="")
            .values_list("musical_key", flat=True).distinct().order_by("musical_key"))
    keep = params.copy()
    keep.pop("ver", None)
    keep.pop("n", None)
    return render(request, "project/explore.html", {
        "tab": tab, "q": q, "f": f, "sections": sections, "keep": keep.urlencode(),
        "mixed": mixed, "more": more, "next_n": shown + MIX_SIZE,
        "filtering": bool(q or any(v for k, v in f.items() if k not in ("my_tempo", "order"))),
        "active_filters": _active_filters(params),
        "genre_choices": GENRE_CHOICES,
        "type_choices": TYPE_CHOICES, "keys": keys,
        "instrument_choices": PartRequestForm.base_fields["instrument"].widget.choices,
        "following_ids": following_ids(request.user),
    })


def _active_filters(params):
    """The filters in use, each with the address that removes it (the × of the chips)."""
    from audio.models import TYPE_CHOICES, GENRE_CHOICES, INSTRUMENT_CHOICES
    names = {"instrumento": dict(INSTRUMENT_CHOICES), "tipo": dict(TYPE_CHOICES),
             "genero": dict(GENRE_CHOICES)}
    chips = []
    for key in ("q", "instrumento", "tag", "pide", "tipo", "genero", "bpm_min", "bpm_max", "tonalidad"):
        for value in params.getlist(key):
            if not value:
                continue
            rest = params.copy()
            rest.setlist(key, [v for v in params.getlist(key) if v != value])
            if key == "pide":
                label = _("Asking for parts")
            elif key == "bpm_min":
                label = _("from %s BPM") % value
            elif key == "bpm_max":
                label = _("up to %s BPM") % value
            elif key == "tag":
                label = "#" + value
            elif key == "q":
                label = "«%s»" % value
            else:
                label = str(names.get(key, {}).get(value, value)).capitalize()
            chips.append({"label": label, "url": "?" + rest.urlencode()})
    return chips


def _explore_filters(params):
    """The advanced search, read once: every section uses what applies to it."""
    from audio.models import TYPE_CHOICES, GENRE_CHOICES

    def number(name):
        try:
            return int(params.get(name) or 0)
        except ValueError:
            return 0
    return {
        "instrument": params.get("instrumento", ""),
        "tag": params.get("tag", "").strip().lstrip("#")[:50],
        "asks": params.get("pide") == "1",
        "types": [t for t in params.getlist("tipo") if t in dict(TYPE_CHOICES)],
        "bpm_min": number("bpm_min"), "bpm_max": number("bpm_max"),
        "key": params.get("tonalidad", "").strip(),
        "genre": params.get("genero", "") if params.get("genero", "") in dict(GENRE_CHOICES) else "",
        "order": params.get("orden", ""),
        "my_tempo": params.get("mi_tempo", ""),
    }


def _people_search(q, instrument, tag=""):
    """People who make music here: who plays what, to find someone for a part."""
    shared_sounds = Audio.objects.filter(contributions__isnull=True, moderation_hidden=False)
    users = (User.objects.filter(is_active=True, userprofile__isnull=False)
             .filter(Q(project__in=Project.objects.listed()) | Q(audio__in=shared_sounds)
                     | ~Q(userprofile__instruments=[]))
             .select_related("userprofile").distinct().order_by("-date_joined"))
    if q:
        users = users.filter(Q(username__icontains=q) | Q(userprofile__realname__icontains=q)
                             | Q(userprofile__location__icontains=q))
    if tag:
        users = users.filter(userprofile__tags__name__iexact=tag)
    people = list(users[:300])
    # Instruments are a small JSON list: filter in Python, it works the same on every database.
    if instrument:
        people = [u for u in people if instrument in (u.userprofile.instruments or [])]
    return people


def _sound_search(request, f):
    """Loose sounds (loops, samples, field recordings) with musical filters."""
    sounds = (Audio.objects.visible_to(request.user).filter(contributions__isnull=True)
              .select_related("user").order_by("-created_at"))
    if f["types"]:
        sounds = sounds.filter(use_type__in=f["types"])
    if f["instrument"]:
        sounds = sounds.filter(instrument=f["instrument"])
    if f["bpm_min"]:
        sounds = sounds.filter(tempo__gte=f["bpm_min"])
    if f["bpm_max"]:
        sounds = sounds.filter(tempo__lte=f["bpm_max"])
    if f["key"]:
        sounds = sounds.filter(musical_key__iexact=f["key"])
    if f["tag"]:
        sounds = sounds.filter(tags__name__iexact=f["tag"]).distinct()
    if f["genre"]:
        sounds = sounds.filter(genre=f["genre"])
    q = request.GET.get("q", "").strip()
    if q:
        sounds = sounds.filter(Q(name__icontains=q) | Q(tags__name__icontains=q) | Q(description__icontains=q)).distinct()
    # How many projects picked each sound up (its layers in other people's music).
    sounds = sounds.annotate(n_used=Count("used_in", distinct=True))
    if f["order"] == "retomados":
        sounds = sounds.order_by("-n_used", "-created_at")
    return {"sounds": sounds, "sound_count": sounds.count()}

@login_required
def my_stuff(request):
    """Estudio › Mine: your works, the ones shared with you, your parts in other people's works, your sounds."""
    projects = (Project.objects.filter(user=request.user)
                .annotate(n_proposed=Count('contributions', filter=Q(contributions__status=Contribution.PROPOSED)),
                          n_parts=Count('contributions', filter=Q(contributions__status=Contribution.INCLUDED)))
                .order_by("-created_at"))
    joined = (Project.objects.filter(Q(memberships__user=request.user, memberships__status=Membership.ACTIVE)
                                     | Q(shared_groups__members__user=request.user))
              .exclude(user=request.user).distinct().select_related("user"))
    # Contributions still waiting for a decision come first.
    contributions = (Contribution.objects.filter(contributor=request.user)
                     .exclude(project__user=request.user)
                     .exclude(status=Contribution.WITHDRAWN)
                     .select_related("project", "project__user", "audio")
                     .order_by(Case(When(status=Contribution.PROPOSED, then=0), default=1), "-created_at"))
    sounds = (Audio.objects.filter(user=request.user, contributions__isnull=True)
              .select_related("user").order_by("-created_at"))
    from .stems import usage_bytes, quota_bytes
    usage, quota = usage_bytes(request.user), quota_bytes()
    # The shortcuts help only when there's more than one section to jump between.
    n_sections = sum(1 for s in (projects, joined, contributions, sounds) if s.exists())
    return render(request, "project/my_stuff.html", {
        "tab": "mine", "projects": projects, "joined": joined, "contributions": contributions, "sounds": sounds,
        "show_jump": n_sections >= 2,
        # Uploaded in one go without details: a calm reminder, not a notification.
        "to_complete": Audio.objects.filter(user=request.user, needs_details=True).count(),
        "usage_mb": usage // (1024 * 1024), "quota_mb": quota // (1024 * 1024),
        "usage_pct": min(100, round(usage * 100 / quota)) if quota else 0,
    })


FAVORITE_FILTERS = ("proyectos", "sonidos", "publicaciones")


@login_required
def my_favorites(request):
    """Estudio › Favorites: what this person marked and can still see, newest first, by kind."""
    from social.models import Reaction, Message, visible_messages
    works, sounds, posts = [], [], []
    for r in Reaction.objects.filter(user=request.user, kind=Reaction.FAVORITE).select_related("content_type")[:200]:
        obj = r.content_object
        if isinstance(obj, Project):
            if Project.objects.listenable_by(request.user).filter(pk=obj.pk).exists():
                works.append(obj)
        elif isinstance(obj, Audio):
            if Audio.objects.visible_to(request.user).filter(pk=obj.pk).exists():
                sounds.append(obj)
        elif isinstance(obj, Message):
            if visible_messages(Message.objects.filter(pk=obj.pk), request.user).exists():
                posts.append(obj)
    if posts:
        amplified = set(Reaction.objects.filter(user=request.user, kind=Reaction.AMPLIFY,
                                                content_type=ContentType.objects.get_for_model(Message),
                                                object_id__in=[m.pk for m in posts])
                        .values_list("object_id", flat=True))
        for m in posts:
            m.is_amplified = m.pk in amplified
    show = request.GET.get("ver")
    if show not in FAVORITE_FILTERS:
        show = ""
    return render(request, "project/my_favorites.html", {
        "tab": "favorites", "show": show,
        "works": works if show in ("", "proyectos") else [],
        "sounds": sounds if show in ("", "sonidos") else [],
        "posts": posts if show in ("", "publicaciones") else [],
        "counts": {"proyectos": len(works), "sonidos": len(sounds), "publicaciones": len(posts)},
        "any": bool(works or sounds or posts),
    })


@login_required
def my_downloads(request):
    """Estudio › Downloads: what this person downloaded and can still hear."""
    from audio.models import Download
    downloads = (Download.objects.filter(user=request.user, audio__in=Audio.objects.visible_to(request.user))
                 .select_related("audio", "audio__user").order_by("-created_at")[:100])
    return render(request, "project/my_downloads.html", {"tab": "downloads", "downloads": downloads})


@login_required
def create_version(request, slug):
    """Older "clone project" entry point: now a new work based on this one."""
    return redirect("%s?from=%s" % (reverse_lazy("project-create"), slug))


@login_required
def download_mix(request, slug=None):
    project = _downloadable(request, slug)
    errors = None
    if request.method == "POST":
        ids = request.POST.getlist('ids')
        if len(ids) > 1:
            try:
                filename = project.mix_audios(ids)
                return redirect("/media/audio_cache/%s" % filename)
            except ValueError:
                pass  # fewer than two of them could be read: same message as choosing one
        errors = {'two_tracks': True}

    return render(request, "project/project_download_mix.html", {
        'object': project, 'errors': errors,
    })
