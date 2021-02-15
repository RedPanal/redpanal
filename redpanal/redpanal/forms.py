import random
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from allauth.account.forms import SignupForm


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

    def validate(self, value):
        super().validate(value)
        if value.lower() != self.answer.lower():
            raise ValidationError("Invalid answer")

class CustomSignupForm(SignupForm):
    music_trivia = MusicTriviaField(max_length=30)
