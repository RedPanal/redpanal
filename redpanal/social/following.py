"""Who follows whom, and what the people you follow publish (the Comunidad feed)."""
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext as _

FEED_VERBS = ("project_created", "audio_created", "commented", "version_saved", "amplified")


def following_ids(user):
    """Ids of the people this user follows."""
    if user is None or not user.is_authenticated:
        return set()
    from actstream.models import Follow
    ct = ContentType.objects.get_for_model(User)
    return {int(pk) for pk in Follow.objects.filter(user=user, content_type=ct).values_list("object_id", flat=True)}


def community_feed(user, limit=40):
    """Public projects, sounds and comments by the people this user follows, newest first."""
    from actstream.models import Action
    from audio.models import Audio
    from project.models import Project
    from social.models import Message
    from django.db.models import Q
    from actstream.models import Follow
    ids = following_ids(user)
    ct_project = ContentType.objects.get_for_model(Project)
    project_ids = [str(pk) for pk in Follow.objects.filter(user=user, content_type=ct_project)
                   .values_list("object_id", flat=True)]
    if not ids and not project_ids:
        return []
    ct = ContentType.objects.get_for_model(User)
    # Amplified things that aren't public come in too: below, each one shows only if this person can see it.
    actions = (Action.objects.filter(Q(public=True) | Q(verb="amplified"))
               .filter(Q(actor_content_type=ct, actor_object_id__in=[str(i) for i in ids], verb__in=FEED_VERBS)
                       | Q(target_content_type=ct_project, target_object_id__in=project_ids,
                           verb__in=("version_saved", "contributed")))
               .exclude(actor_content_type=ct, actor_object_id=str(user.pk))
               .prefetch_related("actor", "action_object", "target").order_by("-timestamp")[:limit * 3])
    listenable = set(Project.objects.listenable_by(user).values_list("pk", flat=True))
    audible = Audio.objects.visible_to(user)
    items, seen = [], set()
    for a in actions:
        obj = a.action_object
        if obj is None:
            continue
        if isinstance(obj, Project):
            kind, work = "project", obj
            if obj.pk not in listenable or obj.moderation_hidden:
                continue
        elif isinstance(obj, Audio):
            # Tracks of a work show up with their work, unless someone amplified that track itself.
            if obj.moderation_hidden or not audible.filter(pk=obj.pk).exists():
                continue
            if a.verb != "amplified" and obj.contributions.exists():
                continue
            kind, work = "sound", None
        elif isinstance(obj, Message):
            if obj.moderation_hidden:
                continue
            about = obj.content_object
            if isinstance(about, Project) and about.pk not in listenable:
                continue
            if isinstance(about, Audio) and not audible.filter(pk=about.pk).exists():
                continue
            # A general post (from a profile) has nothing attached; a comment talks about a project or sound.
            kind, work = ("comment" if about is not None else "post"), None
        elif a.verb == "contributed" and a.target is not None:
            if a.target.pk not in listenable:
                continue
            kind, work = "layer", a.target
        elif a.verb == "version_saved" and a.target is not None:
            if a.target.pk not in listenable:
                continue
            kind, work, obj = "version", a.target, obj
        else:
            continue
        # One card per project: its newest news (a version, a layer) stands for the older ones.
        key = ("work", work.pk) if work is not None else (kind, obj.pk)
        if key in seen:
            continue
        seen.add(key)
        # What the interaction buttons act on: the project, the sound or the comment itself.
        if work is not None:
            target, target_obj = "proyecto", work
        elif kind == "sound":
            target, target_obj = "sonido", obj
        else:
            target, target_obj = "comentario", obj
        items.append({"kind": kind, "actor": a.actor, "when": a.timestamp, "object": obj, "work": work,
                      "amplified": a.verb == "amplified", "target": target, "target_obj": target_obj,
                      "public": target != "proyecto" or work.visibility == "public"})
        if len(items) >= limit:
            break
    return items


