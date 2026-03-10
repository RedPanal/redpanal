from django import forms
from django.utils.translation import gettext as _

from taggit.utils import parse_tags, edit_string_for_tags

from django.contrib.auth.forms import AuthenticationForm, UsernameField

class TagParseError(Exception):
    pass

def tags_to_editable_string(tags):
    return u' '.join([u"#%s" % t for t in tags])

def parse_tags(string):
    tags = string.split()
    for tag in tags:
        if not tag.startswith('#'):
            raise TagParseError(_("Tag '%s' does not start with #" % tag))
    return [tag[1:] for tag in tags if len(tag) > 1]

class TagWidget(forms.TextInput):
    def render(self, name, value, attrs=None, renderer=None):
        if value and not isinstance(value, str):
            value = tags_to_editable_string([o.name for o in value])
        else:
            value = ""
        return super(TagWidget, self).render(name, value, attrs)

class TagField(forms.CharField):
    widget = TagWidget
    help_text = "asdasd"

    def clean(self, value):
        value = super(TagField, self).clean(value)
        try:
            return parse_tags(value)
        except TagParseError as e:
            raise forms.ValidationError(str(e))

# custom login form

class RPLoginForm(AuthenticationForm):
   def __init__(self, *args, **kwargs):
      super(RPLoginForm, self).__init__(*args, **kwargs)

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

