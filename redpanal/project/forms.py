# -*- coding: utf-8 -*-
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from core.forms import TagField
from audio.models import INSTRUMENT_CHOICES
from audio.uploads import ACCEPTED_EXTENSIONS
from redpanal.utils.helpers import get_file_extension
from .models import Project, PartRequest, STATUS_CHOICES, VISIBILITY_CHOICES, VISIBILITY_PUBLIC

REQUEST_INSTRUMENTS = [c for c in INSTRUMENT_CHOICES if c[0] != "multiple"]
MAX_AUDIO_MB = 200


class ProjectForm(forms.ModelForm):

    helper = FormHelper()
    helper.add_input(Submit('submit', 'Submit'))
    # helper.form_class = 'form-horizontal'

    tags =  TagField(required=False)

    class Meta:
        model = Project
        # Visibility is changed from the work's access panel (Project.set_visibility).
        fields = ("name", "description", "tempo", "musical_key", "image", "tags")


def clean_audio_upload(f):
    if not f:
        raise ValidationError(_("Couldn't read uploaded file"))
    if get_file_extension(f.name) not in ACCEPTED_EXTENSIONS:
        raise ValidationError(_("Invalid audio file extension"))
    if f.size > MAX_AUDIO_MB * 1024 * 1024:
        raise ValidationError(_("The file is too big (maximum %d MB)") % MAX_AUDIO_MB)
    return f


def suggested_sources(user, days=30):
    """Sounds this person downloaded lately and can still listen to: likely sources."""
    from datetime import timedelta
    from django.utils import timezone
    from audio.models import Audio
    if user is None or not user.is_authenticated:
        return Audio.objects.none()
    since = timezone.now() - timedelta(days=days)
    return (Audio.objects.visible_to(user)
            .filter(downloads__user=user, downloads__created_at__gte=since)
            .exclude(user=user).select_related("user").order_by("-downloads__created_at").distinct())


class NewWorkForm(forms.Form):
    """Publish an idea: everything is prefilled, only the audio is required."""

    audio = forms.FileField(label=_("Audio"))
    trim_start_ms = forms.IntegerField(required=False, min_value=0, widget=forms.HiddenInput)
    trim_end_ms = forms.IntegerField(required=False, min_value=0, widget=forms.HiddenInput)
    name = forms.CharField(label=_("Title"), max_length=100)
    image = forms.ImageField(label=_("Image (optional)"), required=False)
    part_instrument = forms.ChoiceField(label=_("What is in this recording?"),
                                        choices=[("", "—")] + REQUEST_INSTRUMENTS, required=False,
                                        widget=forms.Select(attrs={"class": "form-select"}))
    missing = forms.MultipleChoiceField(label=_("What is it missing?"), choices=REQUEST_INSTRUMENTS,
                                        required=False, widget=forms.CheckboxSelectMultiple)
    missing_text = forms.CharField(label=_("Tell what you are looking for (optional)"),
                                   max_length=200, required=False,
                                   widget=forms.Textarea(attrs={"rows": 2}))
    visibility = forms.ChoiceField(label=_("Who can listen"), choices=VISIBILITY_CHOICES,
                                   widget=forms.RadioSelect)
    tempo = forms.IntegerField(label=_("Tempo (BPM)"), required=False, min_value=20, max_value=300)
    source = forms.ModelChoiceField(queryset=Project.objects.none(), required=False,
                                    widget=forms.HiddenInput)

    sources = forms.ModelMultipleChoiceField(queryset=None, required=False,
                                             widget=forms.CheckboxSelectMultiple,
                                             label=_("Sounds you used"))

    def __init__(self, *args, user=None, sound=None, **kwargs):
        super().__init__(*args, **kwargs)
        # A new work can only be based on a work this person can listen to.
        self.fields["source"].queryset = Project.objects.listenable_by(user)
        sources = suggested_sources(user)
        if sound is not None:  # "Use it in a new work" from a sound's page
            from audio.models import Audio
            sources = Audio.objects.filter(Q(pk__in=sources.values("pk")) | Q(pk=sound.pk)).select_related("user")
            self.initial.setdefault("sources", [sound.pk])
        self.fields["sources"].queryset = sources
        from .templatetags.obra_tags import display_name
        self.fields["sources"].label_from_instance = lambda a: "%s — %s" % (a.name, display_name(a.user))

    def clean_audio(self):
        return clean_audio_upload(self.cleaned_data.get("audio"))


class FolderWorkForm(forms.Form):
    """A new work from a studio folder: the stems arrive apart, as files."""

    name = forms.CharField(label=_("Title"), max_length=100)
    image = forms.ImageField(label=_("Image (optional)"), required=False)
    missing = forms.MultipleChoiceField(label=_("What is it missing?"), choices=REQUEST_INSTRUMENTS,
                                        required=False, widget=forms.CheckboxSelectMultiple)
    missing_text = forms.CharField(label=_("Tell what you are looking for (optional)"),
                                   max_length=200, required=False,
                                   widget=forms.Textarea(attrs={"rows": 2}))
    visibility = forms.ChoiceField(label=_("Who can listen"), choices=VISIBILITY_CHOICES,
                                   widget=forms.RadioSelect)
    tempo = forms.IntegerField(label=_("Tempo (BPM)"), required=False, min_value=20, max_value=300)


