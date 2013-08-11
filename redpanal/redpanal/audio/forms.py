# -*- coding: utf-8 -*-
from django import forms
from django.utils.translation import ugettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from models import Audio
from redpanal.core.forms import TagField

class AudioForm(forms.ModelForm):

    helper = FormHelper()
    helper.add_input(Submit('submit', 'Submit'))
    tags =  TagField()
    class Meta:
        model = Audio
