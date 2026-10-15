from django.conf import settings
from django.utils import translation


class PersonLanguageMiddleware:
    """The language a person chose in their settings wins over the browser's, on every device.
    Goes after LocaleMiddleware; without a choice, LocaleMiddleware's (cookie, then browser) stays."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = ""
        if request.user.is_authenticated:
            profile = getattr(request.user, "userprofile", None)
            lang = getattr(profile, "language", "") or ""
            if lang in dict(settings.LANGUAGES):
                translation.activate(lang)
                request.LANGUAGE_CODE = lang
            else:
                lang = ""
        response = self.get_response(request)
        name = settings.LANGUAGE_COOKIE_NAME
        if lang and request.COOKIES.get(name) != lang and name not in response.cookies:  # a new choice wins
            response.set_cookie(name, lang, max_age=365 * 24 * 3600, samesite="Lax")
        return response
