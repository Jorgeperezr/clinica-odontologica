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
    funcionalidades = serializers.JSONField(required=False)

    class Meta:
        model = Tenant
        fields = ["id", "name", "ruc", "address", "phone", "email",
                  "is_active", "admin", "funcionalidades", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_admin(self, obj):
        admin = _principal_admin(obj)
        if not admin:
            return None
        return {
            "id": str(admin.id), "email": admin.email,
            "full_name": admin.full_name, "is_active": admin.is_active,
            # Se expone para que el panel distinga «le entregué las
            # credenciales» de «la clínica ya tomó posesión de su cuenta».
            # Sin esto, una clínica que nunca entró se ve igual que una que
            # lleva meses trabajando.
            "must_change_password": admin.must_change_password,
        }

    def validate_funcionalidades(self, value):
        """
        Se normaliza SIEMPRE: lo que llegue se recorta al catálogo y lo
        que falte se rellena. Guardar tal cual lo que mande el panel
        dejaría claves inventadas en la base y, peor, clínicas sin
        alguna clave el día que se añada una funcionalidad nueva.
        """
        from apps.common.funcionalidades import normalizar
        return normalizar(value)

    def to_representation(self, instance):
        from apps.common.funcionalidades import normalizar
        datos = super().to_representation(instance)
        # Igual al leer: una clínica creada antes de que existiera una
        # funcionalidad la recibe con su valor por defecto en vez de un
        # hueco que el panel pintaría como «apagada».
        datos["funcionalidades"] = normalizar(instance.funcionalidades)
        return datos

    def validate_name(self, value):
        qs = Tenant.objects.filter(name__iexact=value.strip())
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("Ya existe una clínica con ese nombre.")
        return value.strip()


def _credencial_temporal(usuario):
    """
    Genera la contraseña, la deja puesta y la devuelve UNA vez.

    Nadie la inventa y nadie la guarda en claro. Y se marca la cuenta
    como pendiente de cambio: mientras no elija la suya, lo único que
    puede hacer es elegirla. Sin esa marca, la contraseña que entrega el
    dueño de la plataforma sigue siendo válida para siempre y él la
    conoce, con lo que «entregar las credenciales» no entrega nada.
    """
    temporal = secrets.token_urlsafe(12)
    usuario.set_password(temporal)
    usuario.must_change_password = True
    usuario.save()
    return temporal


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
        from apps.common.funcionalidades import normalizar
        tenant = serializer.save(
            is_active=True,
            funcionalidades=normalizar(serializer.validated_data.get("funcionalidades")),
        )
        # Siembra del catálogo base de la clínica nueva (Sprint 1)
        call_command("bootstrap", tenant_name=tenant.name)
        _audit_platform(self.request, "create_clinic", "Tenant", tenant.id,
                        {"name": tenant.name})
        self._alta_del_administrador(tenant)

    def _alta_del_administrador(self, tenant):
        """
        Si el alta trae los datos del administrador, se crea aquí mismo.

        Dar de alta una clínica eran TRES actos en dos pestañas: crear la
        clínica, ir a «Administradores» a crear su admin inventándole una
        contraseña, y restablecerla para obtener una generada. Son tres
        pasos para un solo acto, y el del medio pedía a una persona que se
        inventara un secreto, que es como se acaban poniendo contraseñas
        como «clinica2026».

        Sigue siendo opcional: quien prefiera crear la clínica ahora y su
        administrador más tarde puede hacerlo como siempre.
        """
        email = str(self.request.data.get("admin_email", "")).strip()
        full_name = str(self.request.data.get("admin_full_name", "")).strip()
        if not email:
            return
        if User.objects.filter(email__iexact=email).exists():
            # La clínica ya está creada: no se deshace, se avisa. Cancelar
            # el alta entera por un correo repetido sería peor.
            self._credenciales = {"error": "Ya existe un usuario con ese correo."}
            return
        admin = User(tenant=tenant, email=email,
                     full_name=full_name or email, role=User.Role.ADMIN)
        temporal = _credencial_temporal(admin)
        _audit_platform(self.request, "create_clinic_admin", "User", admin.id,
                        {"email": admin.email, "clinic": tenant.name})
        self._credenciales = {
            "email": admin.email,
            "temporary_password": temporal,
            "note": ("Entregar por un canal seguro. No se puede volver a "
                     "consultar: al ingresar, la clínica deberá elegir su "
                     "propia contraseña."),
        }

    def create(self, request, *args, **kwargs):
        self._credenciales = None
        respuesta = super().create(request, *args, **kwargs)
        if self._credenciales:
            respuesta.data["admin"] = self._credenciales
        return respuesta


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
        if not email or not full_name:
            return Response(
                {"detail": "email y full_name son obligatorios."}, status=400,
            )
        if User.objects.filter(email__iexact=email).exists():
            return Response({"detail": "Ya existe un usuario con ese correo."}, status=400)
        user = User(tenant=tenant, email=email, full_name=full_name, role=User.Role.ADMIN)
        # La contraseña la genera el sistema y se muestra una vez. Antes se
        # exigía que el Super Administrador escribiera una de 10+
        # caracteres: pedirle a una persona que invente un secreto para
        # otra es como se acaban poniendo contraseñas como «clinica2026»,
        # y además se la queda quien la inventó.
        temporal = _credencial_temporal(user)
        _audit_platform(request, "create_clinic_admin", "User", user.id,
                        {"email": user.email, "clinic": tenant.name})
        return Response({
            "id": str(user.id),
            "email": user.email,
            "temporary_password": temporal,
            "note": ("Entregar por un canal seguro. No se puede volver a "
                     "consultar: al ingresar, deberá elegir su propia "
                     "contraseña."),
        }, status=201)

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

        temp_password = _credencial_temporal(admin)
        _audit_platform(request, "reset_clinic_admin_password", "User", admin.id,
                        {"clinic": tenant.name, "email": admin.email})
        return Response({
            "email": admin.email,
            "temporary_password": temp_password,
            "note": ("Entregar por un canal seguro. No se puede volver a "
                     "consultar: al ingresar, deberá elegir su propia "
                     "contraseña."),
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
