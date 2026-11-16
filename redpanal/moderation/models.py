from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

MODERATORS_GROUP = "moderadores"


def is_moderator(user):
    """Volunteers who review reports: staff, or members of the "moderadores" group."""
    if user is None or not user.is_authenticated:
        return False
    return user.is_staff or user.groups.filter(name=MODERATORS_GROUP).exists()


class Report(models.Model):
    """Someone flags a work, an audio or a comment for the volunteers to review."""

    REASONS = (
        ("copyright", _("It uses material without permission")),
        ("credit", _("Credits are wrong or missing")),
        ("spam", _("Spam or advertising")),
        ("offensive", _("Offensive or violent")),
        ("other", _("Something else")),
    )
    OPEN, HIDDEN, DISMISSED = "open", "hidden", "dismissed"
    STATUSES = ((OPEN, _("open")), (HIDDEN, _("hidden")), (DISMISSED, _("dismissed")))

    reporter = models.ForeignKey(User, related_name="reports", on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    reason = models.CharField(_("reason"), max_length=20, choices=REASONS)
    detail = models.TextField(_("details"), blank=True, max_length=2000)
    status = models.CharField(max_length=20, choices=STATUSES, default=OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_by = models.ForeignKey(User, related_name="resolved_reports", null=True, blank=True,
                                    on_delete=models.SET_NULL)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution = models.CharField(_("note"), max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return "%s · %s" % (self.get_reason_display(), self.content_object)

    def resolve(self, moderator, status, note=""):
        self.status, self.resolved_by, self.resolved_at, self.resolution = status, moderator, timezone.now(), note
        self.save()
