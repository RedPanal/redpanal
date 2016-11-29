# -*- coding: utf-8 -*-
from django import forms
from django.utils.translation import ugettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from core.forms import TagField
from models import Project

class ProjectForm(forms.ModelForm):

    helper = FormHelper()
    helper.add_input(Submit('submit', 'Submit'))
    helper.form_class = 'form-horizontal'

    tags =  TagField()

    class Meta:
        model = Project
        exclude = ("audios", )

