from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import HasRole
from apps.configuration.models import Agreement, SystemParameter, Tariff, Treatment
from apps.configuration.serializers import (
    AgreementSerializer,
    SystemParameterSerializer,
    TariffSerializer,
    TreatmentSerializer,
)

CAN_MANAGE = HasRole.for_roles("admin")
CAN_VIEW = HasRole.for_roles("admin", "reception", "doctor", "auxiliary")


class _ConfigListCreate(generics.ListCreateAPIView):
    """Base: lectura para staff clínico, escritura solo admin."""

    def get_permissions(self):
        return [CAN_MANAGE()] if self.request.method == "POST" else [CAN_VIEW()]

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)


class _ConfigDetail(generics.RetrieveUpdateDestroyAPIView):
    def get_permissions(self):
        return [CAN_VIEW()] if self.request.method == "GET" else [CAN_MANAGE()]


class TreatmentListCreateView(_ConfigListCreate):
    """GET/POST /config/treatments/ — RF-CFG-02"""

    serializer_class = TreatmentSerializer
    filterset_fields = ["specialty", "is_active"]

    def get_queryset(self):
        return (
            Treatment.objects.filter(tenant=self.request.tenant)
            .select_related("specialty")
            .order_by("name")
        )


class TreatmentDetailView(_ConfigDetail):
    serializer_class = TreatmentSerializer

    def get_queryset(self):
        return Treatment.objects.filter(tenant=self.request.tenant)


class AgreementListCreateView(_ConfigListCreate):
    """GET/POST /config/agreements/ — RF-CFG-04"""

    serializer_class = AgreementSerializer

    def get_queryset(self):
        return Agreement.objects.filter(tenant=self.request.tenant).order_by("name")


class AgreementDetailView(_ConfigDetail):
    serializer_class = AgreementSerializer

    def get_queryset(self):
        return Agreement.objects.filter(tenant=self.request.tenant)


class TariffListCreateView(_ConfigListCreate):
    """GET/POST /config/tarifarios/ — RF-CFG-03"""

    serializer_class = TariffSerializer
    filterset_fields = ["treatment", "agreement"]

    def get_queryset(self):
        return Tariff.objects.filter(tenant=self.request.tenant)


class TariffDetailView(_ConfigDetail):
    serializer_class = TariffSerializer

    def get_queryset(self):
        return Tariff.objects.filter(tenant=self.request.tenant)


class SystemParameterListView(generics.ListAPIView):
    """GET /config/parameters/ — RF-CFG-05"""

    serializer_class = SystemParameterSerializer
    permission_classes = [CAN_MANAGE]

    def get_queryset(self):
        return SystemParameter.objects.filter(tenant=self.request.tenant).order_by("key")


class SystemParameterDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /config/parameters/{id}/ — el admin solo edita 'value'."""

    serializer_class = SystemParameterSerializer
    permission_classes = [CAN_MANAGE]

    def get_queryset(self):
        return SystemParameter.objects.filter(tenant=self.request.tenant)


class ClinicBrandingView(APIView):
    """
    GET  /api/v1/config/branding/  — identidad visual de la clínica.
         Lectura para cualquier usuario autenticado del tenant (el tema
         se aplica a toda la interfaz, no solo al administrador).
    PATCH /api/v1/config/branding/ — solo administrador. Acepta multipart
         (logo) y/o JSON (theme). Con logo_clear=true elimina el logotipo.
         Al subir un logo se devuelve además auto_palette con los colores
         predominantes extraídos, para ofrecer el tema automático.
    """

    permission_classes = [HasRole.for_roles("admin", "reception", "doctor", "auxiliary")]

    def _get_or_create(self, request):
        from .models import ClinicBranding
        obj, _ = ClinicBranding.objects.get_or_create(tenant=request.tenant)
        return obj

    def get(self, request):
        from .serializers import ClinicBrandingSerializer
        obj = self._get_or_create(request)
        return Response(ClinicBrandingSerializer(obj, context={"request": request}).data)

    def patch(self, request):
        from .branding import extract_palette
        from .serializers import ClinicBrandingSerializer

        if request.user.role != "admin":
            return Response({"detail": "Solo el administrador puede modificar la identidad visual."},
                            status=403)

        obj = self._get_or_create(request)
        auto_palette = None

        if str(request.data.get("logo_clear", "")).lower() in ("true", "1"):
            if obj.logo:
                obj.logo.delete(save=False)
            obj.logo = None

        if "logo" in request.FILES:
            # Al reemplazar, el archivo anterior se borra del disco: evita
            # acumular logotipos huérfanos de cada prueba y garantiza que
            # no queden restos de la imagen previa.
            if obj.logo:
                obj.logo.delete(save=False)
            obj.logo = request.FILES["logo"]
            try:
                auto_palette = extract_palette(request.FILES["logo"])
            except Exception:
                auto_palette = None

        for field in ("display_name", "short_name", "address", "phone", "email"):
            if field in request.data:
                setattr(obj, field, str(request.data.get(field) or "").strip()[:200])

        theme = request.data.get("theme")
        if theme is not None:
            import json
            if isinstance(theme, str):
                try:
                    theme = json.loads(theme)
                except ValueError:
                    return Response({"detail": "El tema no tiene un formato válido."}, status=400)
            if not isinstance(theme, dict):
                return Response({"detail": "El tema no tiene un formato válido."}, status=400)
            obj.theme = theme

        obj.save()
        data = ClinicBrandingSerializer(obj, context={"request": request}).data
        if auto_palette is not None:
            data["auto_palette"] = auto_palette
        return Response(data)
