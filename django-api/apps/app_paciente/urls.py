from django.urls import path

from apps.app_paciente import contacto, views

urlpatterns = [
    path("app/me/", views.MiPerfilView.as_view(), name="app-mi-perfil"),
    path("app/citas/", views.MisCitasView.as_view(), name="app-mis-citas"),
    path("app/saldo/", views.MiSaldoView.as_view(), name="app-mi-saldo"),
    path("app/indicaciones/", views.MisIndicacionesView.as_view(), name="app-mis-indicaciones"),
    path("app/logros/", views.MisLogrosView.as_view(), name="app-mis-logros"),
    path("app/clinica/", views.MiClinicaView.as_view(), name="app-mi-clinica"),
    # Pedir cita y escribir al consultorio (lado del paciente)
    path("app/solicitudes-cita/", contacto.MisSolicitudesCitaView.as_view(), name="app-solicitudes-cita"),
    path("app/mensajes/", contacto.MisMensajesView.as_view(), name="app-mensajes"),
    # Bandeja del panel (lado del personal)
    path("bandeja-app/resumen/", contacto.ResumenBandejaView.as_view(), name="bandeja-resumen"),
    path("bandeja-app/solicitudes/", contacto.SolicitudesBandejaView.as_view(), name="bandeja-solicitudes"),
    path("bandeja-app/solicitudes/<uuid:pk>/agendar/", contacto.AgendarSolicitudView.as_view(),
         name="bandeja-agendar"),
    path("bandeja-app/solicitudes/<uuid:pk>/rechazar/", contacto.RechazarSolicitudView.as_view(),
         name="bandeja-rechazar"),
    path("bandeja-app/mensajes/", contacto.MensajesBandejaView.as_view(), name="bandeja-mensajes"),
    path("bandeja-app/mensajes/<uuid:pk>/responder/", contacto.ResponderMensajeView.as_view(),
         name="bandeja-responder"),
]
