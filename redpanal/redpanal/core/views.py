from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse_lazy

from redpanal.audio.models import Audio
from redpanal.project.models import Project
from redpanal.social.models import Message
from redpanal.users.models import UserProfile
from taggit.models import Tag
from itertools import chain
import actstream.models
from datetime import datetime

def index(request):
    context = {}
    if request.user.is_authenticated():
        context.update({
        'ctype': ContentType.objects.get_for_model(User),
        'actor': request.user,
        'action_list': actstream.models.user_stream(request.user),
        "refresh_after_modal": 'refresh',
        })
    else:
        return redirect("/accounts/login/?next=/")

    if request.is_ajax():
        template = "social/actions_list.html"
    else:
        template =  "index.html"
    return render(request, template, context)

def hashtaged_list(request, slug, filters='all'):
    tag = get_object_or_404(Tag, slug=slug)

    audios = Audio.objects.filter(tags__slug=slug).order_by('-created_at') if filters == 'all' or filters == 'audios' else [] 
    projects = Project.objects.filter(tags__slug=slug).order_by('-created_at') if filters == 'all' or filters == 'projects' else []
    messages = Message.objects.filter(tags__slug=slug).order_by('-created_at') if filters == 'all' or filters == 'messages' else []
    users = User.objects.filter(userprofile__tags__slug=slug) if filters == 'all' or filters == 'users' else []

    mixed = sorted(chain(audios, projects, messages, users), key=lambda instance: instance.created_at, reverse=True)

    if request.is_ajax():
        template = "core/mixed_list.html"
    else:
        template = "core/hashtaged_list.html"

    return render(request, template, {
           "list_type": 'mixed',
           "mixed_objects": mixed,
           "tag": tag,
           "filters": filters,
    })


def activity_all(request):

    audios = Audio.objects.all()
    projects = Project.objects.all()
    messages = Message.objects.all()

    mixed_list = sorted(chain(audios, projects, messages), key=lambda instance: instance.created_at, reverse=True)
   
    if request.is_ajax():
        return render(request, "core/mixed_list.html", {
            "mixed_objects": mixed_list,
        })
    else:
        # ordered list of users
        users = User.objects.all().order_by('-date_joined')

        # statistics
        count_users = users.count()
        count_audios = audios.count()
        count_projects = projects.count()
        count_messages = messages.count()

        # get logged in users
        # http://stackoverflow.com/questions/2723052/how-to-get-the-list-of-the-authenticated-users
        # sessions = Session.objects.filter(expire_date__gte=datetime.now())
        # uid_list = []
        # for session in sessions:
        #    data = session.get_decoded()
        #    uid_list.append(data.get('_auth_user_id', None))
        # logged_users = users.filter(id__in=uid_list)   
        
        return render(request, "all_activities.html", {
            "mixed_objects": mixed_list,
            "count_audios": count_audios,
            "count_projects": count_projects,
            "count_messages": count_messages,
            "count_users": count_users,
            "last_users": users,
             # "logged_users": logged_users,
            "refresh_after_modal": 'refresh',
        })
