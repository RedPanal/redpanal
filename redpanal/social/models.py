import re

from django.db import models
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.utils.safestring import mark_safe
from django.db.models.signals import post_save
from django.urls import reverse
from django.contrib.sites.models import Site
from django.utils.html import escape, strip_tags

from actstream import action, registry
from taggit.managers import TaggableManager
from taggit.models import Tag

from audio.models import Audio
from project.models import Project


def tag_get_absolute_url(self):
    return reverse("hashtaged-list", None, (self.slug,))

Tag.get_absolute_url = tag_get_absolute_url


class Message(models.Model):
    msg = models.TextField(verbose_name=_('message'))
    user = models.ForeignKey(User, verbose_name=_('user'), editable=False, on_delete=models.CASCADE)
    created_at = models.DateTimeField(verbose_name=_('created at'), auto_now_add=True)
    tags = TaggableManager(verbose_name=_('hashtags'), blank=True)
    mentioned_users = models.ManyToManyField(User, verbose_name=_('hashtags'), blank=True,
                                           editable=False, related_name="mentioned_messages")
    content_type = models.ForeignKey(ContentType, null=True, editable=False, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(null=True, editable=False)
    content_object = GenericForeignKey('content_type', 'object_id')
    # Moment of the audio the comment refers to, when it was made while listening.
    at_ms = models.PositiveIntegerField(null=True, blank=True, editable=False)
    # A reply to another comment (one level, like a conversation thread).
    parent = models.ForeignKey('self', null=True, blank=True, editable=False, related_name="replies",
                               on_delete=models.CASCADE)
    moderation_hidden = models.BooleanField(default=False, editable=False)
    _msg_html_cache = models.TextField(editable=False, blank=True, null=True)

    def __str__(self):
        return mark_safe(self.as_html())

    def get_absolute_url(self):
        """Where it lives, landing on it: the project or sound it talks about, or its author's profile for a
        general post. Replies land on their thread."""
        thread = self.parent if self.parent_id else self
        about = thread.content_object
        home = about if about is not None and hasattr(about, "get_absolute_url") else thread.user
        return home.get_absolute_url() + "#c%d" % thread.pk

    def where(self):
        """What it talks about (a project or a sound), or None for a general post."""
        thread = self.parent if self.parent_id else self
        about = thread.content_object
        return about if getattr(about, "name", None) else None

    def as_html(self):
        if not self._msg_html_cache:
            self._msg_html_cache = Message.to_html(self.msg)
            self.save()
        return self._msg_html_cache

    # @username, as Django allows it (letters, digits, . + - _), without a trailing period: "gracias @lucia."
    MENTION_REGEX = re.compile(r'(?<![\w@])@([\w.+-]*[\w+-])')

    @staticmethod
    def to_html(msg):
        USER_REGEX = Message.MENTION_REGEX
        HASHTAG_REGEX = re.compile(r'#(\w+)')
        domain = Site.objects.get_current().domain
        domain = domain.replace(".", "\.")
        OBJECTS_URL_REGEX = re.compile(r'(https?://)(%s)/([p|a])/([0-9a-zA-Z_-]+)/?' % domain)
        URL_REGEX = re.compile(r'(https?://)(www\.)?(\S+)')

        html_replaces = []
        def get_and_store_hash(value):
            rep_hash = str(hash(value))
            html_replaces.append((rep_hash, value))
            return rep_hash

        def replace_user(match):
            if match:
                username = match.group(1)
                try:
                    user = User.objects.get(username=username)
                except User.DoesNotExist:
                    return match.group()
                new = '<a href="%s">@%s</a>' % (escape(user.get_absolute_url()), escape(username))
                return get_and_store_hash(new)

        def replace_hashtags(match):
            if match:
                tag = match.group(1)
                try:
                    tagobj = Tag.objects.get(name=tag)
                except Tag.DoesNotExist:
                    return match.group()
                new = '<a href="%s">#%s</a>' % (escape(tagobj.get_absolute_url()), escape(tag))
                return get_and_store_hash(new)

        def replace_objects_urls(match):
            if match:
                slug = match.group(4)
                if match.group(3) == 'a':
                    try:
                        obj = Audio.objects.get(slug=slug)
                    except Audio.DoesNotExist:
                        return match.group()
                elif match.group(3) == 'p':
                    try:
                        obj = Project.objects.get(slug=slug)
                    except Project.DoesNotExist:
                        return match.group()
                else:
                    return match.group()
                # The HTML is cached and shared by every viewer: only public objects may be expanded.
                if isinstance(obj, Audio):
                    is_public = Audio.objects.visible_to(None).filter(pk=obj.pk).exists()
                else:
                    is_public = Project.objects.visible_to(None).filter(pk=obj.pk).exists()
                if not is_public:
                    return match.group()
                text = obj.name[:25] + (obj.name[25:] and '..')
                # Names are written by people: never markup.
                new = '<a href="%s"><i class="fa alias-%s"></i>%s</a>' % (
                    escape(obj.get_absolute_url()), escape(obj._meta.verbose_name), escape(text))
                return get_and_store_hash(new)

        def replace_urls(match):
            if match:
                url = match.group(0)
                text = match.group(3)[:25] + (match.group(3)[25:] and '..')
                # A quote or a bracket in the address must not open an attribute or a tag.
                new = '<a href="%s" target="_blank" rel="noopener nofollow">%s</a>' % (escape(url), escape(text))
                return get_and_store_hash(new)

        # Replace strings for hashes and save the new html in context
        html = re.sub(USER_REGEX, replace_user, msg)
        html = re.sub(HASHTAG_REGEX, replace_hashtags, html)
        html = re.sub(OBJECTS_URL_REGEX, replace_objects_urls, html)
        html = re.sub(URL_REGEX, replace_urls, html)

        # Remove all html tags, and escape what's left (a "<" without its ">", quotes, "&")
        html = escape(strip_tags(html))

        # Replace the hashes with our versions of the html
        for rep_hash, new_html in html_replaces:
            html = html.replace(rep_hash, new_html)

        html = html.replace("\n", "<br>")
        return html

    @staticmethod
    def extract_mentioned_users(msg):
        """Returns the users mentioned with @userfoo @UserBar, also next to punctuation ("@lucia," "(@tincho)")."""
        return User.objects.filter(username__in=set(Message.MENTION_REGEX.findall(msg)))

    @staticmethod
    def extract_hashtags(msg):
        """Returns the list of hashtags in the msg"""
        msg = msg.replace(".", " ").replace(";", " ").replace(",", " ")
        words = msg.split()
        tags = filter(lambda word: word.startswith('#'), words)
        return [tag[1:] for tag in tags]

    def save(self, *args, **kwargs):
        super(Message, self).save(*args, **kwargs)

        tags = Message.extract_hashtags(self.msg)
        self.tags.clear()
        if tags:
            self.tags.add(*tags)

        mentioned_users = Message.extract_mentioned_users(self.msg)
        self.mentioned_users.clear()
        if mentioned_users:
            self.mentioned_users.add(*mentioned_users)

    def get_app_label(self):
        return 'social'
    
    def get_model_name(self):
        return 'message'

    class Meta:
        ordering = ['-created_at']

def message_is_public(message):
    """Anyone may read it: not hidden, and about something everyone can hear (or a general post)."""
    if message.moderation_hidden or (message.parent_id and message.parent.moderation_hidden):
        return False
    about = message.content_object
    # A comment whose project or sound was deleted is not a general post: it has nothing to show.
    if about is None:
        return message.object_id is None
    if isinstance(about, Project):
        return about.visibility == "public" and not about.moderation_hidden
    if isinstance(about, Audio):
        return Audio.objects.visible_to(None).filter(pk=about.pk).exists()
    return True


def sync_message_actions(messages):
    """Keep the `public` flag of the actions about these comments (and their replies) up to date."""
    from actstream.models import Action
    ct = ContentType.objects.get_for_model(Message)
    messages = list(messages)
    replies = Message.objects.filter(parent__in=[m.pk for m in messages]).exclude(pk__in=[m.pk for m in messages])
    for m in messages + list(replies):
        Action.objects.filter(action_object_content_type=ct, action_object_object_id=str(m.pk)).update(
            public=message_is_public(m))


def message_created_signal(sender, instance, created, **kwargs):
    if created:
        # A comment on a work or sound not everyone can hear stays out of the public feeds.
        action.send(instance.user, verb='commented', action_object=instance, public=message_is_public(instance))


class Reaction(models.Model):
    """Someone marks a project, sound or comment as a favorite, or amplifies it to the people who follow them."""
    FAVORITE = "favorite"
    AMPLIFY = "amplify"
    KINDS = ((FAVORITE, _("favorite")), (AMPLIFY, _("amplify")))

    user = models.ForeignKey(User, related_name="reactions", on_delete=models.CASCADE)
    kind = models.CharField(max_length=10, choices=KINDS)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("user", "kind", "content_type", "object_id"),)
        ordering = ["-created_at"]


