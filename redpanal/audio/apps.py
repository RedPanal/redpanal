from __future__ import unicode_literals
from django.apps import AppConfig

class AudioConfig(AppConfig):

    name = 'audio'

    def ready(self):
        from actstream import registry
        registry.register(self.get_model('Audio'))
