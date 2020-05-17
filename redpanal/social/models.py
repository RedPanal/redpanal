import re

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe
from django.db.models.signals import post_save
from django.urls import reverse
from django.contrib.sites.models import Site
from django.utils.html import strip_tags

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
    _msg_html_cache = models.TextField(editable=False, blank=True, null=True)

    def __str__(self):
        return mark_safe(self.as_html())

    def as_html(self):
        if not self._msg_html_cache:
            self._msg_html_cache = Message.to_html(self.msg)
            self.save()
        return self._msg_html_cache

    @staticmethod
    def to_html(msg):
        USER_REGEX = re.compile(r'@([\w-]+)')
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
                new = '<a href="%s">@%s</a>' % (user.get_absolute_url(), username)
                return get_and_store_hash(new)

        def replace_hashtags(match):
            if match:
                tag = match.group(1)
                try:
                    tagobj = Tag.objects.get(name=tag)
                except Tag.DoesNotExist:
                    return match.group()
                new = '<a href="%s">#%s</a>' % (tagobj.get_absolute_url(), tag)
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
                text = obj.name[:25] + (obj.name[25:] and '..')
                new = '<a href="%s"><i class="fa alias-%s"></i>%s</a>' % (obj.get_absolute_url(), obj._meta.verbose_name, text)
                return get_and_store_hash(new)

        def replace_urls(match):
            if match:
                url = match.group(0)
                text = match.group(3)[:25] + (match.group(3)[25:] and '..')
                new = '<a href="%s" target="_blank">%s</a>' % (url, text)
                return get_and_store_hash(new)

        # Replace strings for hashes and save the new html in context
        html = re.sub(USER_REGEX, replace_user, msg)
        html = re.sub(HASHTAG_REGEX, replace_hashtags, html)
        html = re.sub(OBJECTS_URL_REGEX, replace_objects_urls, html)
        html = re.sub(URL_REGEX, replace_urls, html)

        # Remove all html tags
        html = strip_tags(html)

        # Replace the hashes with our versions of the html
        for rep_hash, new_html in html_replaces:
            html = html.replace(rep_hash, new_html)

        html = html.replace("\n", "<br>")
        return html

    @staticmethod
    def extract_mentioned_users(msg):
        """Returns a list of users that are mentioned with @userfoo @UserBar"""
        words = msg.split()
        users = filter(lambda word: word.startswith('@'), words)
        users = [u[1:] for u in users]
        return User.objects.filter(username__in=users)

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

    class Meta:
        ordering = ['-created_at']

def message_created_signal(sender, instance, created, **kwargs):
    if created:
        action.send(instance.user, verb='commented', action_object=instance)

post_save.connect(message_created_signal, sender=Message, dispatch_uid="message_created_signal")