class Notification(models.Model):
    """Someone did something with you or your work: shown with the bell, can be turned off per kind."""
    # Kinds people can turn off from their profile, in the order they are offered.
    PREFERENCES = (
        ("contributed", _("someone makes a new version of my project")),
        ("decided", _("my part is included or kept as an alternative")),
        ("commented", _("someone comments on my project or sound, or mentions me")),
        ("access_requested", _("someone asks to join my project")),
        ("member_added", _("I'm added to a project")),
        ("used_as_source", _("someone creates a project with my project or sound")),
        ("version_saved", _("a project I took part in saves a version")),
        ("followed", _("someone follows me")),
        ("favorited", _("someone marks something of mine as a favorite")),
        ("amplified", _("someone amplifies something of mine")),
        ("replied", _("someone replies to my comment")),
    )
    # Being sent a sound is like being added to a project: the same switch turns both off.
    PREFERENCE_OF = {"included": "decided", "alternative": "decided", "mentioned": "commented",
                     "shared": "member_added"}

    recipient = models.ForeignKey(User, related_name="notifications", on_delete=models.CASCADE)
    actor = models.ForeignKey(User, related_name="+", null=True, on_delete=models.CASCADE)
    kind = models.CharField(max_length=30)
    target_name = models.CharField(max_length=200, blank=True)
    url = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def unread(self):
        return self.read_at is None


