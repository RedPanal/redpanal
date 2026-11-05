from django import forms
from django.utils.translation import gettext_lazy as _
from allauth.account.adapter import DefaultAccountAdapter

from .reserved import is_reserved


class MyAccountAdapter(DefaultAccountAdapter):

    def clean_username(self, username, shallow=False):
        username = super().clean_username(username, shallow=shallow)
        # Profiles live at redpanal.org/<username>/: a page's name can't be taken.
        if is_reserved(username):
            raise forms.ValidationError(_("That name is taken by a page of RedPanal. Try another."))
        return username
