import os
import hashlib
import secrets

from django.db import models, transaction
from django.db.models import Q, Max
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from django.core.files.storage import default_storage
from actstream import action, registry

from taggit.managers import TaggableManager
from autoslug.fields import AutoSlugField
from redpanal.utils.models import BaseModelMixin
from audio.models import Audio, INSTRUMENT_CHOICES, LICENSES_CHOICES
from core import licenses
from pydub import AudioSegment


STATUS_IDEA = "idea"
STATUS_IN_PROGRESS = "in_progress"
STATUS_FINISHED = "finished"
STATUS_CHOICES = (
    (STATUS_IDEA, _("idea")),
    (STATUS_IN_PROGRESS, _("in progress")),
    (STATUS_FINISHED, _("finished")),
)

# Privacy is a stage: a work can start closed and open up when its author wants.
VISIBILITY_PRIVATE = "private"      # the author and the people they invite
VISIBILITY_LINK = "link"            # plus whoever has the secret link
VISIBILITY_OPEN_CALL = "open_call"  # listed: anyone sees the requests and a short preview, and asks to join
VISIBILITY_PUBLIC = "public"        # anyone listens to everything
VISIBILITY_CHOICES = (
    (VISIBILITY_PRIVATE, _("Only me and the people I invite")),
    (VISIBILITY_LINK, _("Whoever has the link")),
    (VISIBILITY_OPEN_CALL, _("Open call: everyone sees what it needs and a preview")),
    (VISIBILITY_PUBLIC, _("Public: everyone listens to everything")),
)
VISIBILITY_SHORT = {  # for tags and summaries
    VISIBILITY_PRIVATE: _("private"),
    VISIBILITY_LINK: _("with link"),
    VISIBILITY_OPEN_CALL: _("open call"),
    VISIBILITY_PUBLIC: _("public"),
}
VISIBILITY_ICONS = {VISIBILITY_PRIVATE: "lock", VISIBILITY_LINK: "link", VISIBILITY_OPEN_CALL: "bullhorn",
                    VISIBILITY_PUBLIC: "globe"}
LISTED_VISIBILITIES = (VISIBILITY_OPEN_CALL, VISIBILITY_PUBLIC)
PREVIEW_SECONDS = 30
LINK_SESSION_KEY = "rp_project_links"


def new_share_token():
    return secrets.token_urlsafe(18)


class ProjectQuerySet(models.QuerySet):

    def listed(self):
        """Works that appear in listings, search and feeds."""
        return self.filter(visibility__in=LISTED_VISIBILITIES, moderation_hidden=False)

    def _with_access(self, base, user):
        # A work hidden by moderation stays only with its author.
        q = base & Q(moderation_hidden=False)
        if user is not None and user.is_authenticated:
            q |= Q(user=user)
            q |= ((Q(memberships__user=user, memberships__status=Membership.ACTIVE)
                   | Q(shared_groups__members__user=user) | Q(shared_groups__owner=user))
                  & Q(moderation_hidden=False))
        return self.filter(q).distinct()

    def listenable_by(self, user):
        """Works whose full audio this user can hear."""
        return self._with_access(Q(visibility=VISIBILITY_PUBLIC), user)

    def visible_to(self, user):
        """Works this user can find: listed ones, their own and the ones they joined."""
        return self._with_access(Q(visibility__in=LISTED_VISIBILITIES), user)


def project_image_upload_to(instance, filename):
    from audio.models import image_upload_to
    return image_upload_to("projects", filename)


