"""Groups for classes and workshops: join with a code, share works, see who took part."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .models import Contribution, GroupMember, Project, WorkGroup


def invite_to_group(request, group, text):
    """Add the people written as @username (or just their usernames) to a group, and tell them."""
    import re
    from django.contrib.auth.models import User
    from social.models import notify
    names = {n.strip("@.") for n in re.split(r"[\s,;]+", text or "") if n.strip("@.")}
    added, unknown = [], []
    for name in sorted(names)[:50]:
        person = User.objects.filter(username__iexact=name, is_active=True).first()
        if person is None:
            unknown.append(name)
            continue
        if person == group.owner:
            continue
        _member, created = GroupMember.objects.get_or_create(group=group, user=person)
        if created:
            notify(person, request.user, "member_added", group.name, group.get_absolute_url())
            added.append(person)
    if added:
        messages.success(request, _("Added to «%(group)s»: %(people)s.") % {
            "group": group.name, "people": ", ".join("@" + p.username for p in added)})
    if unknown:
        messages.error(request, _("There's no one called %s.") % ", ".join("@" + n for n in unknown))
    return added


@login_required
def group_list(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()[:100]
        if name:
            group = WorkGroup.objects.create(name=name, owner=request.user)
            messages.success(request, _("Group created. Share the code %s with your class.") % group.code)
            invite_to_group(request, group, request.POST.get("people", ""))
            return redirect(group)
    groups = (WorkGroup.objects.filter(Q(owner=request.user) | Q(members__user=request.user))
              .distinct().annotate(n_members=Count("members", distinct=True)))
    return render(request, "project/groups.html", {"groups": groups})


@login_required
@require_POST
def group_join(request):
    code = request.POST.get("code", "").strip().upper().replace(" ", "")
    group = WorkGroup.objects.filter(code=code).first()
    if group is None:
        messages.error(request, _("There is no group with the code %s.") % code)
        return redirect("groups")
    if request.user != group.owner:
        GroupMember.objects.get_or_create(group=group, user=request.user)
    messages.success(request, _("You joined «%s».") % group.name)
    return redirect(group)


@login_required
def group_by_number(request, pk, rest=""):
    """Old numeric addresses (/grupos/12/) go to the group's name."""
    group = get_object_or_404(WorkGroup, pk=pk)
    return HttpResponsePermanentRedirect(group.get_absolute_url() + rest)


@login_required
def group_detail(request, slug):
    group = get_object_or_404(WorkGroup, slug=slug)
    if not group.is_member(request.user):
        raise Http404
    is_owner = request.user == group.owner
    works = group.works.select_related("user").order_by("-created_at")
    members = group.members.select_related("user", "user__userprofile")
    # Who took part: contributions of each member to the group's works.
    counts = dict(Contribution.objects.filter(project__in=works).exclude(status=Contribution.WITHDRAWN)
                  .values_list("contributor").annotate(n=Count("pk")))
    rows = [(m, counts.get(m.user_id, 0)) for m in members]
    return render(request, "project/group_detail.html", {
        "group": group, "is_owner": is_owner, "works": works, "rows": rows,
    })


@login_required
@require_POST
def group_invite(request, slug):
    """The coordinator adds people by their @username, without passing the code around."""
    group = get_object_or_404(WorkGroup, slug=slug)
    if request.user != group.owner:
        raise PermissionDenied
    invite_to_group(request, group, request.POST.get("people", ""))
    return redirect(group)


@login_required
@require_POST
def group_member_remove(request, slug, member_pk):
    group = get_object_or_404(WorkGroup, slug=slug)
    member = get_object_or_404(GroupMember, pk=member_pk, group=group)
    if request.user != group.owner and request.user != member.user:
        raise PermissionDenied
    member.delete()
    if request.user == member.user:
        messages.info(request, _("You left «%s».") % group.name)
        return redirect("groups")
    return redirect(group)


@login_required
@require_POST
def share_with_group(request, slug):
    """The author of a work shares it with (or stops sharing it with) one of their groups."""
    project = get_object_or_404(Project, slug=slug)
    if request.user != project.user:
        raise PermissionDenied
    group = get_object_or_404(WorkGroup, pk=request.POST.get("group"))
    if not group.is_member(request.user):
        raise PermissionDenied
    if request.POST.get("remove"):
        project.shared_groups.remove(group)
    else:
        project.shared_groups.add(group)
        messages.success(request, _("Everyone in «%s» can now listen and contribute.") % group.name)
    return redirect("project-settings", slug=project.slug)
