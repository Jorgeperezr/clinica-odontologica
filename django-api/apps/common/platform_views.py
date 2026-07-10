"""
Panel de plataforma (SaaS) — Sprint 21, según especificación:

    Super Administrador (plataforma) — SOLO administra la plataforma:
    1. Dashboard: clínicas totales / activas / suspendidas, admins de clínica.
    2. Gestión de Clínicas: registrar, editar datos generales, activar/
       suspender, credenciales del administrador.
    3. Administradores de Clínicas: solo el admin principal de cada una
       (restablecer contraseña, activar/desactivar, actualizar correo).
    4. Auditoría: solo las acciones del propio Super Administrador.
    5. Configuración General de la plataforma.

PRINCIPIO DE AISLAMIENTO: el Super Administrador NO accede a información
operativa de las clínicas (pacientes, historias, citas, pagos). Ningún
endpoint de este módulo expone esos datos, y los endpoints operativos lo
rechazan por rol (verificado por tests).
"""

import secrets

from django.core.management import call_command
from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AuditLog, User
from apps.common.models import PlatformConfiguration, Tenant
from apps.common.permissions import HasRole

IS_SUPERADMIN = HasRole.for_roles("superadmin")

# Acciones de plataforma que aparecen en el módulo de Auditoría
PLATFORM_ACTIONS = [
    "create_clinic", "update_clinic", "activate_clinic", "deactivate_clinic",
    "create_clinic_admin", "update_clinic_admin", "reset_clinic_admin_password",
    "update_platform_config",
]


def _audit_platform(request, action, entity_type, entity_id, metadata=None):
    AuditLog.objects.create(
        tenant=None,  # acciones de plataforma: no pertenecen a una clínica
        user=request.user,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        metadata=metadata or {},
    )


def _principal_admin(tenant):
    """El administrador principal: el admin más antiguo de la clínica."""
    return (
        User.objects.filter(tenant=tenant, role=User.Role.ADMIN)
        .order_by("created_at")
        .first()
    )


# ─────────────────────────── Clínicas ───────────────────────────

