from django.contrib import admin
from .models import SiteUpdate

@admin.register(SiteUpdate)
class SiteUpdateAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "created_at", "created_by")
    list_filter = ("is_active", "created_at")
    search_fields = ("title", "message")
    ordering = ("-created_at",)

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
