from __future__ import unicode_literals
from django.apps import AppConfig
from django.apps import apps as django_apps

class UsersConfig(AppConfig):

    name = 'users'

    def ready(self):
        from actstream import registry
        registry.register(django_apps.get_model('auth', 'User'))
