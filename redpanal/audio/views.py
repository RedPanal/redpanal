# -*- coding: utf-8 -*-
import os
import re
import string

from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext_lazy as _
from django.urls import reverse_lazy
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, UpdateView, DetailView, CreateView, DeleteView, FormView

from .models import Audio
from project.models import Project
from .forms import AudioEditForm, AudioUploadForm
from redpanal.utils.views import LoginRequiredMixin, UserRequiredMixin
from django.forms import formset_factory

@login_required
def audio_create_update(request, slug=None):
    ##Edit Audio
    
    instance = get_object_or_404(Audio, slug=slug) if slug else None
    title = _("Edit Audio")
    if request.method == "POST":
        form = AudioEditForm(request.POST, request.FILES, user=request.user,
                         instance=instance)
        if form.is_valid():
            project = form.cleaned_data.get("project")
            if project:
                project = get_object_or_404(Project, pk=project.pk)
            audio = form.save()
            if project:
                project.audios.add(audio)
            return redirect("audio-detail", slug=audio.slug)
    else:
        form = AudioEditForm(user=request.user, instance=instance)

    return render(request, "audio/audio_form.html", {
        'form': form,
        'object': instance,
        'title': title
    })

@login_required
def audio_upload(request, slug=None):
    ## Upload files

    instance = get_object_or_404(Audio, slug=slug) if slug else None
    title = _("Upload Audio") 
    if request.method == "POST":
        form = AudioUploadForm(request.POST, request.FILES, 
                        user=request.user, 
                        instance=instance
                         )
        if form.is_valid():
            for item in request.FILES.getlist('audio'):
                Audio.objects.create(audio=item, user=request.user, name=item.name)
            return redirect("index")

    else:
        form = AudioUploadForm(user=request.user, instance=instance)

    return render(request, "audio/audio_form.html", {
        'form': form,
        'object': instance,
        'title': title
    })

class AudioDetailView(DetailView):
    model = Audio

class  AudioDeleteView(LoginRequiredMixin, UserRequiredMixin, DeleteView):
    model = Audio
    success_url = reverse_lazy('index')
