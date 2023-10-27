import random
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from allauth.account.forms import SignupForm, LoginForm


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

class CustomSignupForm(SignupForm):
    #music_trivia = MusicTriviaField(max_length=30)
    #music_trivia.widget.attrs.update({"class": "form-control"}) #https://docs.djangoproject.com/en/4.2/ref/forms/widgets/
    def __init__(self, *args, **kwargs):
        super(CustomSignupForm, self).__init__(*args, **kwargs)
        self.fields['username'].widget = forms.TextInput(attrs={'class': 'form-control'})
        self.fields['email'].widget = forms.TextInput(attrs={'class': 'form-control'})
        self.fields['password1'].widget = forms.PasswordInput(attrs={'class': 'form-control'})
        self.fields['password2'].widget = forms.PasswordInput(attrs={'class': 'form-control'})

class CustomLoginForm(LoginForm):
    def __init__(self, *args, **kwargs):
        super(CustomLoginForm, self).__init__(*args, **kwargs)
        self.fields['login'].widget = forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Juan'})
        self.fields['password'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    
"""
class CustomLoginForm(AuthenticationForm):
   def __init__(self, *args, **kwargs):
      super(CustomLoginForm, self).__init__(*args, **kwargs)

   username = UsernameField(widget=forms.TextInput(
      attrs={
      'class': 'form-control',
      'placeholder': _("Username"),
      'id': 'id_login',
   }))
   password = forms.CharField(widget=forms.PasswordInput(
      attrs={
      'class': 'form-control',
      'placeholder': _("Password"),
      'id': 'id_password',
   }))
"""
