from django.urls import path

from apps.app_paciente import views

urlpatterns = [
    path("app/me/", views.MiPerfilView.as_view(), name="app-mi-perfil"),
    path("app/citas/", views.MisCitasView.as_view(), name="app-mis-citas"),
    path("app/saldo/", views.MiSaldoView.as_view(), name="app-mi-saldo"),
    path("app/indicaciones/", views.MisIndicacionesView.as_view(), name="app-mis-indicaciones"),
    path("app/logros/", views.MisLogrosView.as_view(), name="app-mis-logros"),
    path("app/clinica/", views.MiClinicaView.as_view(), name="app-mi-clinica"),
]
