import random
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class MusicTriviaField(forms.CharField):
    text = _("Trivia, write the incomplete word: ")
    trivias = [
        ('Carlos Gar..l', 'Gardel'),
        ('Indio So...i', 'Solari'),
        ('Caetano Ve..s.', 'Veloso'),
        ('Bowie Da..d', 'David'),
        ('Jimi He...ix', 'Hendrix'),
        ('Freddie Merc...', 'Mercury'),
    ]
    def __init__(self, *args, **kwargs):
        super(MusicTriviaField, self).__init__(*args,**kwargs)
        self.question, self.answer = random.choice(self.trivias)
        self.label = self.text + self.question
        self.attrs = { 'class': 'form-control', }

    def validate(self, value):
        super().validate(value)
        if value.lower() != self.answer.lower():
            raise ValidationError("Invalid answer")


class CustomSignupForm(forms.Form):
    """
    Extra signup form for allauth 65.x.
    In this version, ACCOUNT_SIGNUP_FORM_CLASS must be a plain Form
    that provides extra fields. Widget styling is handled via templates.
    """
    def signup(self, request, user):
        pass