class ClinicSerializer(serializers.ModelSerializer):
    admin = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = ["id", "name", "ruc", "address", "phone", "email",
                  "is_active", "admin", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_admin(self, obj):
        admin = _principal_admin(obj)
        if not admin:
            return None
        return {
            "id": str(admin.id), "email": admin.email,
            "full_name": admin.full_name, "is_active": admin.is_active,
        }

    def validate_name(self, value):
        qs = Tenant.objects.filter(name__iexact=value.strip())
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("Ya existe una clínica con ese nombre.")
        return value.strip()


class ClinicListCreateView(generics.ListCreateAPIView):
    serializer_class = ClinicSerializer
    permission_classes = [IS_SUPERADMIN]
    pagination_class = None

    def get_queryset(self):
        return Tenant.objects.order_by("name")

    def perform_create(self, serializer):
        # Una clínica nueva SIEMPRE nace activa; suspenderla es una acción
        # explícita posterior (PATCH). Esto también neutraliza la semántica
        # de checkbox de los formularios (boolean ausente = False).
        tenant = serializer.save(is_active=True)
        # Siembra del catálogo base de la clínica nueva (Sprint 1)
        call_command("bootstrap", tenant_name=tenant.name)
        _audit_platform(self.request, "create_clinic", "Tenant", tenant.id,
                        {"name": tenant.name})


class ClinicDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ClinicSerializer
    permission_classes = [IS_SUPERADMIN]
    queryset = Tenant.objects.all()

    def perform_update(self, serializer):
        previous_active = serializer.instance.is_active
        tenant = serializer.save()
        if previous_active != tenant.is_active:
            action = "activate_clinic" if tenant.is_active else "deactivate_clinic"
        else:
            action = "update_clinic"
        _audit_platform(self.request, action, "Tenant", tenant.id, {"name": tenant.name})


# ──────────────── Administradores de clínica ────────────────

class ClinicAdminView(APIView):
    """
    GET   → datos del administrador principal de la clínica.
    POST  → crear el administrador (si la clínica no tiene).
    PATCH → actualizar correo / activar-desactivar la cuenta.
    """

    permission_classes = [IS_SUPERADMIN]

    def _tenant(self, pk):
        try:
            return Tenant.objects.get(pk=pk)
        except Tenant.DoesNotExist:
            return None

    def get(self, request, pk):
        tenant = self._tenant(pk)
        if not tenant:
            return Response({"detail": "Clínica no encontrada."}, status=404)
        admin = _principal_admin(tenant)
        if not admin:
            return Response({"admin": None})
        return Response({"admin": {
            "id": str(admin.id), "email": admin.email,
            "full_name": admin.full_name, "is_active": admin.is_active,
        }})

    def post(self, request, pk):
        tenant = self._tenant(pk)
        if not tenant:
            return Response({"detail": "Clínica no encontrada."}, status=404)
        if _principal_admin(tenant):
            return Response(
                {"detail": "La clínica ya tiene administrador. Usa restablecer contraseña o actualizar correo."},
                status=400,
            )
        email = str(request.data.get("email", "")).strip()
        full_name = str(request.data.get("full_name", "")).strip()
        password = str(request.data.get("password", ""))
        if not email or not full_name or len(password) < 10:
            return Response(
                {"detail": "email, full_name y password (10+ caracteres) son obligatorios."},
                status=400,
            )
        if User.objects.filter(email__iexact=email).exists():
            return Response({"detail": "Ya existe un usuario con ese correo."}, status=400)
        user = User(tenant=tenant, email=email, full_name=full_name, role=User.Role.ADMIN)
        user.set_password(password)
        user.save()
        _audit_platform(request, "create_clinic_admin", "User", user.id,
                        {"email": user.email, "clinic": tenant.name})
        return Response({"id": str(user.id), "email": user.email}, status=201)

    def patch(self, request, pk):
        tenant = self._tenant(pk)
        if not tenant:
            return Response({"detail": "Clínica no encontrada."}, status=404)
        admin = _principal_admin(tenant)
        if not admin:
            return Response({"detail": "La clínica no tiene administrador."}, status=404)

        changes = {}
        if "email" in request.data:
            new_email = str(request.data["email"]).strip()
            if User.objects.filter(email__iexact=new_email).exclude(id=admin.id).exists():
                return Response({"detail": "Ese correo ya está en uso."}, status=400)
            changes["previous_email"] = admin.email
            admin.email = new_email
        if "is_active" in request.data:
            raw = request.data["is_active"]
            admin.is_active = raw in (True, 1, "1", "true", "True", "TRUE")
            changes["is_active"] = admin.is_active
        admin.save()
        _audit_platform(request, "update_clinic_admin", "User", admin.id,
                        {"clinic": tenant.name, **changes})
        return Response({"admin": {
            "id": str(admin.id), "email": admin.email,
            "full_name": admin.full_name, "is_active": admin.is_active,
        }})


class ClinicAdminResetPasswordView(APIView):
    """
    POST /platform/clinics/{pk}/admin/reset-password/ — genera una
    contraseña temporal segura y la devuelve UNA sola vez (no se guarda
    en claro en ningún lado). El Super Administrador se la entrega al
    admin de la clínica por un canal seguro.
    """

    permission_classes = [IS_SUPERADMIN]

    def post(self, request, pk):
        try:
            tenant = Tenant.objects.get(pk=pk)
        except Tenant.DoesNotExist:
            return Response({"detail": "Clínica no encontrada."}, status=404)
        admin = _principal_admin(tenant)
        if not admin:
            return Response({"detail": "La clínica no tiene administrador."}, status=404)

        temp_password = secrets.token_urlsafe(12)
        admin.set_password(temp_password)
        admin.save(update_fields=["password"])
        _audit_platform(request, "reset_clinic_admin_password", "User", admin.id,
                        {"clinic": tenant.name, "email": admin.email})
        return Response({
            "email": admin.email,
            "temporary_password": temp_password,
            "note": "Entregar por un canal seguro. No se puede volver a consultar.",
        })


# ─────────────────────────── Dashboard ───────────────────────────

class PlatformOverviewView(APIView):
    """Dashboard del Super Administrador — SOLO datos de plataforma."""

    permission_classes = [IS_SUPERADMIN]

    def get(self, request):
        clinics = Tenant.objects.all()
        return Response({
            "clinics_total": clinics.count(),
            "clinics_active": clinics.filter(is_active=True).count(),
            "clinics_suspended": clinics.filter(is_active=False).count(),
            "clinic_admins_total": User.objects.filter(role=User.Role.ADMIN).count(),
        })


# ─────────────────────────── Auditoría ───────────────────────────

class PlatformAuditView(APIView):
    """Solo las acciones realizadas por el Super Administrador."""

    permission_classes = [IS_SUPERADMIN]

    def get(self, request):
        logs = (
            AuditLog.objects.filter(
                user__role=User.Role.SUPERADMIN,
                action__in=PLATFORM_ACTIONS,
            )
            .select_related("user")
            .order_by("-created_at")[:200]
        )
        return Response({"results": [{
            "id": str(log.id),
            "user": log.user.email if log.user else None,
            "action": log.action,
            "entity_type": log.entity_type,
            "metadata": log.metadata,
            "created_at": log.created_at.isoformat(),
        } for log in logs]})


# ──────────────────── Configuración general ────────────────────

class PlatformConfigSerializer(serializers.ModelSerializer):
    smtp_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    smtp_password_set = serializers.SerializerMethodField()

    class Meta:
        model = PlatformConfiguration
        fields = ["platform_name", "logo_url", "smtp_host", "smtp_port", "smtp_user",
                  "smtp_password", "smtp_password_set", "timezone", "currency", "updated_at"]
        read_only_fields = ["updated_at"]

    def get_smtp_password_set(self, obj):
        return bool(obj.smtp_password)


class PlatformConfigView(APIView):
    permission_classes = [IS_SUPERADMIN]

    def get(self, request):
        return Response(PlatformConfigSerializer(PlatformConfiguration.get_solo()).data)

    def patch(self, request):
        config = PlatformConfiguration.get_solo()
        serializer = PlatformConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _audit_platform(request, "update_platform_config", "PlatformConfiguration",
                        config.id, {"fields": list(request.data.keys())})
        return Response(PlatformConfigSerializer(config).data)
