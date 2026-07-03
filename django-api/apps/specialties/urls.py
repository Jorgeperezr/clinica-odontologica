from django.urls import path

from apps.specialties import views

urlpatterns = [
    path("specialties/", views.SpecialtyListCreateView.as_view(), name="specialty-list"),
    path("specialties/<uuid:pk>/", views.SpecialtyDetailView.as_view(), name="specialty-detail"),
    # Alias bajo /config/ para coherencia con la sección de configuración del SRS
    path("config/specialties/", views.SpecialtyListCreateView.as_view(), name="config-specialty-list"),
    path("config/specialties/<uuid:pk>/", views.SpecialtyDetailView.as_view(), name="config-specialty-detail"),
]
