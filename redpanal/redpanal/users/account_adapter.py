import re
from django import forms

from django.utils.translation import ugettext_lazy as _
from allauth.account.adapter import DefaultAccountAdapter

USERNAME_REGEX = re.compile(r'^[\w.+-]+$')  # same as UserCreationForm regex but without '@'


class MyAccountAdapter(DefaultAccountAdapter):

    def clean_username(self, username):
        username = super(MyAccountAdapter, self).clean_username(username)
        if not USERNAME_REGEX.match(username):
            raise forms.ValidationError(_("Usernames can only contain "
                                          "letters, digits and ./+/-/_."))

        if not (3 <= len(username) <= 15):
            raise forms.ValidationError(_("Username length must be between 3 and 15 chars"))

        return username