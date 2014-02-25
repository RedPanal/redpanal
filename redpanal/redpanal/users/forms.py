from django.forms import ModelForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from models import UserProfile
from redpanal.core.forms import TagField

class UserProfileForm(ModelForm):
    tags =  TagField(required=False)


    helper = FormHelper()
    helper.add_input(Submit('submit', 'Submit'))

    class Meta:
        model = UserProfile
        fields = ['about', 'location']
