from django.db import models
from django.utils.timezone import now
from django.conf import settings

class SiteUpdate(models.Model):
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.URLField(blank=True, null=True, help_text="Optional link (PDF, page, or external URL)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=now)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="site_updates"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
