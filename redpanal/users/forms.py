from django import forms
from django.forms import ModelForm
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from .models import UserProfile
from audio.models import INSTRUMENT_CHOICES
from core.forms import TagField


class UserProfileForm(ModelForm):
    tags =  TagField(label=_('hashtags').capitalize(), required=False,
                     help_text=_("put tags helps you to contact users who share musical tastes"))
    instruments = forms.MultipleChoiceField(
        label=_("instruments you play"), required=False,
        choices=[c for c in INSTRUMENT_CHOICES if c[0] not in ("multiple", "other")],
        widget=forms.CheckboxSelectMultiple,
        help_text=_("we use them to show you works that are looking for those parts"))


    helper = FormHelper()
    helper.add_input(Submit('submit', 'Submit'))

    class Meta:
        model = UserProfile
        fields = ['realname', 'about', 'website', 'location', 'instruments',
                  'cover', 'open_to_collaborate', 'genres', 'tools', 'other_link']
        fieldsets = (
           (None, {'fields': ('tags',)}),
        )


class DeleteUserForm(forms.Form):
    delete = forms.BooleanField(initial=False)

    helper = FormHelper()
    helper.add_input(Submit('submit', 'Submit', css_class='btn-primary'))
    helper.form_method = 'POST'
