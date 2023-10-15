from django.forms import ModelForm
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from .models import UserProfile
from core.forms import TagField


class UserProfileForm(ModelForm):
    tags =  TagField(label=_('hashtags').capitalize(), required=False, 
                     help_text=_("put tags helps you to contact users who share musical tastes"))


    helper = FormHelper()
    helper.add_input(Submit('submit', 'Submit'))

    class Meta:
        model = UserProfile
        fields = ['realname', 'about', 'website', 'location']
        fieldsets = (
           (None, {'fields': ('tags',)}),
        )
