# -*- coding: utf-8 -*-
import os
import re
import json
import string

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse, Http404
from django.utils.translation import gettext_lazy as _
from django.urls import reverse_lazy
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, UpdateView, DetailView, CreateView, DeleteView, FormView

from .models import Audio
from project.models import Project
from .forms import AudioEditForm
from redpanal.utils.views import LoginRequiredMixin, UserRequiredMixin
from django.forms import formset_factory

@login_required
def audio_create_update(request, slug=None):
    """Edit the details of a sound you uploaded (the file itself stays: a new file is a new sound)."""
    from django.core.exceptions import PermissionDenied
    from .forms import SoundEditForm
    audio = get_object_or_404(Audio, slug=slug)
    if audio.user != request.user:
        raise PermissionDenied
    if request.method == "POST":
        form = SoundEditForm(request.POST, request.FILES, instance=audio)
        if form.is_valid():
            form.save()
            return redirect("audio-detail", slug=audio.slug)
    else:
        form = SoundEditForm(instance=audio)
    return render(request, "audio/audio_form.html", {"form": form, "object": audio})

def _listenable_audio_or_404(request, **lookup):
    audio = get_object_or_404(Audio, **lookup)
    if not audio.can_listen(request.user, request):
        raise Http404
    return audio


def _can_download(request, audio):
    """A work can keep its parts from being downloaded; the person who uploaded a file always gets it."""
    if request.user == audio.user:
        return True
    works = Project.objects.filter(contributions__audio=audio).distinct()
    return all(w.can_download(request.user, request) for w in works if w.can_listen(request.user, request))


class AudioDetailView(DetailView):
    model = Audio

    def get_object(self, queryset=None):
        return _listenable_audio_or_404(self.request, slug=self.kwargs["slug"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user, audio = self.request.user, self.object
        visible = Project.objects.visible_to(user)
        context["works"] = visible.filter(Q(audios=audio) | Q(contributions__audio=audio)).distinct()
        context["used_in"] = visible.filter(sources__audio=audio).distinct()
        context["can_download"] = _can_download(self.request, audio)
        context["duration"] = audio.get_duration()
        context["file_format"] = os.path.splitext(audio.audio.name)[1].lstrip(".").upper()
        context["genealogy_below"] = [{"name": p.name, "url": p.get_absolute_url(), "who": p.user}
                                      for p in context["used_in"]]
        # "Add to a project": the person's own projects that don't credit this sound yet.
        # A track of a work is a file like any other: it can be used too, once anyone may hear it.
        if user.is_authenticated and user != audio.user:
            context["my_projects"] = (Project.objects.filter(user=user).exclude(sources__audio=audio)
                                      .order_by("-created_at")[:20])
        from social.following import reaction_state
        context["reactions"] = reaction_state(user, audio)
        # Amplify only what anyone can listen to.
        context["is_public"] = Audio.objects.visible_to(None).filter(pk=audio.pk).exists()
        return context

class  AudioDeleteView(LoginRequiredMixin, UserRequiredMixin, DeleteView):
    model = Audio
    success_url = reverse_lazy('index')


@login_required
def sound_add_to_project(request, pk):
    """Credit a loose sound in one of your projects: it shows in the project's genealogy and its author hears about it."""
    from django.contrib import messages
    from actstream import action
    from project.models import WorkSource, VISIBILITY_PUBLIC
    audio = _listenable_audio_or_404(request, pk=pk)
    if request.method != "POST":
        return redirect(audio)
    project = get_object_or_404(Project, pk=request.POST.get("project"), user=request.user)
    if not WorkSource.objects.filter(project=project, audio=audio).exists():
        WorkSource.objects.create(project=project, audio=audio)
        action.send(request.user, verb="used_as_source", action_object=project, target=audio,
                    public=project.visibility == VISIBILITY_PUBLIC)
    messages.success(request, _("«%(sound)s» is now credited in «%(project)s».") % {"sound": audio.name, "project": project.name})
    return redirect(project)


def audio_stream(request, pk):
    """Play an audio: check who is asking, then hand over the file.

    The file address has a random folder, so only people who pass this check
    learn it; the web server then serves it with seeking support.
    """
    audio = _listenable_audio_or_404(request, pk=pk)
    response = redirect(audio.audio.url)
    response["Cache-Control"] = "private, no-store"
    return response


def audio_download(request, pk):
    """Download the original file; remember it so it can be suggested as a source later."""
    from django.http import FileResponse
    from django.utils import timezone
    from .models import Download
    audio = _listenable_audio_or_404(request, pk=pk)
    if not _can_download(request, audio):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    if request.user.is_authenticated:
        Download.objects.update_or_create(user=request.user, audio=audio,
                                          defaults={"created_at": timezone.now()})
    return FileResponse(audio.audio.open("rb"), as_attachment=True,
                        filename=os.path.basename(audio.audio.name))


def audio_peaks_json(request, pk):
    audio = _listenable_audio_or_404(request, pk=pk)
    big_json_path = audio.audio.path + '.big.json'
    json_path = audio.audio.path + '.json'
    for path in (big_json_path, json_path):
        try:
            with open(path) as f:
                peaks = json.load(f)
            duration_ms = audio.get_duration()
            return JsonResponse({
                'peaks': peaks,
                'duration': duration_ms / 1000 if duration_ms else None,
            })
        except (FileNotFoundError, json.JSONDecodeError):
            continue
    return JsonResponse({'peaks': [], 'duration': 0})