class Project(models.Model, BaseModelMixin):
    """A work ("obra"): a song or piece that grows with parts from several people."""

    name = models.CharField(verbose_name=_('name'), max_length=100)
    slug = AutoSlugField(populate_from='name', always_update=False,
                         editable=False, blank=True, unique=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    description = models.TextField(verbose_name=_('description'), blank=True)
    # A project created from another one: the other one is its source (lineage).
    version_of = models.ForeignKey('self', verbose_name=_('based on'),
                                   blank=True, null=True, editable=False,
                                   related_name="versions", on_delete=models.SET_NULL)
    # Kept in sync with the included contributions, for older code paths.
    audios = models.ManyToManyField("audio.Audio", verbose_name=_('audios'),
                                    blank=True)
    image = models.ImageField(verbose_name=_('image'),
                              upload_to=project_image_upload_to,
                              blank=True, null=True,
                              max_length=150)
    user = models.ForeignKey(User, editable=False, verbose_name=_('user'), on_delete=models.CASCADE)
    tags = TaggableManager(blank=True, verbose_name=_('hashtags'))

    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES,
                              default=STATUS_IDEA)
    visibility = models.CharField(_('who can see it'), max_length=20,
                                  choices=VISIBILITY_CHOICES, default=VISIBILITY_PUBLIC)
    license = models.CharField(_('license'), max_length=30, choices=LICENSES_CHOICES,
                               default=licenses.DEFAULT_LICENSE.code)
    tempo = models.PositiveSmallIntegerField(_('tempo (BPM)'), null=True, blank=True)
    musical_key = models.CharField(_('key'), max_length=20, blank=True)
    share_token = models.CharField(max_length=40, unique=True, default=new_share_token, editable=False)
    # Short, low quality excerpt that open calls let anyone hear.
    preview = models.FileField(upload_to="previews/%Y_%m", blank=True, editable=False)
    preview_start_ms = models.PositiveIntegerField(_('preview starts at (ms)'), default=0)
    # Everyone in these groups can listen and contribute, including people who join later.
    shared_groups = models.ManyToManyField("WorkGroup", related_name="works", blank=True)
    moderation_hidden = models.BooleanField(default=False, editable=False)
    # Without downloads only the author gets the files; listening (and recording what plays) still works.
    allow_downloads = models.BooleanField(_('allow downloads'), default=True)
    # Soft beeps over the open call preview.
    preview_watermark = models.BooleanField(_('sound mark on the preview'), default=False)

    objects = ProjectQuerySet.as_manager()

    def get_absolute_url(self):
        return reverse('project-detail', kwargs={'slug': self.slug})

    def visibility_short(self):
        return VISIBILITY_SHORT.get(self.visibility, "")

    def visibility_icon(self):
        return VISIBILITY_ICONS.get(self.visibility, "lock")

    def get_share_url(self):
        return "%s?k=%s" % (self.get_absolute_url(), self.share_token)

    # -- access ------------------------------------------------------------
    # One place decides who sees, listens to and contributes to a work.

    @property
    def is_listed(self):
        return self.visibility in LISTED_VISIBILITIES and not self.moderation_hidden

    def _hidden_for(self, user):
        """Hidden by moderation: only its author and the moderators get in."""
        if not self.moderation_hidden:
            return False
        from moderation.models import is_moderator
        return not (user is not None and user.is_authenticated and (user == self.user or is_moderator(user)))

    def membership_of(self, user):
        if user is None or not user.is_authenticated:
            return None
        return self.memberships.filter(user=user).first()

    def is_member(self, user):
        if user is None or not user.is_authenticated:
            return False
        if user == self.user:
            return True
        m = self.membership_of(user)
        if m and m.status == Membership.ACTIVE:
            return True
        return self.shared_groups.filter(Q(members__user=user) | Q(owner=user)).exists()

    def has_link(self, request):
        """Whoever opened the secret link in this browser session."""
        if request is None or self.visibility != VISIBILITY_LINK:
            return False
        return self.share_token in request.session.get(LINK_SESSION_KEY, [])

    def remember_link(self, request, token):
        if token and secrets.compare_digest(token, self.share_token):
            links = request.session.get(LINK_SESSION_KEY, [])
            if self.share_token not in links:
                request.session[LINK_SESSION_KEY] = links + [self.share_token]
            return True
        return False

    def can_view(self, user, request=None):
        if self._hidden_for(user):
            return False
        from moderation.models import is_moderator
        return (self.is_listed or self.is_member(user) or self.has_link(request)
                or (self.moderation_hidden and is_moderator(user)))

    def can_listen(self, user, request=None):
        if self._hidden_for(user):
            return False
        from moderation.models import is_moderator
        return (self.visibility == VISIBILITY_PUBLIC or self.is_member(user)
                or self.has_link(request) or (self.moderation_hidden and is_moderator(user)))

    def can_contribute(self, user):
        if user is None or not user.is_authenticated or self.moderation_hidden:
            return False
        return self.visibility == VISIBILITY_PUBLIC or self.is_member(user)

    def can_download(self, user, request=None):
        if not self.can_listen(user, request):
            return False
        return self.allow_downloads or (user is not None and user.is_authenticated and user == self.user)

    def members(self):
        return (User.objects.filter(memberships__project=self, memberships__status=Membership.ACTIVE)
                .select_related("userprofile"))

    def access_requests(self):
        return self.memberships.filter(status=Membership.REQUESTED).select_related("user")

    def set_visibility(self, visibility):
        """Change who can see the work, and keep files, previews and feeds consistent."""
        self.visibility = visibility
        self.save(update_fields=["visibility"])
        if visibility != VISIBILITY_PUBLIC:
            for c in self.contributions.select_related("audio"):
                c.audio.move_to_private_path()
        sync_action_visibility(self)
        self.refresh_preview()
        self.reindex_search()

    def reindex_search(self):
        """Search only holds what anyone may see: refresh the work, its audio and comments."""
        from django.contrib.contenttypes.models import ContentType
        from social.models import Message
        from redpanal.utils.search import reindex
        ct = ContentType.objects.get_for_model(Project)
        reindex([self] + list(Audio.objects.filter(contributions__project=self).distinct())
                + list(Message.objects.filter(content_type=ct, object_id=self.pk)))

    def refresh_preview(self):
        """Open calls get a short excerpt of the current mix; other works none."""
        import json
        from .preview import build_preview
        if self.preview:
            peaks_path = self.preview.path + ".json"
            if os.path.exists(peaks_path):
                os.remove(peaks_path)
            self.preview.delete(save=False)
        if self.visibility == VISIBILITY_OPEN_CALL:
            content = build_preview(self)
            if content is not None:
                self.preview.save("%s-preview.mp3" % self.slug, content, save=False)
                with open(self.preview.path + ".json", "w") as f:
                    json.dump(content.peaks, f)
        Project.objects.filter(pk=self.pk).update(preview=self.preview.name or "")

    def preview_peaks_url(self):
        return self.preview.url + ".json" if self.preview else ""

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "project"
        verbose_name_plural = "projects"
        ordering = ["-created_at"]

    def get_license(self):
        return licenses.LICENSES[self.license]

    def create_version(self, user):
        project = Project(name=self.name, description=self.description,
                          version_of=self, user=user)
        project.save()
        project.tags.add(*self.tags.all())
        return project

    def audios_from_versions(self):
        return Audio.objects.filter(project__in=self.versions.all())

    def all_audios(self):
        return Audio.objects.filter(Q(project__in=self.versions.all()) | Q(project=self))

    def collaborators(self):
        return User.objects.filter(Q(audio__in=self.all_audios()) | Q(pk=self.user.pk)).distinct()

    # -- collaboration ---------------------------------------------------

    def contributions_with(self, status):
        return (self.contributions.filter(status=status)
                .select_related('audio', 'audio__user', 'contributor', 'request')
                .order_by('created_at'))

    def parts(self):
        return self.contributions_with(Contribution.INCLUDED)

    def aligned_parts(self):
        """What the single player plays: included parts that line up in time."""
        return self.parts().filter(alignment=Contribution.ALIGNED, audio__moderation_hidden=False)

    def loose_parts(self):
        """Included parts that play on their own: not aligned yet, or independent on purpose."""
        return self.parts().exclude(alignment=Contribution.ALIGNED)

    def proposed(self):
        return self.contributions_with(Contribution.PROPOSED)

    def alternatives(self):
        return self.contributions_with(Contribution.ALTERNATIVE)

    def open_requests(self):
        return self.requests.filter(PartRequest.open_q()).order_by('created_at')

    def credits(self, contributions=None):
        """People and what they played, derived from the included parts."""
        contributions = self.parts() if contributions is None else contributions
        people = {}
        for c in contributions:
            entry = people.setdefault(c.contributor_id, {'user': c.contributor, 'roles': []})
            role = c.audio.get_instrument_display() if c.audio.instrument else c.audio.name
            if role not in entry['roles']:
                entry['roles'].append(role)
        return list(people.values())

    def latest_version(self):
        return self.versions_saved.order_by('-number').first()

    @transaction.atomic
    def save_version(self, user, message=""):
        number = (self.versions_saved.aggregate(n=Max('number'))['n'] or 0) + 1
        version = Version.objects.create(project=self, number=number, created_by=user, message=message,
                                         parent=self.current_version())
        version.contributions.set(self.parts())
        version.attachments.set(self.attachments.filter(replaced=False))
        return version

    def current_version(self):
        """The version that sounds like the work today (its author's), if there is one."""
        now = set(self.parts().values_list("pk", flat=True))
        for version in self.versions_saved.prefetch_related("contributions").order_by("-number"):
            if {c.pk for c in version.contributions.all()} == now:
                return version
        return None

    def first_version(self):
        """Older works had no versions: what sounds today becomes v1, by its author."""
        if not self.versions_saved.exists() and self.parts().exists():
            return self.save_version(self.user)
        return None

    @transaction.atomic
    def new_version(self, user, added, parent=None, message=""):
        """Someone added files: a new version with what `parent` had (by default, what sounds
        today) plus them. The author's own additions are already in what sounds today."""
        added = list(added)
        base = list(parent.contributions.all()) if parent is not None else list(self.parts())
        number = (self.versions_saved.aggregate(n=Max('number'))['n'] or 0) + 1
        version = Version.objects.create(project=self, number=number, created_by=user, message=message,
                                         parent=parent or self.current_version_before(added))
        version.contributions.set({c.pk: c for c in base + added}.values())
        version.attachments.set(self.attachments.filter(replaced=False))
        return version

    def current_version_before(self, added):
        """The latest version that had what sounds today, leaving out the files just added."""
        now = set(self.parts().values_list("pk", flat=True)) - {c.pk for c in added}
        for version in self.versions_saved.prefetch_related("contributions").order_by("-number"):
            if {c.pk for c in version.contributions.all()} == now:
                return version
        return self.latest_version()

    def mix_audios(self, ids):
        audios = self.audios.filter(id__in=ids)
        if len(audios) < 2:
            raise ValueError("Need at least 2 audios to mix")

        # A file whose processing failed (no fingerprint, can't be decoded) is left out of the mix
        # instead of breaking it.
        from audio.models import calculate_hashsum
        from pydub.exceptions import CouldntDecodeError
        readable = []
        for audio in audios:
            try:
                fingerprint = audio.hashsum or calculate_hashsum(audio.audio.path)
                readable.append((audio, fingerprint))
            except (FileNotFoundError, OSError, ValueError):
                continue
        if len(readable) < 2:
            raise ValueError("Need at least 2 readable audios to mix")

        hashsum = hashlib.sha1()
        for _audio, fingerprint in readable:
            hashsum.update(fingerprint.encode())

        hashsum = format(hashsum.hexdigest())
        filename = "%s.ogg" % hashsum

        path = default_storage.path('audio_cache')
        if not default_storage.exists(path):
            os.makedirs(path)

        path = default_storage.path(os.path.join('audio_cache', filename))
        if not default_storage.exists(path):
            mix = AudioSegment.empty()
            for audio, _fingerprint in readable:
                try:
                    a = AudioSegment.from_file(audio.audio.path)
                except (CouldntDecodeError, FileNotFoundError, OSError):
                    continue
                if a.duration_seconds > mix.duration_seconds:
                    mix = a.overlay(mix)
                else:
                    mix = mix.overlay(a)
            mix.export(path, format="ogg")
        return filename


