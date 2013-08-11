from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.db.models.signals import post_save

from taggit.managers import TaggableManager

class Message(models.Model):
    msg = models.TextField(verbose_name=_('message'))
    user = models.ForeignKey(User, verbose_name=_('user'), editable=False)
    created_at = models.DateTimeField(verbose_name=_('created at'), auto_now_add=True)
    tags = TaggableManager(verbose_name=_('hashtags'), blank=True)
    mentioned_users = models.ManyToManyField(User, verbose_name=_('hashtags'), blank=True,
                                           null=True, editable=False,
                                           related_name="mentioned_users")
    content_type = models.ForeignKey(ContentType, null=True, editable=False)
    object_id = models.PositiveIntegerField(null=True, editable=False)
    content_object = generic.GenericForeignKey('content_type', 'object_id')

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


def message_created_signal(sender, instance, created, **kwargs):
    if created:
        action.send(instance.user, verb=_('commented'), action_object=instance)

post_save.connect(message_created_signal, sender=Message, dispatch_uid="message_created_signal")
