# -*- coding: utf-8 -*-
import os
import re
import string

from django.contrib.auth.decorators import login_required

from django.urls import reverse_lazy
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, UpdateView, DetailView, CreateView, DeleteView, FormView

from .models import Audio
from project.models import Project
from .forms import AudioForm
from redpanal.utils.views import LoginRequiredMixin, UserRequiredMixin
from django.forms import formset_factory

@login_required
def audio_create_update(request, slug=None):
    audioformset = formset_factory(AudioForm, extra=2)
    instance = get_object_or_404(Audio, slug=slug) if slug else None
    if request.method == "POST":
        form = AudioForm(request.POST, request.FILES, user=request.user,
                         instance=instance)
        formset = audioformset(request.POST, form_kwargs={'user': request.user, 'instance':instance})
        if formset.is_valid():
            for item in request.FILES:
                
                audio = Audio(
                    user = request.user,
                    name=request.FILES[item].name, 
                    audio=request.FILES[item]
                    )
                audio.save()
            return redirect("audio-detail", slug=audio.slug)

            # for form in formset:
                # project = form.cleaned_data.get("project")
                # name = form.cleaned_data.get("name")
                # breakpoint()
                # if project:
                    # project = get_object_or_404(Project, pk=project.pk)
                # audio = form.save(commit=False)
                # audio.name = "123123"
                # audio.audio = request.FILES['form-0-audio']
                # audio.save()
                # if project:
                    # project.audios.add(audio)
            # return redirect("audio-detail", slug=audio.slug)
    else:
        # form = AudioForm(user=request.user, instance=instance)
        formset = audioformset(form_kwargs={'user': request.user, 'instance':instance})

    return render(request, "audio/audio_form.html", {
        'formset': formset,
        'object': instance,
    })

class AudioDetailView(DetailView):
    model = Audio

class  AudioDeleteView(LoginRequiredMixin, UserRequiredMixin, DeleteView):
    model = Audio
    success_url = reverse_lazy('index')
