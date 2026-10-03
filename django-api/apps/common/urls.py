from django.urls import path

from apps.common import health
from apps.common import platform_views as views

urlpatterns = [
    # Sondas de salud: públicas y sin autenticación, porque quien las
    # consulta (Docker, un balanceador, un monitor) no tiene credenciales.
    path("health/", health.HealthView.as_view(), name="health"),
    path("ready/", health.ReadyView.as_view(), name="ready"),
    path("platform/overview/", views.PlatformOverviewView.as_view(), name="platform-overview"),
    path("platform/clinics/", views.ClinicListCreateView.as_view(), name="platform-clinics"),
    path("platform/clinics/<uuid:pk>/", views.ClinicDetailView.as_view(), name="platform-clinic-detail"),
    path("platform/clinics/<uuid:pk>/admin/", views.ClinicAdminView.as_view(), name="platform-clinic-admin"),
    path("platform/clinics/<uuid:pk>/admin/reset-password/",
         views.ClinicAdminResetPasswordView.as_view(), name="platform-clinic-admin-reset"),
    path("platform/audit/", views.PlatformAuditView.as_view(), name="platform-audit"),
    path("platform/config/", views.PlatformConfigView.as_view(), name="platform-config"),
]