def notify(recipient, actor, kind, target_name="", url=""):
    """Leave a notification, unless it's your own action or you turned that kind off."""
    if recipient is None or recipient == actor or not recipient.is_active:
        return None
    profile = getattr(recipient, "userprofile", None)
    preference = Notification.PREFERENCE_OF.get(kind, kind)
    if profile is not None and preference in (profile.notify_off or []):
        return None
    return Notification.objects.create(recipient=recipient, actor=actor, kind=kind,
                                       target_name=str(target_name)[:200], url=url[:300])


def notify_from_action(sender, instance, created, **kwargs):
    """Turn what happens on the site (actions) into notifications for the people it concerns."""
    if not created:
        return
    actor, verb = instance.actor, instance.verb
    obj, target = instance.action_object, instance.target
    if verb == "contributed" and target is not None:
        notify(target.user, actor, "contributed", target.name, obj.get_absolute_url() if obj else target.get_absolute_url())
    elif verb == "commented" and obj is not None:
        about = obj.content_object
        name = getattr(about, "name", "") if about is not None else ""
        url = obj.get_absolute_url()
        if about is None:
            # A general post (or a reply to one): it lives on its author's profile.
            name = (obj.parent.msg if obj.parent_id else obj.msg)[:60]
        owner = about if isinstance(about, User) else getattr(about, "user", None)
        notify(owner, actor, "commented", name, url)
        # Read from the text: the message stores its mentions only after this signal runs.
        for person in Message.extract_mentioned_users(obj.msg):
            if person == owner:
                continue
            # Nobody hears about a project they can't listen to, not even its name.
            if isinstance(about, Project) and not Project.objects.listenable_by(person).filter(pk=about.pk).exists():
                continue
            if isinstance(about, Audio) and not Audio.objects.visible_to(person).filter(pk=about.pk).exists():
                continue
            notify(person, actor, "mentioned", name, url)
    elif verb == "access_requested" and target is not None:
        notify(target.user, actor, "access_requested", target.name, target.get_absolute_url() + "#solicitudes")
    elif verb == "member_added" and obj is not None and target is not None:
        notify(obj.user, actor, "member_added", target.name, target.get_absolute_url())
    elif verb == "used_as_source" and target is not None and obj is not None:
        notify(target.user, actor, "used_as_source", target.name, obj.get_absolute_url())
    elif verb == "version_saved" and obj is not None and target is not None:
        people = {c.contributor for c in obj.contributions.select_related("contributor")}
        for person in people:
            notify(person, actor, "version_saved", target.name, obj.get_absolute_url())


def visible_messages(queryset, user):
    """Leave out hidden comments, replies to hidden comments, and comments on works or sounds this
    person can't listen to. Every page, feed, API and index that lists comments goes through here."""
    allowed_projects = Project.objects.listenable_by(user).values("pk")
    allowed_audios = Audio.objects.visible_to(user).values("pk")
    ct_project = ContentType.objects.get_for_model(Project)
    ct_audio = ContentType.objects.get_for_model(Audio)
    # Keep only targets this person can hear (deleted ones are not in the allowed set), plus
    # general posts and other content types. Written as an allow-list so NULL content_type works.
    visible = (Q(content_type=ct_project, object_id__in=allowed_projects)
               | Q(content_type=ct_audio, object_id__in=allowed_audios)
               | Q(content_type__isnull=True)
               | ~Q(content_type__in=[ct_project, ct_audio]))
    return (queryset.filter(visible)
            .exclude(moderation_hidden=True)
            .exclude(parent__moderation_hidden=True))

post_save.connect(message_created_signal, sender=Message, dispatch_uid="message_created_signal")

from actstream.models import Action  # noqa: E402  (actstream is loaded before this app)
post_save.connect(notify_from_action, sender=Action, dispatch_uid="notify_from_action")
