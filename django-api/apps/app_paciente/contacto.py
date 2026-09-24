"""
Pedir cita y escribir al consultorio desde la app, y la bandeja donde lo
atiende el personal.

Lado del paciente (`/api/v1/app/…`): hereda de `BaseVistaPaciente`, así
que exige rol de paciente y que la clínica tenga contratada la app, y el
paciente sale del token.

Lado del personal (`/api/v1/bandeja-app/…`): quien ve la agenda ve las
solicitudes, pero solo quien puede crear citas (administración y
recepción) las agenda o las rechaza, igual que en la agenda. Los
mensajes los contestan administración, recepción y doctores: una
pregunta del paciente puede ser clínica.

**Agendar crea la cita de verdad**, con el mismo serializador de la
agenda. Así pasan las mismas validaciones (nada en el pasado, nada
encima de otra cita del doctor) y una solicitud nunca queda marcada como
«agendada» sin una cita detrás.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.app_paciente.models import MensajeConsultorio, SolicitudCita
from apps.app_paciente.permissions import ficha_del_paciente
from apps.app_paciente.views import BaseVistaPaciente
from apps.common.permisos_funcionalidad import RequiereFuncionalidad
from apps.common.permissions import HasRole

# Límites para que la bandeja no se pueda inundar desde un teléfono.
MAX_SOLICITUDES_PENDIENTES = 3
MAX_MENSAJES_SIN_RESPUESTA = 5
MAX_DIAS_ADELANTE = 120
MAX_TEXTO = 1000

APP = RequiereFuncionalidad.para("app_paciente")
VEN = [HasRole.for_roles("admin", "reception", "doctor", "auxiliary"), APP]
AGENDAN = [HasRole.for_roles("admin", "reception"), APP]
RESPONDEN = [HasRole.for_roles("admin", "reception", "doctor"), APP]


# ── Formato de salida ───────────────────────────────────────────────────

def _solicitud(s, personal=False):
    d = {
        "id": str(s.id),
        "fecha_preferida": s.fecha_preferida.isoformat(),
        "franja": s.franja,
        "franja_texto": s.get_franja_display(),
        "motivo": s.motivo,
        "estado": s.estado,
        "estado_texto": s.get_estado_display(),
        "respuesta": s.respuesta,
        "creada": s.created_at.isoformat(),
        "cita": ({"id": str(s.cita.id), "inicio": s.cita.scheduled_start.isoformat()}
                 if s.cita else None),
    }
    if personal:
        d["paciente"] = {"id": str(s.patient.id), "nombre": s.patient.full_name,
                         "telefono": s.patient.phone}
    return d


def _mensaje(m, personal=False):
    d = {
        "id": str(m.id),
        "texto": m.texto,
        "creado": m.created_at.isoformat(),
        "respuesta": m.respuesta,
        "respondido": m.respondido_en.isoformat() if m.respondido_en else None,
    }
    if personal:
        d["paciente"] = {"id": str(m.patient.id), "nombre": m.patient.full_name}
        d["respondido_por"] = m.respondido_por.full_name if m.respondido_por else None
    return d


def _texto(valor, campo, maximo, obligatorio=True):
    t = (valor or "").strip() if isinstance(valor, str) else ""
    if obligatorio and not t:
        raise serializers.ValidationError({campo: "Escribe algo antes de enviar."})
    if len(t) > maximo:
        raise serializers.ValidationError({campo: f"Máximo {maximo} caracteres."})
    return t


# ── Lado del paciente ───────────────────────────────────────────────────

class MisSolicitudesCitaView(BaseVistaPaciente):
    """GET/POST /api/v1/app/solicitudes-cita/"""

    def get(self, request):
        ficha = ficha_del_paciente(request)
        qs = SolicitudCita.objects.filter(tenant=request.tenant, patient=ficha).select_related("cita")[:30]
        return Response([_solicitud(s) for s in qs])

    def post(self, request):
        ficha = ficha_del_paciente(request)
        datos = request.data if isinstance(request.data, dict) else {}

        fecha = serializers.DateField().run_validation(datos.get("fecha_preferida"))
        # La fecha de la CLÍNICA: con el servidor en otra zona horaria,
        # `date.today()` dejaba pedir cita para «ayer» o rechazaba «hoy».
        hoy = timezone.localdate()
        if fecha < hoy:
            raise serializers.ValidationError({"fecha_preferida": "Elige hoy o un día futuro."})
        if fecha > hoy + timedelta(days=MAX_DIAS_ADELANTE):
            raise serializers.ValidationError(
                {"fecha_preferida": f"Solo se puede pedir con {MAX_DIAS_ADELANTE} días de antelación."})

        franja = datos.get("franja") or SolicitudCita.Franja.CUALQUIERA
        if franja not in SolicitudCita.Franja.values:
            raise serializers.ValidationError({"franja": "Franja no válida."})
        motivo = _texto(datos.get("motivo"), "motivo", 300, obligatorio=False)

        pendientes = SolicitudCita.objects.filter(
            tenant=request.tenant, patient=ficha, estado=SolicitudCita.Estado.PENDIENTE,
        ).count()
        if pendientes >= MAX_SOLICITUDES_PENDIENTES:
            return Response(
                {"detail": f"Ya tienes {pendientes} solicitudes pendientes. "
                           "Espera a que la clínica las atienda."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        s = SolicitudCita.objects.create(
            tenant=request.tenant, patient=ficha,
            fecha_preferida=fecha, franja=franja, motivo=motivo,
        )
        return Response(_solicitud(s), status=status.HTTP_201_CREATED)


class MisMensajesView(BaseVistaPaciente):
    """GET/POST /api/v1/app/mensajes/"""

    def get(self, request):
        ficha = ficha_del_paciente(request)
        qs = MensajeConsultorio.objects.filter(tenant=request.tenant, patient=ficha)[:50]
        return Response([_mensaje(m) for m in qs])

    def post(self, request):
        ficha = ficha_del_paciente(request)
        datos = request.data if isinstance(request.data, dict) else {}
        texto = _texto(datos.get("texto"), "texto", MAX_TEXTO)
        sin_respuesta = MensajeConsultorio.objects.filter(
            tenant=request.tenant, patient=ficha, respondido_en__isnull=True,
        ).count()
        if sin_respuesta >= MAX_MENSAJES_SIN_RESPUESTA:
            return Response(
                {"detail": f"Tienes {sin_respuesta} mensajes sin responder. "
                           "La clínica te contestará pronto."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        m = MensajeConsultorio.objects.create(tenant=request.tenant, patient=ficha, texto=texto)
        return Response(_mensaje(m), status=status.HTTP_201_CREATED)


# ── Lado del personal ───────────────────────────────────────────────────

class ResumenBandejaView(APIView):
    """GET /api/v1/bandeja-app/resumen/ — lo pendiente, para el contador del menú."""

    permission_classes = VEN

    def get(self, request):
        return Response({
            "solicitudes_pendientes": SolicitudCita.objects.filter(
                tenant=request.tenant, estado=SolicitudCita.Estado.PENDIENTE).count(),
            "mensajes_sin_responder": MensajeConsultorio.objects.filter(
                tenant=request.tenant, respondido_en__isnull=True).count(),
        })


class SolicitudesBandejaView(APIView):
    """GET /api/v1/bandeja-app/solicitudes/?estado=pendiente|todas"""

    permission_classes = VEN

    def get(self, request):
        qs = SolicitudCita.objects.filter(tenant=request.tenant).select_related("patient", "cita")
        if request.query_params.get("estado", "pendiente") == "pendiente":
            # Las pendientes, las más antiguas primero: es el orden en que
            # hay que atenderlas.
            qs = qs.filter(estado=SolicitudCita.Estado.PENDIENTE).order_by("created_at")
        return Response([_solicitud(s, personal=True) for s in qs[:100]])


def _pendiente(request, pk):
    s = SolicitudCita.objects.filter(pk=pk, tenant=request.tenant).select_related("patient").first()
    if s is None:
        return None, Response({"detail": "No existe esa solicitud."}, status=status.HTTP_404_NOT_FOUND)
    if s.estado != SolicitudCita.Estado.PENDIENTE:
        return None, Response({"detail": "Esa solicitud ya se atendió."}, status=status.HTTP_409_CONFLICT)
    return s, None


class AgendarSolicitudView(APIView):
    """
    POST /api/v1/bandeja-app/solicitudes/<id>/agendar/
    { doctor, scheduled_start, scheduled_end, notes? }

    Crea la cita y marca la solicitud, las dos cosas o ninguna.
    """

    permission_classes = AGENDAN

    def post(self, request, pk):
        from apps.agenda.serializers import AppointmentSerializer

        with transaction.atomic():
            s, error = _pendiente(request, pk)
            if error:
                return error
            # Se bloquea la fila: dos recepcionistas agendando la misma
            # solicitud a la vez darían dos citas.
            s = SolicitudCita.objects.select_for_update().get(pk=s.pk)
            if s.estado != SolicitudCita.Estado.PENDIENTE:
                return Response({"detail": "Esa solicitud ya se atendió."}, status=status.HTTP_409_CONFLICT)

            datos = request.data if isinstance(request.data, dict) else {}
            notas = (datos.get("notes") or "").strip()
            if s.motivo and s.motivo not in notas:
                notas = f"{notas}\n" if notas else ""
                notas += f"Pedida desde la app: {s.motivo}"
            ser = AppointmentSerializer(
                data={**datos, "patient": str(s.patient_id), "notes": notas},
                context={"request": request},
            )
            ser.is_valid(raise_exception=True)
            cita = ser.save(tenant=request.tenant)

            s.estado = SolicitudCita.Estado.AGENDADA
            s.cita = cita
            s.respuesta = _texto(datos.get("respuesta"), "respuesta", 300, obligatorio=False)
            s.atendida_por = request.user
            s.atendida_en = timezone.now()
            s.save()
        return Response(_solicitud(s, personal=True))


class RechazarSolicitudView(APIView):
    """POST /api/v1/bandeja-app/solicitudes/<id>/rechazar/ { respuesta }"""

    permission_classes = AGENDAN

    def post(self, request, pk):
        s, error = _pendiente(request, pk)
        if error:
            return error
        datos = request.data if isinstance(request.data, dict) else {}
        # Obligatoria: un «no» sin explicación deja al paciente sin saber
        # si probar otro día o llamar.
        s.respuesta = _texto(datos.get("respuesta"), "respuesta", 300)
        s.estado = SolicitudCita.Estado.RECHAZADA
        s.atendida_por = request.user
        s.atendida_en = timezone.now()
        s.save()
        return Response(_solicitud(s, personal=True))


class MensajesBandejaView(APIView):
    """GET /api/v1/bandeja-app/mensajes/?pendientes=1"""

    permission_classes = VEN

    def get(self, request):
        qs = MensajeConsultorio.objects.filter(tenant=request.tenant).select_related("patient", "respondido_por")
        if request.query_params.get("pendientes", "1") == "1":
            qs = qs.filter(respondido_en__isnull=True).order_by("created_at")
        return Response([_mensaje(m, personal=True) for m in qs[:100]])


class ResponderMensajeView(APIView):
    """POST /api/v1/bandeja-app/mensajes/<id>/responder/ { respuesta }"""

    permission_classes = RESPONDEN

    def post(self, request, pk):
        m = MensajeConsultorio.objects.filter(pk=pk, tenant=request.tenant).select_related("patient").first()
        if m is None:
            return Response({"detail": "No existe ese mensaje."}, status=status.HTTP_404_NOT_FOUND)
        if m.respondido_en:
            return Response({"detail": "Ese mensaje ya tiene respuesta."}, status=status.HTTP_409_CONFLICT)
        datos = request.data if isinstance(request.data, dict) else {}
        m.respuesta = _texto(datos.get("respuesta"), "respuesta", MAX_TEXTO)
        m.respondido_por = request.user
        m.respondido_en = timezone.now()
        m.save()
        return Response(_mensaje(m, personal=True))
