from django.urls import path

from apps.common import platform_views as views

urlpatterns = [
    path("platform/clinics/", views.ClinicListCreateView.as_view(), name="platform-clinics"),
    path("platform/clinics/<uuid:pk>/", views.ClinicDetailView.as_view(), name="platform-clinic-detail"),
    path("platform/clinics/<uuid:pk>/admin/", views.ClinicAdminCreateView.as_view(), name="platform-clinic-admin"),
    path("platform/overview/", views.PlatformOverviewView.as_view(), name="platform-overview"),
]
