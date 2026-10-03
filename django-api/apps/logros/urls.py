from django.urls import path

from apps.logros import views

urlpatterns = [
    path("logros/", views.LogroListCreateView.as_view(), name="logro-list"),
    path("logros/<uuid:pk>/", views.LogroDetailView.as_view(), name="logro-detail"),
    path("logros/otorgar/", views.OtorgarLogroView.as_view(), name="logro-otorgar"),
    path("logros/evaluar/", views.EvaluarLogrosView.as_view(), name="logro-evaluar"),
    path("patients/<uuid:pk>/logros/", views.LogrosDelPacienteView.as_view(),
         name="logros-del-paciente"),
]
