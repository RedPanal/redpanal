"""Who may see each thing in the activity streams.

The `public` flag stored on each action is a cache that can go stale (a work becomes private,
moderation hides something, a version is taken down). Every page and API that lists actions
passes them through `visible_actions`, which checks each object the action talks about against
the same rules the pages use: `Project.objects.listenable_by/visible_to`, `Audio.objects.visible_to`,
`visible_messages`, `Version.hidden` and `moderation_hidden`.
"""
from django.contrib.auth.models import User


class _Checker:
    """Answers "can this person see this object?", remembering each answer."""

    def __init__(self, user):
        self.user = user if user is not None and user.is_authenticated else None
        self._cache = {}

    def _remember(self, key, compute):
        if key not in self._cache:
            self._cache[key] = compute()
        return self._cache[key]

    def is_self(self, other):
        return self.user is not None and other is not None and other.pk == self.user.pk

    def project_visible(self, project):
        """Can find it (its name): listed works, and the ones this person is part of."""
        from project.models import Project
        return self._remember(("pv", project.pk),
                              lambda: Project.objects.visible_to(self.user).filter(pk=project.pk).exists())

    def project_listenable(self, project):
        """Can hear what's inside: its parts, versions and comments."""
        from project.models import Project
        return self._remember(("pl", project.pk),
                              lambda: Project.objects.listenable_by(self.user).filter(pk=project.pk).exists())

    def audio_visible(self, audio):
        from audio.models import Audio
        return self._remember(("a", audio.pk),
                              lambda: Audio.objects.visible_to(self.user).filter(pk=audio.pk).exists())

    def message_visible(self, message):
        from .models import Message, visible_messages
        return self._remember(("m", message.pk),
                              lambda: visible_messages(Message.objects.filter(pk=message.pk), self.user).exists())

    def version_visible(self, version):
        if not self.project_listenable(version.project):
            return False
        if not version.hidden:
            return True
        return self.is_self(version.created_by) or self.is_self(version.project.user)

    def contribution_visible(self, contribution):
        return self.project_listenable(contribution.project) and self.audio_visible(contribution.audio)

    def object_visible(self, obj, as_target=False):
        """`as_target`: the work something happened in (a part, a version): its content must be audible."""
        from audio.models import Audio
        from project.models import Contribution, Membership, Project, Version
        from .models import Message
        if obj is None:
            return True
        if isinstance(obj, User):
            return obj.is_active
        if isinstance(obj, Project):
            return self.project_listenable(obj) if as_target else self.project_visible(obj)
        if isinstance(obj, Audio):
            return self.audio_visible(obj)
        if isinstance(obj, Message):
            return self.message_visible(obj)
        if isinstance(obj, Version):
            return self.version_visible(obj)
        if isinstance(obj, Contribution):
            return self.contribution_visible(obj)
        if isinstance(obj, Membership):
            # Who is part of a work: only for its author and that person.
            return self.is_self(obj.user) or self.is_self(obj.project.user)
        # Anything else (a group, a reaction...): not listed in streams.
        return False


def can_see_action(action, user, checker=None):
    checker = checker or _Checker(user)
    if not action.public and not checker.is_self(action.actor):
        return False
    # The thing it talks about was deleted: nothing to show.
    if action.action_object_object_id and action.action_object is None:
        return False
    if action.target_object_id and action.target is None:
        return False
    return (checker.object_visible(action.action_object)
            and checker.object_visible(action.target, as_target=True))


def visible_actions(actions, user, limit=None):
    """The actions of `actions` (any iterable or queryset) this person may see, in order.

    With `limit`, stops after that many: pass an unsliced queryset and it is read in chunks.
    """
    checker = _Checker(user)
    found = []
    for action in _iterate(actions):
        if can_see_action(action, user, checker):
            found.append(action)
            if limit is not None and len(found) >= limit:
                break
    return found


def _iterate(actions, chunk=100):
    from django.db.models.query import QuerySet
    if not isinstance(actions, QuerySet) or actions.query.is_sliced:
        yield from actions
        return
    start = 0
    while True:
        batch = list(actions.prefetch_related("actor", "action_object", "target")[start:start + chunk])
        yield from batch
        if len(batch) < chunk:
            return
        start += chunk
