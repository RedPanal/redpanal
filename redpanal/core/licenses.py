from django.utils.translation import gettext_lazy as _

class License(object):
    def __init__(self, code, name, url, icon, icon_small, plain=""):
        self.code = code
        self.name = name
        self.url = url
        self.icon = icon
        self.icon_small = icon_small
        # What the license means for people, without acronyms
        self.plain = plain

CC_BY_SA_4_0 = License("CC-BY-SA-4.0",
                        _("Creative Commons Attribution-ShareAlike 4.0 International"),
                        _("https://creativecommons.org/licenses/by-sa/4.0/"),
                        "https://licensebuttons.net/l/by-sa/4.0/88x31.png",
                        "/static/img/rp-cc-by-sa_45.png",
                        _("Anyone can use it if they credit the people who made it and share alike."),
                        )

LICENSES = {
    CC_BY_SA_4_0.code: CC_BY_SA_4_0,
}

DEFAULT_LICENSE = CC_BY_SA_4_0
