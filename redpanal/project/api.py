"""Works over the API: what the studio sync tool (tools/redpanal_sync.py) needs.

Same access rules as the web: a work is reached only if the person may see it,
and changes go through the same functions (add_stems, save_version).
"""
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from audio.uploads import ACCEPTED_EXTENSIONS
from redpanal.api import SignedTokenAuthentication
from .models import ATTACHMENT_EXTENSIONS, Contribution, Project, VISIBILITY_PUBLIC
from .stems import add_stems


def _work_summary(project, user):
    return {
        "slug": project.slug, "name": project.name, "visibility": project.visibility,
        "status": project.status, "is_owner": project.user_id == user.pk,
        "can_contribute": project.can_contribute(user), "url": project.get_absolute_url(),
    }


def _work_or_404(request, slug):
    project = get_object_or_404(Project, slug=slug)
    if not project.can_view(request.user, request):
        raise Http404
    return project


@api_view(["GET"])
@authentication_classes([SignedTokenAuthentication])
@permission_classes([IsAuthenticated])
def works(request):
    """Works this person can see; ?mine=1 for only their own."""
    mine = Project.objects.visible_to(request.user).order_by("-created_at")
    if request.query_params.get("mine"):
        mine = mine.filter(user=request.user)
    return Response([_work_summary(p, request.user) for p in mine[:200]])


@api_view(["GET"])
@authentication_classes([SignedTokenAuthentication])
@permission_classes([IsAuthenticated])
def work_detail(request, slug):
    project = _work_or_404(request, slug)
    data = _work_summary(project, request.user)
    if project.can_listen(request.user, request):
        data["parts"] = [{
            "id": c.pk, "name": c.audio.name, "instrument": c.audio.instrument,
            "contributor": c.contributor.username, "status": c.status, "offset_ms": c.offset_ms,
            "source_filename": c.source_filename,
            "sha256": [h for h in (c.audio.sha256, c.audio.source_sha256) if h],
        } for c in project.contributions.exclude(status=Contribution.WITHDRAWN).select_related("audio", "contributor")]
        data["attachments"] = [{"name": a.name, "kind": a.kind, "size": a.size, "sha256": a.sha256}
                               for a in project.attachments.filter(replaced=False)]
        data["versions"] = [{"number": v.number, "created_at": v.created_at, "message": v.message}
                            for v in project.versions_saved.all()]
    data["accepted_extensions"] = {"audio": ACCEPTED_EXTENSIONS, "attachments": ATTACHMENT_EXTENSIONS}
    return Response(data)


@api_view(["POST"])
@authentication_classes([SignedTokenAuthentication])
@permission_classes([IsAuthenticated])
def work_stems(request, slug):
    project = _work_or_404(request, slug)
    if not project.can_contribute(request.user):
        return Response({"error": _("You can't contribute to this work.")}, status=403)
    files = request.FILES.getlist("stems")
    if not files:
        return Response({"error": _("No file arrived.")}, status=400)
    accept = str(request.data.get("accept_terms", "")).lower() in ("1", "true", "yes", "on")
    result = add_stems(project, request.user, files, instruments=request.data.getlist("instruments"),
                       note=str(request.data.get("note", ""))[:500], accept_terms=accept)
    status = 400 if result.errors and not (result.added or result.replaced or result.attachments) else 200
    return Response({
        "added": result.added, "replaced": result.replaced, "unchanged": result.unchanged,
        "attachments": result.attachments, "attachments_unchanged": result.attachments_unchanged,
        "errors": result.errors,
    }, status=status)


@api_view(["POST"])
@authentication_classes([SignedTokenAuthentication])
@permission_classes([IsAuthenticated])
def work_versions(request, slug):
    from actstream import action
    project = _work_or_404(request, slug)
    if request.user != project.user:
        return Response({"error": _("Only the person who created the work saves versions.")}, status=403)
    version = project.save_version(request.user, str(request.data.get("message", ""))[:500])
    action.send(request.user, verb='version_saved', action_object=version, target=project,
                public=project.visibility == VISIBILITY_PUBLIC)
    return Response({"number": version.number, "url": version.get_absolute_url()}, status=201)
