from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import HasRole, IsClinicAdmin
from apps.configuration.models import Agreement, SystemParameter, Tariff, Treatment
from apps.configuration.pricing import price_matrix
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
        # Cuántos pacientes cubre cada convenio: es el dato que decide si se
        # puede desactivar sin dejar a nadie con una tarifa a medias.
        return (
            Agreement.objects.filter(tenant=self.request.tenant)
            .annotate(
                patient_count=Count("patients", filter=Q(patients__is_active=True))
            )
            .order_by("name")
        )


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


class PriceMatrixView(APIView):
    """
    GET  /api/v1/config/price-matrix/ — rejilla tratamiento × convenio.
    PUT  /api/v1/config/price-matrix/ — fija o borra el precio de una celda.

    Existe porque la rejilla es el modo natural de trabajar un tarifario —se
    revisa por columnas, «qué me paga esta aseguradora por cada cosa»— y
    montarla desde `/config/tarifarios/` obligaba al panel a pedir
    tratamientos, convenios y tarifarios por separado y a cruzarlos a mano,
    resolviendo la herencia de precios en el navegador. Esa herencia es una
    regla de negocio y va en el servidor (ver `pricing.price_for`).

    El PUT hace alta-o-actualización porque una celda no distingue las dos
    cosas: el usuario escribe un precio donde antes había uno heredado y no
    tiene por qué saber si eso crea una fila o modifica la que había. Un
    POST daría 400 por la restricción de unicidad la segunda vez.

    Cuerpo del PUT:
      {"treatment": uuid, "agreement": uuid | null, "price": "45.00" | null}

    `price: null` **borra** la fila y devuelve la celda a su valor heredado.
    Es la única forma de deshacer un precio pactado sin dejarlo clavado.
    """

    permission_classes = [CAN_VIEW]

    def get_permissions(self):
        return [CAN_MANAGE()] if self.request.method == "PUT" else [CAN_VIEW()]

    def get(self, request):
        return Response(price_matrix(request.tenant))

    def put(self, request):
        treatment_id = request.data.get("treatment")
        agreement_id = request.data.get("agreement") or None
        raw_price = request.data.get("price", None)

        try:
            treatment = Treatment.objects.get(id=treatment_id, tenant=request.tenant)
        except (Treatment.DoesNotExist, ValidationError, ValueError):
            return Response({"detail": "Tratamiento no encontrado."}, status=404)

        agreement = None
        if agreement_id:
            try:
                agreement = Agreement.objects.get(id=agreement_id, tenant=request.tenant)
            except (Agreement.DoesNotExist, ValidationError, ValueError):
                return Response({"detail": "Convenio no encontrado."}, status=404)

        if raw_price in (None, ""):
            deleted, _ = Tariff.objects.filter(
                tenant=request.tenant, treatment=treatment, agreement=agreement
            ).delete()
            return Response({"deleted": bool(deleted)}, status=status.HTTP_200_OK)

        try:
            price = Decimal(str(raw_price))
        except (InvalidOperation, TypeError):
            return Response({"detail": "Precio inválido."}, status=400)
        if price < 0:
            return Response({"detail": "El precio no puede ser negativo."}, status=400)

        tariff, created = Tariff.objects.update_or_create(
            tenant=request.tenant, treatment=treatment, agreement=agreement,
            defaults={"price": price},
        )
        return Response(
            TariffSerializer(tariff).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


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


class PuedeRespaldar(IsClinicAdmin):
    """
    Quién puede generar y abrir copias:

      · la administración de la clínica, la de toda la clínica;
      · cada doctor o auxiliar con la función «respaldo», la de SUS
        pacientes (ver `tenant_backup.collect_profesional`).

    Hereda de `IsClinicAdmin` para que el Super Administrador siga fuera:
    no tiene clínica y no es titular de los datos de ninguna.
    """

    message = "No tienes asignada la función de respaldo en la clínica."

    def has_permission(self, request, view):
        if super().has_permission(request, view):
            return True
        from apps.accounts.funciones import tiene

        u = request.user
        return bool(u and u.is_authenticated and u.tenant_id and not u.is_superuser
                    and u.role in ("doctor", "auxiliary") and tiene(u, "respaldo"))


def _es_admin_de_clinica(request):
    return IsClinicAdmin().has_permission(request, None)


class TenantBackupView(APIView):
    """
    POST /api/v1/config/backup/ — genera la copia cifrada y la devuelve
    como un .zip con la copia y lo necesario para abrirla sin la
    plataforma (instrucciones y herramientas, ver `paquete_respaldo`).

    Cuerpo: {"passphrase": "...", "passphrase_confirm": "..."}

    La administración se lleva la de toda la clínica; un doctor o un
    auxiliar, la de sus pacientes (ver `PuedeRespaldar`).
    """

    permission_classes = [PuedeRespaldar]

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

        from apps.common.paquete_respaldo import empaquetar
        from apps.common.tenant_backup import build_encrypted, suggested_filename

        profesional = None if _es_admin_de_clinica(request) else request.user
        blob, manifest = build_encrypted(request.tenant, passphrase, requested_by=request.user,
                                         profesional=profesional)
        nombre = suggested_filename(request.tenant, profesional)
        paquete = empaquetar(blob, nombre, manifest)

        # Se audita el hecho, nunca la frase: dejarla en el registro
        # anularía el cifrado para cualquiera que lea la auditoría.
        _audit_backup(request, "create_backup", {
            "alcance": manifest["alcance"]["tipo"],
            "total_records": manifest["total_records"],
            "bytes": len(blob),
        })

        response = HttpResponse(paquete, content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{nombre[:-len(".clinicabk")]}.zip"'
        response["X-Backup-Records"] = str(manifest["total_records"])
        return response


class TenantBackupToolsView(APIView):
    """
    GET /api/v1/config/backup/herramientas/ — solo las instrucciones y
    las herramientas de descifrado, sin datos. Para quien tiene una copia
    antigua o perdió el .zip y conserva el .clinicabk.
    """

    permission_classes = [PuedeRespaldar]

    def get(self, request):
        from django.http import HttpResponse

        from apps.common.paquete_respaldo import solo_herramientas

        response = HttpResponse(solo_herramientas(), content_type="application/zip")
        response["Content-Disposition"] = 'attachment; filename="como-descifrar-la-copia.zip"'
        return response


class TenantBackupDecryptView(APIView):
    """
    POST /api/v1/config/backup/decrypt/ — descifra una copia y devuelve
    su contenido legible.

    Envío multipart: `file` (el .clinicabk o el .zip de la descarga) y
    `passphrase`.

    Descifrar NO restaura nada: devuelve la información para consultarla
    o guardarla en claro. Reemplazar la base de datos con una copia es
    una operación destructiva que se hace desde el servidor, con
    `scripts/restore.sh`, y no debe estar a un clic en un panel web.

    La administración abre cualquier copia de su clínica; un profesional,
    solo las suyas.
    """

    permission_classes = [PuedeRespaldar]

    def post(self, request):
        from apps.common.paquete_respaldo import sacar_copia
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
            payload = read_encrypted(sacar_copia(upload.read()), passphrase)
        except BackupError as exc:
            _audit_backup(request, "decrypt_backup_failed", {"reason": str(exc)})
            return Response({"error": {"message": str(exc)}},
                            status=status.HTTP_400_BAD_REQUEST)

        # Una copia de otra clínica no se abre aquí aunque se conozca su
        # frase: cada administración descifra lo suyo.
        manifest = payload.get("manifest", {})
        origin = manifest.get("tenant", {}).get("id")
        if origin and str(origin) != str(request.tenant.id):
            _audit_backup(request, "decrypt_backup_denied", {"origin_tenant": str(origin)})
            return Response(
                {"error": {"message": "Esta copia pertenece a otra clínica y no se puede abrir aquí."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        # Y un profesional, solo las suyas: la de la clínica o la de un
        # colega llevan pacientes que no son suyos.
        alcance = manifest.get("alcance") or {"tipo": "clinica"}
        if not _es_admin_de_clinica(request) and (
                alcance.get("tipo") != "profesional" or alcance.get("user_id") != str(request.user.id)):
            _audit_backup(request, "decrypt_backup_denied", {"alcance": alcance.get("tipo")})
            return Response(
                {"error": {"message": "Esta copia no es tuya: solo puedes abrir las que generaste tú. "
                                      "Pide a la administración de la clínica que la abra."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        _audit_backup(request, "decrypt_backup", {
            "alcance": alcance.get("tipo"),
            "total_records": manifest.get("total_records", 0),
            "generated_at": manifest.get("generated_at", ""),
        })
        return Response(payload)


# ── Módulos que usa la clínica ─────────────────────────────────────────
class ModulosClinicaView(APIView):
    """
    GET/PATCH /api/v1/config/modulos/ — qué módulos usa ESTA clínica.

    Dos llaves distintas. La plataforma decide qué tiene contratado cada
    clínica (Plataforma → Clínicas); la administración de la clínica
    decide, dentro de eso, qué quiere usar: apagar el odontograma 3D o
    las rachas y logros si en su consulta no se usan. Solo puede apagar y
    volver a encender lo contratado: aquí no se da de alta nada.

    Apagar no borra datos; al encenderlo de nuevo todo sigue ahí.
    """

    permission_classes = [IsClinicAdmin]

    def _respuesta(self, tenant):
        from apps.common.funcionalidades import CATALOGO, contratadas, efectivas

        contratado, efectivo = contratadas(tenant), efectivas(tenant)
        return Response([
            {"clave": clave, "nombre": d["nombre"], "descripcion": d["descripcion"],
             "contratado": contratado[clave], "activo": efectivo[clave]}
            for clave, d in CATALOGO.items()
        ])

    def get(self, request):
        return self._respuesta(request.tenant)

    def patch(self, request):
        from apps.common.funcionalidades import CATALOGO, contratadas

        datos = request.data if isinstance(request.data, dict) else {}
        desconocidas = sorted(set(datos) - set(CATALOGO))
        if desconocidas:
            return Response({"detail": f"Módulos desconocidos: {', '.join(desconocidas)}."},
                            status=status.HTTP_400_BAD_REQUEST)
        if any(not isinstance(v, bool) for v in datos.values()):
            return Response({"detail": "Cada módulo va con verdadero o falso."},
                            status=status.HTTP_400_BAD_REQUEST)
        contratado = contratadas(request.tenant)
        sin_contrato = sorted(k for k, v in datos.items() if v and not contratado[k])
        if sin_contrato:
            nombres = ", ".join(CATALOGO[k]["nombre"] for k in sin_contrato)
            return Response(
                {"detail": f"Tu clínica no tiene contratado: {nombres}. "
                           "Pídeselo al administrador de la plataforma."},
                status=status.HTTP_403_FORBIDDEN)

        tenant = request.tenant
        tenant.modulos_clinica = {**(tenant.modulos_clinica or {}), **datos}
        tenant.save(update_fields=["modulos_clinica"])
        from apps.accounts.models import AuditLog

        AuditLog.objects.create(
            tenant=tenant, user=request.user, action="update_modules",
            entity_type="Tenant", entity_id=str(tenant.id), metadata=datos,
        )
        return self._respuesta(tenant)
