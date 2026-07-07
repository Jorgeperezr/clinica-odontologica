from django.contrib import admin

from apps.whatsapp.models import (
    WhatsAppMessageLog,
    WhatsAppOptIn,
    WhatsAppTemplate,
)


@admin.register(WhatsAppTemplate)
class WhatsAppTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "meta_template_name", "category", "language", "is_active"]
    list_filter = ["category", "is_active", "tenant"]


@admin.register(WhatsAppOptIn)
class WhatsAppOptInAdmin(admin.ModelAdmin):
    list_display = ["patient", "channel", "opted_in_at", "revoked_at"]
    list_filter = ["tenant"]


@admin.register(WhatsAppMessageLog)
class WhatsAppMessageLogAdmin(admin.ModelAdmin):
    list_display = ["patient_phone", "template", "status", "created_at"]
    list_filter = ["status", "tenant"]
