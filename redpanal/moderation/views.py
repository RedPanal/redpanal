"""Reports and the volunteers' panel. Hiding never deletes anyone's work."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from audio.models import Audio
from project.models import Project, sync_action_visibility
from social.models import Message
from .models import Report, is_moderator

REPORTABLE = {"obra": Project, "audio": Audio, "comentario": Message}


def _can_see(user, obj, request):
    if isinstance(obj, Project):
        return obj.can_view(user, request)
    if isinstance(obj, Audio):
        return obj.can_listen(user, request)
    target = obj.content_object
    if isinstance(target, Project):
        return target.can_view(user, request) and not obj.moderation_hidden
    return not obj.moderation_hidden


def _back_url(obj):
    if isinstance(obj, Message) and isinstance(obj.content_object, Project):
        return obj.content_object.get_absolute_url() + "#conversacion"
    return obj.get_absolute_url() if hasattr(obj, "get_absolute_url") else "/"


@login_required
def report_create(request, kind, pk):
    model = REPORTABLE.get(kind)
    if model is None:
        raise Http404
    obj = get_object_or_404(model, pk=pk)
    if not _can_see(request.user, obj, request):
        raise Http404
    if request.method == "POST":
        reason = request.POST.get("reason")
        if reason in dict(Report.REASONS):
            Report.objects.create(reporter=request.user, content_type=ContentType.objects.get_for_model(model),
                                  object_id=obj.pk, reason=reason, detail=request.POST.get("detail", "")[:2000])
            messages.success(request, _("Thanks. The volunteers who moderate will review it."))
            return redirect(_back_url(obj))
    return render(request, "moderation/report_form.html", {
        "object": obj, "kind": kind, "reasons": Report.REASONS, "back": _back_url(obj),
    })


def _context_of(obj):
    """What the moderator needs to decide: where it is used and what came from it."""
    if isinstance(obj, Audio):
        return {"works": Project.objects.filter(contributions__audio=obj).distinct(),
                "derived": Project.objects.filter(sources__audio=obj).distinct()}
    if isinstance(obj, Project):
        return {"works": [], "derived": Project.objects.filter(version_of=obj)}
    return {"works": [], "derived": []}


@login_required
def panel(request):
    if not is_moderator(request.user):
        raise PermissionDenied
    show = request.GET.get("ver", Report.OPEN)
    reports = Report.objects.filter(status=show).select_related("reporter", "content_type")[:100]
    items = []
    for r in reports:
        obj = r.content_object
        items.append({"report": r, "object": obj, "kind": type(obj).__name__.lower() if obj else None,
                      **(_context_of(obj) if obj else {"works": [], "derived": []})})
    return render(request, "moderation/panel.html", {"items": items, "show": show,
                                                      "statuses": Report.STATUSES})


def set_hidden(obj, hidden):
    """Hide or bring back. Feeds and search follow; files and credits stay where they are."""
    obj.moderation_hidden = hidden
    obj.save(update_fields=["moderation_hidden"])
    from redpanal.utils.search import reindex
    from actstream.models import Action
    if isinstance(obj, Project):
        sync_action_visibility(obj)
        obj.reindex_search()
    else:
        ct = ContentType.objects.get_for_model(type(obj))
        if hidden:
            Action.objects.filter(action_object_content_type=ct, action_object_object_id=str(obj.pk)).update(public=False)
        reindex([obj])


@login_required
@require_POST
def decide(request, pk):
    if not is_moderator(request.user):
        raise PermissionDenied
    report = get_object_or_404(Report, pk=pk)
    decision = request.POST.get("decision")
    note = request.POST.get("note", "")[:500]
    obj = report.content_object
    if decision == "hide" and obj is not None:
        set_hidden(obj, True)
        Report.objects.filter(content_type=report.content_type, object_id=report.object_id,
                              status=Report.OPEN).update(status=Report.HIDDEN)
        report.resolve(request.user, Report.HIDDEN, note)
    elif decision == "restore" and obj is not None:
        set_hidden(obj, False)
        report.resolve(request.user, Report.DISMISSED, note)
    else:
        report.resolve(request.user, Report.DISMISSED, note)
    return redirect("moderation-panel")