SOUND_TYPES = [("loop", _("loop")), ("sample", _("sample")), ("field", _("field recording")),
               ("other", _("other"))]


class SoundForm(forms.Form):
    """A loose sound for anyone to use: what Tincho filters by comes first."""

    audio = forms.FileField(label=_("Audio"))
    name = forms.CharField(label=_("Name"), max_length=100)
    image = forms.ImageField(label=_("Image (optional)"), required=False)
    use_type = forms.ChoiceField(label=_("Type"), choices=SOUND_TYPES, initial="loop", widget=forms.RadioSelect)
    instrument = forms.ChoiceField(label=_("Instrument"), choices=[("", "—")] + list(INSTRUMENT_CHOICES),
                                   required=False)
    tempo = forms.IntegerField(label=_("Tempo (BPM)"), required=False, min_value=20, max_value=300)
    musical_key = forms.CharField(label=_("Key"), max_length=20, required=False)
    description = forms.CharField(label=_("Description (optional)"), required=False,
                                  widget=forms.Textarea(attrs={"rows": 2}))

    def clean_audio(self):
        return clean_audio_upload(self.cleaned_data.get("audio"))


class ContributionForm(forms.Form):
    """Sumar una pista: the file (recorded while listening, or chosen) and, optionally, a note.

    The instrument comes from the collaboration answered, the person's profile or the file name;
    the offset only from recording over the work; the license is the work's, by default.
    """
    audio = forms.FileField(label=_("Your part"))
    instrument = forms.ChoiceField(label=_("Instrument"), choices=[("", "")] + list(REQUEST_INSTRUMENTS), required=False)
    request = forms.ModelChoiceField(queryset=PartRequest.objects.none(), required=False,
                                     label=_("Request"), empty_label=_("None in particular"))
    offset_ms = forms.IntegerField(label=_("Offset (ms)"), initial=0, required=False,
                                   min_value=-600000, max_value=600000)
    note = forms.CharField(label=_("Note for the author (optional)"), max_length=500,
                           required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, project=None, is_owner=False, **kwargs):
        super().__init__(*args, **kwargs)
        if project is not None:
            self.fields["request"].queryset = project.open_requests()

    def clean_audio(self):
        return clean_audio_upload(self.cleaned_data.get("audio"))


class PartRequestForm(forms.ModelForm):
    class Meta:
        model = PartRequest
        fields = ("instrument", "description", "open_until")
        widgets = {"instrument": forms.Select(choices=REQUEST_INSTRUMENTS),
                   "open_until": forms.DateInput(attrs={"type": "date"})}


class CommentForm(forms.Form):
    msg = forms.CharField(label=_("Comment"), max_length=1000)
    at_ms = forms.IntegerField(required=False, min_value=0, widget=forms.HiddenInput)


class VisibilityForm(forms.Form):
    visibility = forms.ChoiceField(label=_("Who can listen"), choices=VISIBILITY_CHOICES,
                                   widget=forms.RadioSelect)
    preview_start_s = forms.IntegerField(label=_("The preview starts at (seconds)"), required=False,
                                         min_value=0, max_value=3600)
    confirm_public = forms.BooleanField(required=False)
    allow_downloads = forms.BooleanField(required=False, label=_("People with access can download the parts"))
    preview_watermark = forms.BooleanField(required=False, label=_("Add a sound mark to the preview"))

    def __init__(self, *args, already_public=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.already_public = already_public

    def clean(self):
        data = super().clean()
        # Publishing asks for confirmation; saving other settings of a public work doesn't.
        if (data.get("visibility") == VISIBILITY_PUBLIC and not self.already_public
                and not data.get("confirm_public")):
            raise ValidationError(_("Confirm that you want to publish the work."))
        return data


class InviteForm(forms.Form):
    username = forms.CharField(label=_("Username"), max_length=150)

    def clean_username(self):
        from django.contrib.auth.models import User
        name = self.cleaned_data["username"].strip().lstrip("@")
        user = User.objects.filter(username__iexact=name).first()
        if user is None:
            raise ValidationError(_("There is nobody called @%s in RedPanal.") % name)
        return user


class AccessRequestForm(forms.Form):
    message = forms.CharField(label=_("Tell who you are and what you would bring (optional)"),
                              max_length=300, required=False, widget=forms.Textarea(attrs={"rows": 2}))


class VersionForm(forms.Form):
    message = forms.CharField(label=_("Message for the people who contributed (optional)"),
                              max_length=500, required=False,
                              widget=forms.Textarea(attrs={"rows": 2}))
