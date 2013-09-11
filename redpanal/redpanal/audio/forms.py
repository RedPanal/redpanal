# -*- coding: utf-8 -*-
from django import forms
from django.utils.translation import ugettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from models import Audio
from redpanal.project.models import Project
from redpanal.core.forms import TagField

class AudioForm(forms.ModelForm):

    tags =  TagField(required=False)
    project = forms.ModelChoiceField(Project)

    helper = FormHelper()
    helper.add_input(Submit('submit', 'Submit'))
    class Meta:
        model = Audio

    def __init__(self, data=None, *args, **kwargs):
        user = kwargs.pop('user')
        super(AudioForm, self).__init__(data, *args, **kwargs)
        self.instance.user = user
        initial_project = self.instance.project_set.all()[0] if self.instance.pk else None
        self.fields['project'] = forms.ModelChoiceField(queryset=Project.objects.filter(user=user),
                                                        initial=initial_project)
