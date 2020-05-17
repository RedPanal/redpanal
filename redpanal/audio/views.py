# -*- coding: utf-8 -*-
import os
import re
import string

from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, UpdateView, DetailView, CreateView, DeleteView

from .models import Audio
from project.models import Project
from .forms import AudioForm
from redpanal.utils.views import LoginRequiredMixin, UserRequiredMixin


@login_required
def audio_create_update(request, slug=None):
    instance = get_object_or_404(Audio, slug=slug) if slug else None
    if request.method == "POST":
        form = AudioForm(request.POST, request.FILES, user=request.user,
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
        form = AudioForm(user=request.user, instance=instance)

    return render(request, "audio/audio_form.html", {
        'form': form,
        'object': instance,
    })

class AudioDetailView(DetailView):
    model = Audio

class  AudioDeleteView(LoginRequiredMixin, UserRequiredMixin, DeleteView):
    model = Audio
    success_url = reverse_lazy('index')
