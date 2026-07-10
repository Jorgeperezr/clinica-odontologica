"""
Panel de plataforma (SaaS): endpoints exclusivos del Super Administrador
para gestionar las clínicas (tenants) del sistema.

Jerarquía:
    Super Administrador (sin clínica)
    └── Clínica A/B/C… (tenant)
        └── Administrador, Doctores, Recepción, Auxiliares (staff del tenant)

El Super Administrador NO opera dentro de las clínicas: crea la clínica,
crea a su primer Administrador, y puede activarla/desactivarla. Todo lo
demás (pacientes, agenda, pagos) pertenece al staff de cada clínica y
queda aislado por tenant.
"""

from django.core.management import call_command
from django.db.models import Count, Q
from rest_framework import generics, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AuditLog, User
from apps.common.models import Tenant
from apps.common.permissions import HasRole

IS_SUPERADMIN = HasRole.for_roles("superadmin")


class ClinicSerializer(serializers.ModelSerializer):
    staff_count = serializers.IntegerField(read_only=True)
    patient_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Tenant
        fields = ["id", "name", "ruc", "is_active", "staff_count", "patient_count", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_name(self, value):
        qs = Tenant.objects.filter(name__iexact=value.strip())
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("Ya existe una clínica con ese nombre.")
        return value.strip()


class ClinicAdminSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=150)
    password = serializers.CharField(min_length=10, write_only=True)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Ya existe un usuario con ese correo.")
        return value


def _clinic_queryset():
    return Tenant.objects.annotate(
        staff_count=Count("users", filter=~Q(users__role=User.Role.PATIENT), distinct=True),
        patient_count=Count("patients", distinct=True),
    ).order_by("name")


class ClinicListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/platform/clinics/ — solo Super Administrador."""

    serializer_class = ClinicSerializer
    permission_classes = [IS_SUPERADMIN]
    pagination_class = None

    def get_queryset(self):
        return _clinic_queryset()

    def perform_create(self, serializer):
        tenant = serializer.save()
        # Sembrar el catálogo base de la clínica nueva (especialidades,
        # parámetros del sistema y los 12 estados del odontograma) —
        # el mismo bootstrap del Sprint 1, por clínica.
        call_command("bootstrap", tenant_name=tenant.name)
        AuditLog.objects.create(
            tenant=tenant, user=self.request.user,
            action="create_clinic", entity_type="Tenant", entity_id=str(tenant.id),
            metadata={"name": tenant.name},
        )


class ClinicDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/platform/clinics/{id}/ — activar/desactivar, renombrar."""

    serializer_class = ClinicSerializer
    permission_classes = [IS_SUPERADMIN]

    def get_queryset(self):
        return _clinic_queryset()

    def perform_update(self, serializer):
        previous_active = serializer.instance.is_active
        tenant = serializer.save()
        if previous_active != tenant.is_active:
            AuditLog.objects.create(
                tenant=tenant, user=self.request.user,
                action="activate_clinic" if tenant.is_active else "deactivate_clinic",
                entity_type="Tenant", entity_id=str(tenant.id),
                metadata={"name": tenant.name},
            )


class ClinicAdminCreateView(APIView):
    """POST /api/v1/platform/clinics/{pk}/admin/ — crear el Administrador de una clínica."""

    permission_classes = [IS_SUPERADMIN]

    def post(self, request, pk):
        try:
            tenant = Tenant.objects.get(pk=pk)
        except Tenant.DoesNotExist:
            return Response({"detail": "Clínica no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ClinicAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User(
            tenant=tenant,
            email=serializer.validated_data["email"],
            full_name=serializer.validated_data["full_name"],
            role=User.Role.ADMIN,
        )
        user.set_password(serializer.validated_data["password"])
        user.save()
        AuditLog.objects.create(
            tenant=tenant, user=request.user,
            action="create_clinic_admin", entity_type="User", entity_id=str(user.id),
            metadata={"email": user.email, "clinic": tenant.name},
        )
        return Response(
            {"id": str(user.id), "email": user.email, "full_name": user.full_name, "role": user.role},
            status=status.HTTP_201_CREATED,
        )


class PlatformOverviewView(APIView):
    """GET /api/v1/platform/overview/ — indicadores globales del SaaS."""

    permission_classes = [IS_SUPERADMIN]

    def get(self, request):
        from apps.patients.models import Patient

        clinics = Tenant.objects.all()
        return Response({
            "clinics_total": clinics.count(),
            "clinics_active": clinics.filter(is_active=True).count(),
            "staff_total": User.objects.exclude(role=User.Role.PATIENT)
                                       .exclude(role=User.Role.SUPERADMIN).count(),
            "patients_total": Patient.objects.count(),
        })
