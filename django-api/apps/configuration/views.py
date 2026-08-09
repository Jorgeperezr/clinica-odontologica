from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import HasRole, IsClinicAdmin
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


class DocumentAppearanceView(APIView):
    """
    GET   /api/v1/config/document-appearance/ — apariencia de los documentos.
          Lectura para todo el personal clínico: los generadores de PDF y
          la vista previa del panel la necesitan, no solo el administrador.
    PATCH /api/v1/config/document-appearance/ — solo administrador. Acepta
          uno o varios grupos; los ajustes se fusionan con lo guardado, de
          modo que enviar solo el grupo tocado no borra el resto.

    El formulario MSP HCU-033/2021 queda FUERA de este motor por ser un
    formato oficial de diseño legalmente fijado.
    """

    permission_classes = [HasRole.for_roles("admin", "reception", "doctor", "auxiliary")]

    def _get_or_create(self, request):
        from .models import DocumentAppearance
        obj, _ = DocumentAppearance.objects.get_or_create(tenant=request.tenant)
        return obj

    def get(self, request):
        from .serializers import DocumentAppearanceSerializer
        return Response(DocumentAppearanceSerializer(self._get_or_create(request)).data)

    def patch(self, request):
        from .serializers import DocumentAppearanceSerializer

        if request.user.role != "admin":
            return Response(
                {"error": {"message": "Solo el administrador puede cambiar la apariencia."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        obj = self._get_or_create(request)
        ser = DocumentAppearanceSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    def delete(self, request):
        """Restablece la apariencia por defecto (solo administrador)."""
        from .models import DocumentAppearance
        from .serializers import DocumentAppearanceSerializer

        if request.user.role != "admin":
            return Response(
                {"error": {"message": "Solo el administrador puede restablecer la apariencia."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        obj = self._get_or_create(request)
        for group in DocumentAppearance.GROUPS:
            setattr(obj, group, DocumentAppearance.DEFAULTS[group]())
        obj.save()
        return Response(DocumentAppearanceSerializer(obj).data)


# ── Copia de seguridad de la clínica (Sprint 65) ─────────────────────
MIN_PASSPHRASE = 12
MAX_BACKUP_UPLOAD = 60 * 1024 * 1024      # 60 MB


def _audit_backup(request, action, metadata=None):
    from apps.accounts.models import AuditLog

    AuditLog.objects.create(
        tenant=request.tenant, user=request.user, action=action,
        entity_type="TenantBackup", entity_id=str(request.tenant.id),
        ip_address=request.META.get("REMOTE_ADDR"),
        metadata=metadata or {},
    )


class TenantBackupView(APIView):
    """
    POST /api/v1/config/backup/ — genera la copia cifrada de la clínica y
    la devuelve como descarga.

    Cuerpo: {"passphrase": "...", "passphrase_confirm": "..."}

    Solo la administradora o el administrador de la clínica. El Super
    Administrador queda fuera a propósito: administra la plataforma, no
    es titular de los datos de ninguna clínica (ver `IsClinicAdmin`).
    """

    permission_classes = [IsClinicAdmin]

    def post(self, request):
        passphrase = (request.data.get("passphrase") or "").strip()
        confirm = (request.data.get("passphrase_confirm") or "").strip()

        if len(passphrase) < MIN_PASSPHRASE:
            return Response(
                {"error": {"message":
                    f"La frase de cifrado debe tener al menos {MIN_PASSPHRASE} caracteres."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if confirm and confirm != passphrase:
            return Response(
                {"error": {"message": "La frase de cifrado y su confirmación no coinciden."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.http import HttpResponse

        from apps.common.tenant_backup import build_encrypted, suggested_filename

        blob, manifest = build_encrypted(request.tenant, passphrase, requested_by=request.user)

        # Se audita el hecho, nunca la frase: dejarla en el registro
        # anularía el cifrado para cualquiera que lea la auditoría.
        _audit_backup(request, "create_backup", {
            "total_records": manifest["total_records"],
            "bytes": len(blob),
        })

        response = HttpResponse(blob, content_type="application/octet-stream")
        response["Content-Disposition"] = f'attachment; filename="{suggested_filename(request.tenant)}"'
        response["X-Backup-Records"] = str(manifest["total_records"])
        return response


class TenantBackupDecryptView(APIView):
    """
    POST /api/v1/config/backup/decrypt/ — descifra una copia y devuelve
    su contenido legible.

    Envío multipart: `file` (el .clinicabk) y `passphrase`.

    Descifrar NO restaura nada: devuelve la información para consultarla
    o guardarla en claro. Reemplazar la base de datos con una copia es
    una operación destructiva que se hace desde el servidor, con
    `scripts/restore.sh`, y no debe estar a un clic en un panel web.
    """

    permission_classes = [IsClinicAdmin]

    def post(self, request):
        from apps.common.tenant_backup import BackupError, read_encrypted

        upload = request.FILES.get("file")
        passphrase = (request.data.get("passphrase") or "").strip()

        if upload is None:
            return Response({"error": {"message": "Adjunta el archivo de la copia."}},
                            status=status.HTTP_400_BAD_REQUEST)
        if not passphrase:
            return Response({"error": {"message": "Escribe la frase con la que se cifró."}},
                            status=status.HTTP_400_BAD_REQUEST)
        if upload.size > MAX_BACKUP_UPLOAD:
            return Response(
                {"error": {"message": "El archivo supera el tamaño máximo admitido (60 MB)."}},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        try:
            payload = read_encrypted(upload.read(), passphrase)
        except BackupError as exc:
            _audit_backup(request, "decrypt_backup_failed", {"reason": str(exc)})
            return Response({"error": {"message": str(exc)}},
                            status=status.HTTP_400_BAD_REQUEST)

        # Una copia de otra clínica no se abre aquí aunque se conozca su
        # frase: cada administración descifra lo suyo.
        origin = payload.get("manifest", {}).get("tenant", {}).get("id")
        if origin and str(origin) != str(request.tenant.id):
            _audit_backup(request, "decrypt_backup_denied", {"origin_tenant": str(origin)})
            return Response(
                {"error": {"message": "Esta copia pertenece a otra clínica y no se puede abrir aquí."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        _audit_backup(request, "decrypt_backup", {
            "total_records": payload["manifest"].get("total_records", 0),
            "generated_at": payload["manifest"].get("generated_at", ""),
        })
        return Response(payload)
