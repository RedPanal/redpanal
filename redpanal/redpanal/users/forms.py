from django.forms import ModelForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from models import UserProfile

class UserProfileForm(ModelForm):
    helper = FormHelper()
    helper.add_input(Submit('submit', 'Submit'))

    class Meta:
        model = UserProfile
        fields = ['about', 'location']
