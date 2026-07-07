from django.urls import path

from apps.specialties import views

urlpatterns = [
    path("specialties/", views.SpecialtyListCreateView.as_view(), name="specialty-list"),
    path("specialties/<uuid:pk>/", views.SpecialtyDetailView.as_view(), name="specialty-detail"),
    path("specialties/<uuid:pk>/form-template/", views.SpecialtyFormTemplateView.as_view(), name="specialty-form-template"),
    # Alias bajo /config/
    path("config/specialties/", views.SpecialtyListCreateView.as_view(), name="config-specialty-list"),
    path("config/specialties/<uuid:pk>/", views.SpecialtyDetailView.as_view(), name="config-specialty-detail"),
    # Formularios clínicos por especialidad (Sprint 7)
    path("patients/<uuid:pk>/specialty-forms/", views.PatientSpecialtyFormListCreateView.as_view(), name="patient-specialty-forms"),
    path("specialty-forms/<uuid:pk>/", views.SpecialtyFormDetailView.as_view(), name="specialty-form-detail"),
]
