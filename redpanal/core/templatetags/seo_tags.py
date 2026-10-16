"""The <head> of each page for search engines and link previews (core/seo.py builds the content).

    {% seo_meta %}                       the defaults, in base.html
    {% seo_meta title=... description=... noindex=True %}
    {% seo_audio object %} / {% seo_project object %} / {% seo_person person %} / {% seo_site %}
"""
from django import template
from django.templatetags.static import static
from django.utils.safestring import mark_safe
from django.utils.translation import get_language, gettext as _

from core import seo

register = template.Library()

OG_LOCALES = {"es": "es_AR", "en": "en_US", "pt": "pt_BR"}


def _context(context, title=None, description=None, image=None, kind="website", noindex=False, data=None):
    request = context.get("request")
    if request is None:
        return {}
    if data is not None and not isinstance(data, list):
        data = [data]
    return {
        "title": title or "RedPanal",
        "description": description or _("Free music community: share ideas, add layers to other people's projects "
                                        "and find sounds to use, all under free licenses."),
        "canonical": request.build_absolute_uri(request.path),
        "image": image or request.build_absolute_uri(static("img/icon-512.png")),
        "large_image": bool(image),
        "kind": kind,
        "noindex": noindex,
        "locale": OG_LOCALES.get((get_language() or "es")[:2], "es_AR"),
        "json_ld": [mark_safe(seo.as_json_ld(d)) for d in (data or [])],
    }


@register.inclusion_tag("core/_seo.html", takes_context=True)
def seo_meta(context, title=None, description=None, image=None, kind="website", noindex=False):
    return _context(context, title, description, image, kind, noindex)


@register.inclusion_tag("core/_seo.html", takes_context=True)
def seo_audio(context, audio):
    request = context["request"]
    public = audio.visibility == "public" and not audio.moderation_hidden
    return _context(context, seo.audio_title(audio), seo.audio_description(audio),
                    request.build_absolute_uri(audio.image.url) if audio.image else None, "music.song",
                    noindex=not public, data=seo.audio_data(audio, request) if public else None)


@register.inclusion_tag("core/_seo.html", takes_context=True)
def seo_project(context, project):
    from project.models import LISTED_VISIBILITIES
    request = context["request"]
    # A work behind a secret link or private is never indexed, whatever the address.
    listed = project.visibility in LISTED_VISIBILITIES and not project.moderation_hidden
    return _context(context, project.name, seo.project_description(project),
                    request.build_absolute_uri(project.image.url) if project.image else None, "music.album",
                    noindex=not listed, data=seo.project_data(project, request) if listed else None)


@register.inclusion_tag("core/_seo.html", takes_context=True)
def seo_person(context, person, avatar_url=""):
    request = context["request"]
    if not avatar_url:
        try:
            from avatar.templatetags.avatar_tags import avatar_url as primary_avatar
            avatar_url = primary_avatar(person, 192)
        except Exception:  # no picture is fine: the profile still has its data
            avatar_url = ""
    profile = getattr(person, "userprofile", None)
    cover = getattr(profile, "cover", None)
    from project.templatetags.obra_tags import display_name
    return _context(context, display_name(person), seo.person_description(person),
                    request.build_absolute_uri(cover.url) if cover else None, "profile",
                    data=seo.person_data(person, request, avatar_url))


@register.inclusion_tag("core/_seo.html", takes_context=True)
def seo_site(context, title=None, description=None):
    return _context(context, title, description, data=seo.site_data(context["request"]))


@register.simple_tag
def audio_title(audio):
    """The <title> of a sound's page: its name and what it is."""
    return seo.audio_title(audio)
