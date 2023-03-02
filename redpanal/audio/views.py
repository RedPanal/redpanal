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
    ## Upload files
    instance = get_object_or_404(Audio, slug=slug) if slug else None
    if request.method == "POST":
        form = AudioForm(request.POST, request.FILES, 
                        user=request.user, 
                        instance=instance
                         )
        if form.is_valid() is False:
            for item in request.FILES.getlist('audio'):
                Audio.objects.create(audio=item, user=request.user, name=item.name)
            return redirect("index")

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
