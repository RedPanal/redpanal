"""Before moving profiles to the root: people whose name is the name of a page.

    python manage.py check_usernames

Exact matches can't be reached at /<username>/ (the page wins) and have to be renamed; names that differ only in
capitals do work, but are listed to look at."""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from users.reserved import reserved_usernames, route_names


class Command(BaseCommand):
    help = "Lists people whose username collides with a page of the site."

    def handle(self, *args, **options):
        routes = route_names()
        reserved = reserved_usernames()
        hidden, similar = [], []
        for user in User.objects.only("username", "date_joined").order_by("username"):
            if user.username in routes:
                hidden.append(user)
            elif user.username.lower() in reserved:
                similar.append(user)
        for user in hidden:
            self.stdout.write(self.style.ERROR("Hidden by a page: %s (since %s)" % (user.username, user.date_joined.date())))
        for user in similar:
            self.stdout.write(self.style.WARNING("Reserved name, still reachable: %s" % user.username))
        if not hidden and not similar:
            self.stdout.write(self.style.SUCCESS("No username collides with a page."))
