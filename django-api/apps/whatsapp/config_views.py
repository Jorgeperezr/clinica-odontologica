"""
La clínica conecta SU cuenta de WhatsApp.

Regla que manda sobre todo lo demás en este archivo: **el token entra
pero no sale**. Se puede escribir, se puede saber si está puesto y se
ven sus últimos cuatro caracteres para reconocerlo; leerlo entero, no.
Un token de Meta permite enviar mensajes en nombre de la clínica, y
devolverlo al navegador lo expone a cualquier extensión instalada y a
cualquiera que mire la pestaña de red.
"""

from django.utils import timezone
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.funciones import tiene
from apps.accounts.models import User
from apps.common.permisos_funcionalidad import RequiereFuncionalidad
from apps.whatsapp.models import ConfiguracionWhatsApp


class PuedeGestionarWhatsApp(BasePermission):
    """
    El administrador de la clínica, y el profesional al que se le
    concedió el permiso al crearlo. Mismo criterio que con los logros:
    quien puede escribir en nombre de la clínica se decide una vez, al
    dar de alta a la persona, y no por llevar bata.
    """

    message = "No tienes permiso para configurar WhatsApp en esta clínica."

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if u.role == User.Role.ADMIN or u.is_superuser:
            return True
        return tiene(u, "whatsapp")


class ConfiguracionWhatsAppView(APIView):
    """
    GET   /api/v1/config/whatsapp/ — cómo está, sin el token.
    PATCH /api/v1/config/whatsapp/ — conectarla o cambiarla.
    """

    permission_classes = [
        PuedeGestionarWhatsApp,
        RequiereFuncionalidad.para("whatsapp"),
    ]

    def _config(self, request):
        obj, _ = ConfiguracionWhatsApp.objects.get_or_create(tenant=request.tenant)
        return obj

    def _estado(self, obj):
        return {
            "phone_number_id": obj.phone_number_id,
            "numero_visible": obj.numero_visible,
            "plantilla_recordatorio": obj.plantilla_recordatorio,
            "activo": obj.activo,
            # Nunca el token: solo si está y cómo acaba.
            "token_puesto": bool(obj.token),
            "token_pista": obj.pista_del_token,
            "esta_configurada": obj.esta_configurada,
            "puede_enviar": obj.puede_enviar,
            "comprobado_en": obj.comprobado_en,
        }

    def get(self, request):
        return Response(self._estado(self._config(request)))

    def patch(self, request):
        obj = self._config(request)

        for campo in ("phone_number_id", "numero_visible", "plantilla_recordatorio"):
            if campo in request.data:
                setattr(obj, campo, str(request.data.get(campo) or "").strip()[:80])

        # El token solo se toca si viene algo. Mandar la cadena vacía NO
        # lo borra por accidente: para quitarlo hay que decirlo aparte,
        # porque un formulario que reenvía sus campos vacíos dejaría a la
        # clínica sin WhatsApp sin que nadie lo pidiera.
        if str(request.data.get("token_borrar", "")).lower() in ("true", "1"):
            obj.token = ""
        elif str(request.data.get("access_token", "")).strip():
            obj.token = str(request.data["access_token"]).strip()

        if "activo" in request.data:
            encender = str(request.data.get("activo")).lower() in ("true", "1")
            if encender and not obj.esta_configurada:
                return Response(
                    {"detail": "Faltan datos para encenderlo: hacen falta el "
                               "identificador de número, el token y la plantilla."},
                    status=400,
                )
            obj.activo = encender

        # Apagarlo solo si deja de estar configurada: así, borrar el
        # token no deja la clínica «encendida» sin poder enviar nada.
        if obj.activo and not obj.esta_configurada:
            obj.activo = False

        obj.comprobado_en = timezone.now()
        obj.save()
        return Response(self._estado(obj))