class PartRequest(models.Model):
    """What a work is missing ("pedido"): an instrument or role, open to contributions."""

    project = models.ForeignKey(Project, related_name="requests", on_delete=models.CASCADE)
    instrument = models.CharField(_('instrument'), max_length=30, choices=INSTRUMENT_CHOICES)
    description = models.CharField(_('what you are looking for'), max_length=200, blank=True)
    is_open = models.BooleanField(default=True)
    # Optional: until when layers are welcome. After that date it shows as closed.
    open_until = models.DateField(_('open until'), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.get_instrument_display()

    @staticmethod
    def open_q(prefix=""):
        """Open and not past its date (computed now, never at import time)."""
        today = timezone.localdate()
        return (Q(**{prefix + "is_open": True})
                & (Q(**{prefix + "open_until__isnull": True}) | Q(**{prefix + "open_until__gte": today})))


class Contribution(models.Model):
    """A part in a work ("aporte"). The owner's own parts are contributions too."""

    PROPOSED = "proposed"      # older works: waited for the author's decision
    INCLUDED = "included"      # in what the work sounds like by default (its author's version)
    ALTERNATIVE = "alternative"
    WITHDRAWN = "withdrawn"
    VERSIONED = "versioned"    # someone else's file, in the version they made: no permission needed
    STATUS_CHOICES = (
        (PROPOSED, _("proposed")),
        (INCLUDED, _("included")),
        (ALTERNATIVE, _("alternative")),
        (WITHDRAWN, _("withdrawn")),
        (VERSIONED, _("in a version")),
    )

    project = models.ForeignKey(Project, related_name="contributions", on_delete=models.CASCADE)
    audio = models.ForeignKey(Audio, related_name="contributions", on_delete=models.CASCADE)
    contributor = models.ForeignKey(User, related_name="contributions", on_delete=models.CASCADE)
    request = models.ForeignKey(PartRequest, related_name="contributions", null=True, blank=True,
                                on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PROPOSED)
    note = models.CharField(_('note'), max_length=500, blank=True)
    # Where the part starts relative to the beginning of the work.
    offset_ms = models.IntegerField(_('offset (ms)'), default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    # When the contributor accepted that the part follows the work's license,
    # including if the work is published later.
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    # Name of the stem in the studio folder, to recognise a new take of the same track.
    source_filename = models.CharField(max_length=255, blank=True)

    # Does this part line up in time with the rest? Only aligned parts play together.
    ALIGNED = "aligned"      # confirmed: it plays in the work's single player
    PENDING = "pending"      # unknown: plays on its own until someone aligns it
    SEPARATE = "separate"    # deliberately independent (another idea, a take to compare…)
    ALIGNMENT_CHOICES = (
        (ALIGNED, _("aligned")),
        (PENDING, _("not aligned yet")),
        (SEPARATE, _("independent")),
    )
    # Every upload path decides it (guess_alignment); the default keeps parts created directly playable.
    alignment = models.CharField(max_length=20, choices=ALIGNMENT_CHOICES, default=ALIGNED)

    class Meta:
        ordering = ["created_at"]
        unique_together = (("project", "audio"),)

    def __str__(self):
        return "%s · %s" % (self.audio.name, self.contributor)

    def get_absolute_url(self):
        # Someone else's file is heard in the version they made.
        if self.status == self.VERSIONED:
            version = self.versions.order_by("number").first()
            if version is not None:
                return "%s?v=%d" % (self.project.get_absolute_url(), version.number)
        return "%s#capa-%d" % (self.project.get_absolute_url(), self.pk)

    def set_status(self, status):
        """Move between states. No state deletes anyone's audio."""
        self.status = status
        self.decided_at = timezone.now()
        self.save(update_fields=["status", "decided_at"])
        if status == self.INCLUDED:
            self.project.audios.add(self.audio)
        else:
            self.project.audios.remove(self.audio)
        self.project.refresh_preview()


def durations_match(a_ms, b_ms):
    """Stems exported together from a DAW last the same (a few ms of rounding at most)."""
    if not a_ms or not b_ms:
        return False
    return abs(a_ms - b_ms) <= max(60, 0.005 * max(a_ms, b_ms))


def guess_alignment(project, audio, batch_durations=()):
    """First guess for a new part, before anyone listens.

    The first part sets the timeline. A part as long as the aligned ones, or as
    the other stems uploaded with it, was most likely exported from the same
    session. Anything else waits for someone to align it by ear.
    """
    duration = audio.get_duration()
    aligned = [c.audio.get_duration() for c in project.contributions
               .filter(alignment=Contribution.ALIGNED).exclude(audio_id=audio.pk).select_related("audio")]
    batch = [d for d in batch_durations if d]
    if aligned:
        references = aligned
    elif len(batch) > 1:
        # No timeline yet: full-length stems from a DAW share the longest duration.
        references = [max(batch)]
    else:
        return Contribution.ALIGNED  # the first part sets the timeline
    if any(durations_match(duration, d) for d in references):
        return Contribution.ALIGNED
    return Contribution.PENDING


class Membership(models.Model):
    """A person who can listen to and contribute to a non public work."""

    REQUESTED = "requested"
    ACTIVE = "active"
    STATUS_CHOICES = (
        (REQUESTED, _("asked to join")),
        (ACTIVE, _("member")),
    )

    project = models.ForeignKey(Project, related_name="memberships", on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name="memberships", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)
    message = models.CharField(_('message'), max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        unique_together = (("project", "user"),)

    def __str__(self):
        return "%s · %s (%s)" % (self.project, self.user, self.status)


class Version(models.Model):
    """A moment of a work: which files sounded and who played them.

    Adding a file makes a new version, by whoever added it: the files of the version it comes
    from (`parent`) plus theirs. Nobody asks permission and nothing waits; what the work sounds
    like by default is its author's version, and the author can adopt any other.
    """

    project = models.ForeignKey(Project, related_name="versions_saved", on_delete=models.CASCADE)
    number = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.CharField(_('message'), max_length=500, blank=True)
    contributions = models.ManyToManyField(Contribution, related_name="versions")
    attachments = models.ManyToManyField("Attachment", related_name="versions", blank=True)
    parent = models.ForeignKey("self", null=True, blank=True, related_name="children", on_delete=models.SET_NULL)
    # The author took it off the work's page (rare: it stays for whoever made it).
    hidden = models.BooleanField(default=False)

    class Meta:
        ordering = ["-number"]
        unique_together = (("project", "number"),)

    def __str__(self):
        return "%s · v%d" % (self.project, self.number)

    def get_absolute_url(self):
        return reverse('project-version', kwargs={'slug': self.project.slug, 'number': self.number})

    def parts(self):
        return self.contributions.select_related('audio', 'audio__user', 'contributor').order_by('created_at')

    def credits(self):
        return self.project.credits(self.parts())


def new_group_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I: easy to dictate in class
    return "".join(secrets.choice(alphabet) for _ in range(6))


def group_slug(name, others):
    """The group's address: its name, never only digits (those are old numeric addresses), unique."""
    from django.utils.text import slugify
    base = (slugify(name) or "grupo")[:100]
    if base.isdigit():
        base = "grupo-" + base
    slug, n = base, 2
    while others.filter(slug=slug).exists():
        slug, n = "%s-%d" % (base, n), n + 1
    return slug


class WorkGroup(models.Model):
    """A class or workshop: people join with a code and share works among them."""
    name = models.CharField(_('name'), max_length=100)
    owner = models.ForeignKey(User, related_name="owned_groups", on_delete=models.CASCADE)
    code = models.CharField(max_length=12, unique=True, default=new_group_code)
    slug = models.SlugField(max_length=110, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = group_slug(self.name, WorkGroup.objects.exclude(pk=self.pk))
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('group-detail', kwargs={'slug': self.slug})

    def is_member(self, user):
        return user.is_authenticated and (user == self.owner or self.members.filter(user=user).exists())


class GroupMember(models.Model):
    group = models.ForeignKey(WorkGroup, related_name="members", on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name="group_memberships", on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["joined_at"]
        unique_together = (("group", "user"),)


class WorkSource(models.Model):
    """A sound or a work that another work is made from: credited and shown in the lineage."""
    project = models.ForeignKey(Project, related_name="sources", on_delete=models.CASCADE)
    audio = models.ForeignKey(Audio, related_name="used_in", null=True, blank=True, on_delete=models.SET_NULL)
    source_project = models.ForeignKey(Project, related_name="used_in", null=True, blank=True,
                                       on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return str(self.audio or self.source_project)

    @property
    def author(self):
        obj = self.audio or self.source_project
        return obj.user if obj else None


def attachment_upload_to(instance, filename):
    import datetime, posixpath, unicodedata
    filename = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode()
    return posixpath.join(datetime.datetime.now().strftime('uploads/sessions/%Y_%m'),
                          secrets.token_urlsafe(16), filename)


ATTACHMENT_KINDS = {
    # Session files: only useful with the same DAW and plugins; kept as they are.
    "session": ["cpr", "ptx", "ptf", "als", "rpp", "flp", "song", "bwproject", "logicx", "aup3", "ardour", "zip"],
    # Open exchange format between DAWs.
    "dawproject": ["dawproject"],
    "midi": ["mid", "midi"],
    "preset": ["fxp", "fxb", "vstpreset", "aupreset", "nmsv", "adv", "adg", "h2p", "tfx"],
    "notes": ["txt", "pdf", "md"],
}
ATTACHMENT_EXTENSIONS = sorted(ext for exts in ATTACHMENT_KINDS.values() for ext in exts)


def attachment_kind(filename):
    ext = os.path.splitext(filename)[1][1:].lower()
    for kind, exts in ATTACHMENT_KINDS.items():
        if ext in exts:
            return kind
    return None


class Attachment(models.Model):
    """A file that travels with a work but RedPanal doesn't play: sessions, MIDI, presets."""

    KIND_CHOICES = (
        ("session", _("DAW session")),
        ("dawproject", _("DAWproject (open format)")),
        ("midi", _("MIDI")),
        ("preset", _("effect or instrument preset")),
        ("notes", _("notes")),
    )

    project = models.ForeignKey(Project, related_name="attachments", on_delete=models.CASCADE)
    uploaded_by = models.ForeignKey(User, related_name="attachments", on_delete=models.CASCADE)
    file = models.FileField(upload_to=attachment_upload_to, max_length=300)
    name = models.CharField(max_length=255)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    size = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # A newer file with the same name replaces this one; old versions keep it.
    replaced = models.BooleanField(default=False)

    class Meta:
        ordering = ["name", "-created_at"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('project-attachment', kwargs={'slug': self.project.slug, 'pk': self.pk})


def project_created_signal(sender, instance, created, **kwargs):
    if created:
        action.send(instance.user, verb='project_created', action_object=instance,
                    public=instance.is_listed)

post_save.connect(project_created_signal, sender=Project)


def sync_action_visibility(project):
    """Feeds only show what everyone may see.

    Announcing a listed work is public; audio, contributions and comments
    are public only when the work is public.
    """
    from django.contrib.contenttypes.models import ContentType
    from actstream.models import Action
    from social.models import Message

    ct_project = ContentType.objects.get_for_model(Project)
    ct_audio = ContentType.objects.get_for_model(Audio)
    ct_contribution = ContentType.objects.get_for_model(Contribution)
    ct_version = ContentType.objects.get_for_model(Version)
    ct_message = ContentType.objects.get_for_model(Message)
    pk = str(project.pk)
    is_public = project.visibility == VISIBILITY_PUBLIC

    Action.objects.filter(action_object_content_type=ct_project, action_object_object_id=pk).update(
        public=project.is_listed)
    audio_ids = [str(i) for i in project.contributions.values_list("audio_id", flat=True)]
    contribution_ids = [str(i) for i in project.contributions.values_list("pk", flat=True)]
    version_ids = [str(i) for i in project.versions_saved.values_list("pk", flat=True)]
    message_ids = [str(i) for i in Message.objects.filter(content_type=ct_project, object_id=project.pk)
                   .values_list("pk", flat=True)]
    Action.objects.filter(
        Q(action_object_content_type=ct_audio, action_object_object_id__in=audio_ids)
        | Q(action_object_content_type=ct_contribution, action_object_object_id__in=contribution_ids)
        | Q(action_object_content_type=ct_version, action_object_object_id__in=version_ids)
        | Q(action_object_content_type=ct_message, action_object_object_id__in=message_ids)
        | Q(target_content_type=ct_project, target_object_id=pk)
    ).update(public=is_public)
