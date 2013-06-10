# -*- coding: utf-8 -*-
import os
import re
import string

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse_lazy

from django.views.generic import ListView, UpdateView, DetailView, CreateView, DeleteView

from models import AudioFile
from forms import AudioFileForm

class LoginRequiredMixin(object):

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(LoginRequiredMixin, self).dispatch(*args, **kwargs)

class UserRequiredMixin(object):

    def get_object(self, queryset=None):
        object = super(UserRequiredMixin, self).get_object(queryset)
        if object.user == self.request.user:
            return object
        else:
            raise PermissionDenied

class AudioCreateView(LoginRequiredMixin, CreateView):
    model = AudioFile
    form_class = AudioFileForm

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super(AudioCreateView, self).form_valid(form)

class AudioDetailView(DetailView):
    model = AudioFile

class  AudioUpdateView(LoginRequiredMixin, UserRequiredMixin, UpdateView):
    model = AudioFile
    form_class = AudioFileForm

class  AudioDeleteView(LoginRequiredMixin, UserRequiredMixin, DeleteView):
    model = AudioFile
    success_url = reverse_lazy('index')
