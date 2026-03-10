# -*- coding: utf-8 -*-
from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from .models import Audio
from project.models import Project
from core.forms import TagField
from redpanal.utils.helpers import get_file_extension
from multiupload.fields import MultiFileField

AUDIO_EXTENSIONS = ["mp3", "ogg", "oga", "flac", "wav"]


class AudioEditForm(forms.ModelForm):
    ## Edit Audio Form

    tags = TagField(required=False)
    project = forms.ModelChoiceField(Project.objects.all(), required=False)
    audio = forms.FileField(label=_("Audio"), help_text=_("Allowed extensions: %s") % ", ".join(AUDIO_EXTENSIONS))

    helper = FormHelper()
    # helper.form_class = 'form-horizontal'
    helper.add_input(Submit('submit', 'Submit'))
    class Meta:
        model = Audio
        widgets = {
            'license': forms.RadioSelect,
        }
        fields = '__all__'

    def __init__(self, data=None, *args, **kwargs):
        user = kwargs.pop('user')
        super(AudioEditForm, self).__init__(data, *args, **kwargs)
        self.instance.user = user
        initial_project = self.instance.project_set.all()[0] if self.instance.pk and \
                         self.instance.project_set.all() else None
        self.fields['project'] = forms.ModelChoiceField(queryset=Project.objects.filter(user=user),
                                                        initial=initial_project, required=False)

    def clean_audio(self):
        f = self.cleaned_data.get('audio', False)
        if not f:
            raise ValidationError(_("Couldn't read uploaded file"))
        if not get_file_extension(f.name) in AUDIO_EXTENSIONS:
            raise ValidationError(_("Invalid audio file extension"))
        return f

class AudioUploadForm(forms.ModelForm):
    #Upload Form

    audio = MultiFileField(
        label=_("Audio"), 
        help_text=_("Allowed extensions: %s") % ", ".join(AUDIO_EXTENSIONS))

    helper = FormHelper()
    helper.form_class = 'form-horizontal'
    helper.add_input(Submit('submit', 'Submit'))
    class Meta:
        model = Audio
        widgets = {
            'license': forms.RadioSelect,
        }
        fields = []
        enctype = "multipart/form-data"

    def __init__(self, data=None, *args, **kwargs):
        user = kwargs.pop('user')
        super(AudioUploadForm, self).__init__(data, *args, **kwargs)
        self.instance.user = user

    def clean_audio(self):
        files = self.cleaned_data.get('audio', False)
        for f in files:
            if not f:
                raise ValidationError(_("Couldn't read uploaded file"))
            if not get_file_extension(f.name) in AUDIO_EXTENSIONS:
                raise ValidationError(_("Invalid audio file extension"))
