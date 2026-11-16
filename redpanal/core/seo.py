"""What search engines and link previews read about each page: a title that starts with the content, a description
made from the data, and schema.org data. Built from the objects, so every page has them without anyone writing them."""
import json

from django.templatetags.static import static
from django.utils.html import strip_tags
from django.utils.text import Truncator
from django.utils.translation import gettext as _

from core import licenses

DESCRIPTION_MAX = 160


def _clip(text, n=DESCRIPTION_MAX):
    return Truncator(" ".join(strip_tags(text or "").split())).chars(n)


def _license_url(code):
    lic = licenses.LICENSES.get(code) or licenses.DEFAULT_LICENSE
    return str(lic.url)


def _duration(ms):
    """ISO 8601, as schema.org wants it: PT1M23S."""
    if not ms:
        return None
    total = int(round(ms / 1000))
    minutes, seconds = divmod(total, 60)
    return "PT%dM%dS" % (minutes, seconds) if minutes else "PT%dS" % seconds


def _person(user, request):
    from project.templatetags.obra_tags import display_name
    return {"@type": "Person", "name": display_name(user), "url": request.build_absolute_uri(user.get_absolute_url())}


def _image(request, field):
    return request.build_absolute_uri(field.url) if field else None


# -- sounds --------------------------------------------------------------------------------------

def audio_kind(audio):
    """«loop of synthesizer, 92 BPM, A minor»: what the sound is, in a few words."""
    kind = audio.get_use_type_display() if audio.use_type else _("sound")
    if audio.instrument:
        kind = _("%(kind)s of %(instrument)s") % {"kind": kind, "instrument": audio.get_instrument_display()}
    parts = [kind]
    if audio.tempo:
        parts.append("%d BPM" % audio.tempo)
    if audio.musical_key:
        parts.append(audio.musical_key)
    return ", ".join(parts)


def audio_title(audio):
    return "%s · %s" % (audio.name, audio_kind(audio))


def audio_description(audio):
    from project.templatetags.obra_tags import display_name
    if audio.description:
        lead = audio.description
    else:
        kind = audio_kind(audio)
        lead = _("%(what)s by %(who)s.") % {"what": kind[:1].upper() + kind[1:], "who": display_name(audio.user)}
    return _clip(lead + " " + _("Free license: listen to it, download it and use it in your projects."))


def audio_data(audio, request):
    data = {
        "@context": "https://schema.org", "@type": "MusicRecording",
        "name": audio.name, "url": request.build_absolute_uri(audio.get_absolute_url()),
        "description": audio_description(audio), "byArtist": _person(audio.user, request),
        "license": _license_url(audio.license), "datePublished": audio.created_at.date().isoformat(),
        "duration": _duration(audio.get_duration()), "image": _image(request, audio.image),
        "genre": audio.get_genre_display() if audio.genre else None,
        "keywords": ", ".join(audio.tags.names()) or None,
        "audio": {"@type": "AudioObject", "contentUrl": request.build_absolute_uri(audio.get_stream_url())},
    }
    return {k: v for k, v in data.items() if v}


# -- projects ------------------------------------------------------------------------------------

def project_description(project):
    from project.templatetags.obra_tags import display_name
    if project.description:
        lead = project.description
    else:
        people = [display_name(c["user"]) for c in project.credits()]
        who = ", ".join(people[:4]) or display_name(project.user)
        lead = _("A project by %(who)s on RedPanal, made in layers.") % {"who": who}
    return _clip(lead + " " + _("Listen to it and add your own layer."))


def project_data(project, request):
    composers = [project.user] + [c["user"] for c in project.credits() if c["user"] != project.user]
    data = {
        "@context": "https://schema.org", "@type": "MusicComposition",
        "name": project.name, "url": request.build_absolute_uri(project.get_absolute_url()),
        "description": project_description(project),
        "composer": [_person(u, request) for u in composers[:10]],
        "license": _license_url(project.license), "dateCreated": project.created_at.date().isoformat(),
        "musicalKey": project.musical_key or None, "image": _image(request, project.image),
        "keywords": ", ".join(project.tags.names()) or None,
    }
    return {k: v for k, v in data.items() if v}


# -- people --------------------------------------------------------------------------------------

def person_description(person):
    from project.templatetags.obra_tags import display_name
    profile = getattr(person, "userprofile", None)
    about = getattr(profile, "about", "") or ""
    if about:
        return _clip(about)
    from audio.models import INSTRUMENT_CHOICES
    names = dict(INSTRUMENT_CHOICES)
    plays = [str(names.get(i, i)) for i in (getattr(profile, "instruments", None) or [])][:4]
    lead = _("%(who)s on RedPanal.") % {"who": display_name(person)}
    if plays:
        lead += " " + _("Plays %(what)s.") % {"what": ", ".join(plays)}
    return _clip(lead + " " + _("Listen to their projects and sounds, under free licenses."))


def person_data(person, request, avatar_url=""):
    from project.templatetags.obra_tags import display_name
    data = {"@type": "Person", "name": display_name(person), "alternateName": "@" + person.username,
            "url": request.build_absolute_uri(person.get_absolute_url()),
            "description": person_description(person),
            "image": request.build_absolute_uri(avatar_url) if avatar_url else None}
    return {"@context": "https://schema.org", "@type": "ProfilePage",
            "mainEntity": {k: v for k, v in data.items() if v}}


# -- the site ------------------------------------------------------------------------------------

def site_data(request):
    from django.urls import reverse
    home = request.build_absolute_uri("/")
    return [
        {"@context": "https://schema.org", "@type": "WebSite", "name": "RedPanal", "url": home,
         "potentialAction": {"@type": "SearchAction",
                             "target": request.build_absolute_uri(reverse("explore")) + "?q={search_term_string}",
                             "query-input": "required name=search_term_string"}},
        {"@context": "https://schema.org", "@type": "Organization", "name": "RedPanal", "url": home,
         "logo": request.build_absolute_uri(static("img/icon-512.png"))},
    ]


def as_json_ld(data):
    """Safe inside <script>: no "</script>" can close it early."""
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
