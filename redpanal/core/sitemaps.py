"""sitemap.xml: what search engines should find — public projects and open calls, public sounds, the people who
share them and the hashtags they use. Nothing private, behind a secret link or hidden by moderation."""
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.sitemaps import Sitemap
from django.contrib.sitemaps.views import sitemap as django_sitemap
from django.db.models import Q
from django.urls import reverse


class _OnThisHost(Sitemap):
    """Addresses on the host that was asked, not on the Sites record (which says example.com in development)."""
    host = None

    def get_domain(self, site=None):
        return self.host or super().get_domain(site)


class PagesSitemap(_OnThisHost):
    changefreq, priority = "daily", 0.6

    def items(self):
        return ["index", "explore", "all-people"]

    def location(self, name):
        return reverse(name)


def listed_projects():
    from project.models import Project
    return Project.objects.listed()


def public_sounds():
    """Loose sounds, and parts of works that are listed."""
    from audio.models import Audio
    return (Audio.objects.visible_to(None).filter(moderation_hidden=False)
            .filter(Q(contributions__isnull=True) | Q(contributions__project__in=listed_projects()))
            .distinct())


class ProjectsSitemap(_OnThisHost):
    changefreq, priority, limit = "weekly", 0.8, 5000

    def items(self):
        return listed_projects().order_by("-created_at")

    def lastmod(self, project):
        return project.created_at


class SoundsSitemap(_OnThisHost):
    changefreq, priority, limit = "monthly", 0.7, 5000

    def items(self):
        return public_sounds().order_by("-created_at")

    def lastmod(self, audio):
        return audio.created_at


class PeopleSitemap(_OnThisHost):
    changefreq, priority, limit = "weekly", 0.5, 5000

    def items(self):
        return (User.objects.filter(Q(project__in=listed_projects()) | Q(audio__in=public_sounds()))
                .distinct().order_by("username"))


class TagsSitemap(_OnThisHost):
    changefreq, priority, limit = "weekly", 0.4, 5000

    def items(self):
        from taggit.models import Tag
        from audio.models import Audio
        from project.models import Project
        used = (Q(taggit_taggeditem_items__content_type=ContentType.objects.get_for_model(Project),
                  taggit_taggeditem_items__object_id__in=listed_projects().values("pk"))
                | Q(taggit_taggeditem_items__content_type=ContentType.objects.get_for_model(Audio),
                    taggit_taggeditem_items__object_id__in=public_sounds().values("pk")))
        return Tag.objects.filter(used).distinct().order_by("slug")

    def location(self, tag):
        return reverse("hashtaged-list", args=[tag.slug])


SITEMAPS = {"pages": PagesSitemap, "projects": ProjectsSitemap, "sounds": SoundsSitemap,
            "people": PeopleSitemap, "tags": TagsSitemap}


def sitemap_xml(request):
    maps = {}
    for name, cls in SITEMAPS.items():
        maps[name] = cls()
        maps[name].host = request.get_host()
    return django_sitemap(request, sitemaps=maps)
