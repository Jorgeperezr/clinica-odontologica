"""
API de rachas y logros.

Dos públicos distintos y por eso dos grupos de vistas: el panel de la
clínica, que define y otorga, y la app del paciente, que solo lee lo
suyo. La del paciente vive en `apps.app_paciente` y no aquí, para que
siga cumpliéndose la regla de que el paciente nunca elige de quién son
los datos.
"""

from datetime import date

from django.db import IntegrityError, transaction
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permisos_funcionalidad import RequiereFuncionalidad
from apps.logros import reglas
from apps.logros.models import Logro, LogroDePaciente
from apps.logros.permissions import PuedeGestionarLogros

# Hace falta el permiso de la persona Y que la clínica tenga el módulo.
PUEDE = [PuedeGestionarLogros, RequiereFuncionalidad.para("logros")]
from apps.logros.serializers import LogroDePacienteSerializer, LogroSerializer


class LogroListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/logros/ — el catálogo de la clínica."""

    serializer_class = LogroSerializer
    permission_classes = PUEDE
    pagination_class = None

    def get_queryset(self):
        return Logro.objects.filter(tenant=self.request.tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)


class LogroDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = LogroSerializer
    permission_classes = PUEDE

    def get_queryset(self):
        return Logro.objects.filter(tenant=self.request.tenant)

    def perform_destroy(self, instance):
        # `PROTECT` en la FK impide borrar un logro ya concedido, y con
        # razón: borrarlo reescribiría la historia de quien lo ganó. Se
        # desactiva, que es lo que casi siempre se quiere de verdad.
        if instance.concesiones.exists():
            instance.activo = False
            instance.save(update_fields=["activo"])
            return
        instance.delete()


class OtorgarLogroView(APIView):
    """
    POST /api/v1/logros/otorgar/ — a mano, a un paciente concreto.

    Es la mitad que las reglas no cubren: premiar algo que el sistema no
    puede ver.
    """

    permission_classes = PUEDE

    def post(self, request):
        from apps.patients.models import Patient

        logro_id = request.data.get("logro")
        paciente_id = request.data.get("patient")
        if not logro_id or not paciente_id:
            return Response({"detail": "Faltan «logro» y «patient»."}, status=400)

        logro = Logro.objects.filter(pk=logro_id, tenant=request.tenant).first()
        paciente = Patient.objects.filter(pk=paciente_id, tenant=request.tenant).first()
        if not logro or not paciente:
            # Un 404 y no un 400: el id puede existir en OTRA clínica, y
            # decir «no es válido» confirmaría que existe en alguna parte.
            return Response({"detail": "Logro o paciente no encontrado."}, status=404)

        concesion = LogroDePaciente.objects.create(
            tenant=request.tenant, patient=paciente, logro=logro,
            otorgado_por=request.user, nota=str(request.data.get("nota", ""))[:200],
        )
        return Response(LogroDePacienteSerializer(concesion).data, status=201)


class LogrosDelPacienteView(generics.ListAPIView):
    """GET /api/v1/patients/{id}/logros/ — para la ficha del panel."""

    serializer_class = LogroDePacienteSerializer
    permission_classes = PUEDE
    pagination_class = None

    def get_queryset(self):
        return LogroDePaciente.objects.filter(
            patient_id=self.kwargs["pk"], tenant=self.request.tenant,
        ).select_related("logro", "otorgado_por")


class EvaluarLogrosView(APIView):
    """
    POST /api/v1/logros/evaluar/ — pasa las reglas automáticas.

    Se puede llamar desde el panel para no esperar a la tarea
    programada. Es idempotente: la restricción de unicidad por periodo
    impide conceder dos veces el mismo mes.
    """

    permission_classes = PUEDE

    def post(self, request):
        mes = _primer_dia_del_mes_pedido(request.data.get("mes"))
        concedidos = evaluar(request.tenant, mes)
        return Response({
            "mes": mes.isoformat(),
            "concedidos": concedidos,
            "detalle": "Sin novedades." if concedidos == 0
                       else f"{concedidos} logro(s) concedidos.",
        })


def _primer_dia_del_mes_pedido(valor):
    if valor:
        try:
            partido = date.fromisoformat(str(valor))
            return date(partido.year, partido.month, 1)
        except ValueError:
            # Un mes mal escrito no merece un 400: quien pulsa «evaluar»
            # en el panel casi siempre quiere el mes en curso, y es lo
            # que se devuelve abajo. Rechazar la petición entera por un
            # parámetro opcional sería peor que ignorarlo.
            pass
    from django.utils import timezone
    # `localdate` y no `date.today()`: importa la fecha de la clínica.
    hoy = timezone.localdate()
    return date(hoy.year, hoy.month, 1)


def evaluar(tenant, mes):
    """
    Concede los logros automáticos que correspondan a ese mes.

    Devuelve cuántos concedió. Se salta en silencio los que ya estaban
    —la restricción de unicidad los rechaza— porque evaluar dos veces el
    mismo mes tiene que ser inofensivo: si no, nadie se atrevería a
    pulsar el botón dos veces.
    """
    from apps.patients.models import Patient

    automaticos = list(Logro.objects.filter(
        tenant=tenant, activo=True,
    ).exclude(regla=Logro.Regla.MANUAL))
    if not automaticos:
        return 0

    concedidos = 0
    pacientes = Patient.objects.filter(tenant=tenant, is_active=True)
    for paciente in pacientes.iterator():
        for logro in automaticos:
            if logro.meses_requeridos > 1:
                if reglas.racha_de(paciente, logro, mes) < logro.meses_requeridos:
                    continue
            elif not reglas.cumple(logro, paciente, mes):
                continue
            try:
                # El `atomic` interior NO es decorativo: sin él, el
                # IntegrityError que lanza la restricción de unicidad
                # deja la transacción envenenada y TODO lo que viene
                # después revienta con «You can't execute queries until
                # the end of the atomic block». Es decir, la segunda
                # evaluación del mismo mes tumbaría la operación entera
                # en vez de no hacer nada. Con el punto de guardado solo
                # se deshace este INSERT.
                with transaction.atomic():
                    LogroDePaciente.objects.create(
                        tenant=tenant, patient=paciente, logro=logro, periodo=mes,
                    )
                concedidos += 1
            except IntegrityError:
                # Ya lo tenía de una evaluación anterior de este mismo mes.
                pass
    return concedidos