def related_content(user, already, limit=12):
    """More to listen to, linked to what this person plays and tags, beyond the people they follow.

    `already` holds the keys of what the feed shows ("work", pk) / ("sound", pk) so nothing repeats.
    Each item says why it's there.
    """
    from audio.models import Audio, INSTRUMENT_CHOICES
    from project.models import Project, PartRequest
    from taggit.models import Tag
    profile = getattr(user, "userprofile", None)
    instruments = list(profile.instruments or []) if profile else []
    labels = dict(INSTRUMENT_CHOICES)
    my_tags = set(Tag.objects.filter(project__user=user).values_list("name", flat=True))
    my_tags |= set(Tag.objects.filter(audio__user=user).values_list("name", flat=True))
    if profile is not None:
        my_tags |= set(profile.tags.values_list("name", flat=True))
    public_projects = Project.objects.filter(visibility="public", moderation_hidden=False).exclude(user=user)
    shared_sounds = Audio.objects.visible_to(None).filter(contributions__isnull=True).exclude(user=user)
    found = []

    # Projects asking for what this person plays.
    if instruments:
        for r in (PartRequest.objects.filter(PartRequest.open_q(), instrument__in=instruments,
                                             project__in=Project.objects.listed().exclude(user=user))
                  .select_related("project", "project__user").order_by("-created_at")[:limit]):
            found.append((r.created_at, "work", r.project,
                          _("Looking for %(what)s, which you play") % {"what": labels.get(r.instrument, "")}))
    # Projects and sounds with the same hashtags.
    if my_tags:
        for p in public_projects.filter(tags__name__in=my_tags).distinct().select_related("user")[:limit]:
            tag = next((t for t in p.tags.names() if t in my_tags), "")
            found.append((p.created_at, "work", p, _("Because you use #%(tag)s") % {"tag": tag}))
        for s in shared_sounds.filter(tags__name__in=my_tags).distinct().select_related("user")[:limit]:
            tag = next((t for t in s.tags.names() if t in my_tags), "")
            found.append((s.created_at, "sound", s, _("Because you use #%(tag)s") % {"tag": tag}))
    # Sounds for the instruments this person plays.
    if instruments:
        for s in shared_sounds.filter(instrument__in=instruments).select_related("user")[:limit]:
            found.append((s.created_at, "sound", s, _("Because you play %(what)s") % {"what": labels.get(s.instrument, "")}))

    items, seen = [], set(already)
    for when, kind, obj, reason in sorted(found, key=lambda f: f[0], reverse=True):
        key = (kind, obj.pk)
        if key in seen:
            continue
        seen.add(key)
        is_work = kind == "work"
        items.append({"kind": "project" if is_work else "sound", "actor": None, "when": when, "reason": reason,
                      "object": obj, "work": obj if is_work else None, "amplified": False,
                      "target": "proyecto" if is_work else "sonido", "target_obj": obj,
                      "public": not is_work or obj.visibility == "public"})
        if len(items) >= limit:
            break
    return items


def feed_keys(items):
    """What a feed already shows, to leave it out of the related content."""
    return {("work", i["work"].pk) if i["work"] is not None else (i["kind"], i["object"].pk) for i in items}


def people_to_follow(user, limit=6):
    """People who publish things others can listen to, that this user doesn't follow yet."""
    from audio.models import Audio
    from django.db.models import Q
    from project.models import Project
    exclude = following_ids(user) | {user.pk}
    shared = Audio.objects.filter(contributions__isnull=True, moderation_hidden=False)
    return list(User.objects.filter(is_active=True)
                .filter(Q(project__in=Project.objects.listed()) | Q(audio__in=shared))
                .exclude(pk__in=exclude).select_related("userprofile").distinct()
                .order_by("-last_login")[:limit])

def reaction_state(user, obj):
    """(favorited, amplified) for one thing, as this person left it."""
    from .models import Reaction
    if user is None or not user.is_authenticated:
        return False, False
    kinds = set(Reaction.objects.filter(user=user, content_type=ContentType.objects.get_for_model(obj),
                                        object_id=obj.pk).values_list("kind", flat=True))
    return Reaction.FAVORITE in kinds, Reaction.AMPLIFY in kinds


def mark_reactions(user, items):
    """Tell each feed item whether this person already favorited or amplified what it shows."""
    from .models import Reaction
    if not items:
        return items
    done = {(r.kind, r.content_type_id, r.object_id)
            for r in Reaction.objects.filter(user=user)}
    for item in items:
        obj = item["target_obj"]
        ct = ContentType.objects.get_for_model(obj).pk
        item["is_favorite"] = (Reaction.FAVORITE, ct, obj.pk) in done
        item["is_amplified"] = (Reaction.AMPLIFY, ct, obj.pk) in done
    return items
