from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe
from django.db.models.signals import post_save
from django.core.urlresolvers import reverse

from actstream import action
from taggit.managers import TaggableManager
from taggit.models import Tag

from redpanal.audio.models import Audio
from redpanal.project.models import Project


class Message(models.Model):
    msg = models.TextField(verbose_name=_('message'))
    user = models.ForeignKey(User, verbose_name=_('user'), editable=False)
    created_at = models.DateTimeField(verbose_name=_('created at'), auto_now_add=True)
    tags = TaggableManager(verbose_name=_('hashtags'), blank=True)
    mentioned_users = models.ManyToManyField(User, verbose_name=_('hashtags'), blank=True,
                                           null=True, editable=False,
                                           related_name="mentioned_messages")
    content_type = models.ForeignKey(ContentType, null=True, editable=False)
    object_id = models.PositiveIntegerField(null=True, editable=False)
    content_object = generic.GenericForeignKey('content_type', 'object_id')
    _msg_html_cache = models.TextField(editable=False, blank=True, null=True)

    def __unicode__(self):
        return mark_safe(self.as_html())

    def as_html(self):
        if not self._msg_html_cache:
            self._msg_html_cache = Message.to_html(self.msg)
            self.save()
        return self._msg_html_cache

    @staticmethod
    def to_html(msg):
        import re
        USER_REGEX = re.compile(r'@(\w+)')
        HASHTAG_REGEX = re.compile(r'#(\w+)')
        # ToDo: deberia obtenerse el dominio del sitio de forma dinamica?
        OBJECTS_URL_REGEX = re.compile(r'(https?://)(grafiks\.info:8080)/([p|a])/([0-9a-zA-Z_-]+)/?') #beta\.redpanal\.org
        URL_REGEX = re.compile(r'(https?://)(www\.)?(\S+)')
        
        def replace_user(match):
            if match:
                username = match.group(1)
                try:
                    user = User.objects.get(username=username)
                except User.DoesNotExist:
                    return match.group()
                return '<a href="%s">@%s</a>' % (user.get_absolute_url(), username)

        def replace_hashtags(match):
            if match:
                tag = match.group(1)
                try:
                    tagobj = Tag.objects.get(name=tag)
                except Tag.DoesNotExist:
                    return match.group()
                return '<a href="%s">#%s</a>' % (reverse("hashtaged-list", None, (tagobj.slug,)), tag)

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
                return '<a href="%s"><i class="fa alias-%s"></i>%s</a>' % (obj.get_absolute_url(), obj._meta.verbose_name, text)

        def replace_urls(match):
            if match:
                url = match.group(0)               
                text = match.group(3)[:25] + (match.group(3)[25:] and '..')
                return '<a href="%s" target="_blank">%s</a>' % (url, text)

        msg = msg.replace("\n", "<br>")
        html = re.sub(USER_REGEX, replace_user, msg)
        html = re.sub(HASHTAG_REGEX, replace_hashtags, html)
        html = re.sub(OBJECTS_URL_REGEX, replace_objects_urls, html)
        html = re.sub(URL_REGEX, replace_urls, html)
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
