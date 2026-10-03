"""
Alertas clínicas del paciente (ver `alertas.py`).

  GET  /api/v1/patients/{id}/alertas/          las alertas activas
  POST /api/v1/patients/{id}/alertas/revisar/  {"texto": "..."} → choques
                                               de una receta con ellas

Las alertas salen de los antecedentes médicos, así que tienen el mismo
acceso que ellos: administrador, doctor y auxiliar; recepción no. Y cada
consulta queda en la auditoría como un acceso a los antecedentes
(LOPDP), igual que abrirlos.
"""

from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AuditLog
from apps.clinical.alertas import alertas_de_antecedentes, revisar_receta
from apps.clinical.models import Form033Record
from apps.patients.models import MedicalBackground, Patient
from apps.patients.views import CAN_EDIT_MEDICAL

LARGO_MAXIMO = 5000


def _alertas(request, pk, accion):
    paciente = generics.get_object_or_404(Patient, pk=pk, tenant=request.tenant, is_active=True)
    fondo = MedicalBackground.objects.filter(patient=paciente).first()
    form033 = Form033Record.objects.filter(patient=paciente).order_by("-date", "-created_at").first()
    AuditLog.objects.create(
        tenant=request.tenant, user=request.user, action=accion,
        entity_type="MedicalBackground", entity_id=str(paciente.id),
    )
    return alertas_de_antecedentes(fondo, form033)


class AlertasPacienteView(APIView):
    permission_classes = [CAN_EDIT_MEDICAL]

    def get(self, request, pk):
        return Response({"alertas": _alertas(request, pk, "view_clinical_alerts")})


class RevisarRecetaView(APIView):
    """Avisa; no bloquea. Guardar la receta sigue siendo decisión del profesional."""

    permission_classes = [CAN_EDIT_MEDICAL]

    def post(self, request, pk):
        texto = request.data.get("texto")
        if not isinstance(texto, str) or not texto.strip():
            return Response({"detail": "Falta el texto de la receta."}, status=400)
        if len(texto) > LARGO_MAXIMO:
            return Response({"detail": "La receta es demasiado larga para revisarla."}, status=400)
        alertas = _alertas(request, pk, "check_prescription_alerts")
        return Response({"choques": revisar_receta(texto, alertas), "alertas": alertas})
