from __future__ import unicode_literals
from django.apps import AppConfig

class ProjectConfig(AppConfig):

    name = 'project'

    def ready(self):
        from actstream import registry
        registry.register(self.get_model('Project'))
