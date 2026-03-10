# -*- coding: utf-8 -*-
from django import forms
from django.contrib.contenttypes.models import ContentType


class MessageForm(forms.Form):

    msg = forms.CharField(max_length=1000)


class MessageWithContentForm(forms.Form):

    msg = forms.CharField(max_length=1000)
    content_type = forms.ModelChoiceField(queryset=ContentType.objects.all(),
                                          widget=forms.HiddenInput())
    object_id = forms.IntegerField(widget=forms.HiddenInput())

