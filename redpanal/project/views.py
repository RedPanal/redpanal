from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse_lazy
from django.views.generic import ListView, UpdateView, DetailView, CreateView, DeleteView

from .models import Project
from .forms import ProjectForm
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

@login_required
def create_version(request, slug):
    project = get_object_or_404(Project, slug=slug)
    if request.method == "POST":
        new_project = project.create_version(request.user)
        new_project.user = request.user
        new_project.save()
        return redirect("project-detail", slug=project.slug)

    return render(request, "project/project_create_version.html", {
        'object': project,
    })


@login_required
def download_mix(request, slug=None):
    project = get_object_or_404(Project, slug=slug)
    errors = None
    if request.method == "POST":
        ids = request.POST.getlist('ids')
        if len(ids) > 1:
            filename = project.mix_audios(ids)
            return redirect("/media/audio_cache/%s" % filename)
        errors = {'two_tracks': True}

    return render(request, "project/project_download_mix.html", {
        'object': project, 'errors': errors,
    })
