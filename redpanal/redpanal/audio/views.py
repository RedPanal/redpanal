# -*- coding: utf-8 -*-
import os
import re
import string

from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse_lazy

from django.views.generic import ListView, UpdateView, DetailView, CreateView, DeleteView

from models import Audio
from forms import AudioForm
from ..utils.views import LoginRequiredMixin, UserRequiredMixin


class AudioCreateView(LoginRequiredMixin, CreateView):
    model = Audio
    form_class = AudioForm

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super(AudioCreateView, self).form_valid(form)


class AudioDetailView(DetailView):
    model = Audio


class  AudioUpdateView(LoginRequiredMixin, UserRequiredMixin, UpdateView):
    model = Audio
    form_class = AudioForm


class  AudioDeleteView(LoginRequiredMixin, UserRequiredMixin, DeleteView):
    model = Audio
    success_url = reverse_lazy('index')
