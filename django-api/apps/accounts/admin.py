from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.models import AuditLog, DeviceToken, OTPCode, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["email"]
    list_display = ["email", "phone", "role", "tenant", "is_active", "is_staff"]
    list_filter = ["role", "is_active", "tenant"]
    search_fields = ["email", "phone"]
    fieldsets = (
        (None, {"fields": ("email", "phone", "password")}),
        ("Rol y sede", {"fields": ("role", "tenant")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "phone", "role", "tenant", "password1", "password2")}),
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "user", "action", "entity_type", "entity_id"]
    list_filter = ["action", "entity_type"]
    search_fields = ["entity_id"]
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.register(OTPCode)
admin.site.register(DeviceToken)

from apps.accounts.models import PasswordResetToken  # noqa: E402

admin.site.register(PasswordResetToken)
