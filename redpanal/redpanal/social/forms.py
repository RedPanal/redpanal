# -*- coding: utf-8 -*-
from django import forms


class MessageForm(forms.Form):

    msg = forms.CharField(max_length=140)
