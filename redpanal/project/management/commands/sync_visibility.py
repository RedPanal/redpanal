"""Recompute the `public` flag of every stored action from the current visibility rules.

Older code marked comments on private or hidden sounds as public and could republish what
moderation hid. Pages and the API now check each action when they read it, but the stored
flag is also fixed here so nothing stale is left behind. Safe to run more than once.
"""
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Recompute the public flag of feed actions from the current visibility of what they talk about."

    def handle(self, *args, **options):
        from actstream.models import Action
        from audio.models import Audio
        from project.models import Project, sync_action_visibility
        from social.models import Message, sync_message_actions

        projects = 0
        for project in Project.objects.iterator():
            sync_action_visibility(project)
            projects += 1
        # Comments on sounds outside any work, and general posts.
        sync_message_actions(Message.objects.filter(parent__isnull=True).exclude(
            content_type=ContentType.objects.get_for_model(Project)))
        ct_audio = ContentType.objects.get_for_model(Audio)
        public_sounds = {str(pk) for pk in Audio.objects.visible_to(None).values_list("pk", flat=True)}
        stale = [a.pk for a in Action.objects.filter(public=True, verb="audio_created",
                                                     action_object_content_type=ct_audio)
                 if a.action_object_object_id not in public_sounds]
        Action.objects.filter(pk__in=stale).update(public=False)
        self.stdout.write("Synced %d works; %d sound announcements made private." % (projects, len(stale)))
