from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse_lazy
from django.views.generic import ListView, UpdateView, DetailView, CreateView, DeleteView

from models import Project
from forms import ProjectForm
from redpanal.utils.views import LoginRequiredMixin, UserRequiredMixin

class ProjectDetailView(DetailView):
    model = Project


class ProjectCreateView(LoginRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super(ProjectCreateView, self).form_valid(form)


class  ProjectUpdateView(LoginRequiredMixin, UserRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm


class  ProjectDeleteView(LoginRequiredMixin, UserRequiredMixin, DeleteView):
    model = Project
    success_url = reverse_lazy('index')

class ProjectListView(ListView):
    model = Project
