"""Visit statistics with Umami, hosted by RedPanal itself (docs: ESTADISTICAS.md).

What it never does: identify a person (no user, no IP, no cookies), record a private page or what someone searched.
Off unless the server sets UMAMI_SCRIPT_URL and UMAMI_WEBSITE_ID (so development and tests send nothing).

Pages: counted by rp-analytics.js, only when the page allows it (see `trackable`).
Events: "play" and "download" are seen in the browser; the ones that happen on the server ("signup", "upload",
"contribute", "follow", "post") are queued here and sent by the next page that loads.
"""
from django.conf import settings

# Each person's own pages: never counted, not even their address.
PRIVATE_PATHS = ("/estudio/", "/ajustes/", "/avisos/", "/crear/", "/accounts/", "/moderacion/", "/admin/",
                 "/reproductor/", "/idioma/")
EVENTS = ("signup", "upload", "contribute", "follow", "post")
_SESSION_KEY = "rp_analytics_events"


def enabled():
    return bool(getattr(settings, "UMAMI_SCRIPT_URL", "") and getattr(settings, "UMAMI_WEBSITE_ID", ""))


def queue_event(request, name):
    """Something that happened on the server, for the next page to send (only its name: no data about whom)."""
    if not enabled() or name not in EVENTS or not hasattr(request, "session"):
        return
    queued = request.session.get(_SESSION_KEY, [])
    if len(queued) < 20:
        request.session[_SESSION_KEY] = queued + [name]


def pop_events(request):
    if not hasattr(request, "session"):
        return []
    return request.session.pop(_SESSION_KEY, []) if _SESSION_KEY in request.session else []


def trackable(request):
    """Whether this page can be counted: public pages only. What search engines must not index (private, behind a
    secret link, hidden by moderation, a filtered search) isn't counted either; core.seo marks it while rendering."""
    if getattr(request, "rp_noindex", False):
        return False
    return not request.path.startswith(PRIVATE_PATHS)


def context(request):
    """For base.html: how to load Umami, if it's on."""
    if not enabled():
        return {"umami": None}
    return {"umami": {"script": settings.UMAMI_SCRIPT_URL, "website": settings.UMAMI_WEBSITE_ID,
                      "domains": getattr(settings, "UMAMI_DOMAINS", "")}}
