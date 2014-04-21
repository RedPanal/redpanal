from django.utils.translation import ugettext_lazy as _

class License(object):
    def __init__(self, code, name, url, icon, icon_small):
        self.code = code
        self.name = name
        self.url = url
        self.icon = icon
        self.icon_small = icon_small

CC_BY_SA_4_0 = License("CC-BY-SA-4.0",
                        _("Creative Commons Attribution-ShareAlike 4.0 International"),
                        _("http://creativecommons.org/licenses/by-sa/4.0/"),
                        "http://i.creativecommons.org/l/by-sa/4.0/88x31.png",
                        "/static/img/rp-cc-by-sa_45.png",
                        )

LICENSES = {
    CC_BY_SA_4_0.code: CC_BY_SA_4_0,
}

DEFAULT_LICENSE = CC_BY_SA_4_0
