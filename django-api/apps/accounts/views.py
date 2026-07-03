import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts.models import AuditLog, DeviceToken, OTPCode, User
from apps.accounts.serializers import (
    DeviceTokenSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    StaffLoginSerializer,
    UserSerializer,
)
from apps.common.permissions import HasRole
from apps.whatsapp.gateway_client import send_whatsapp_template

OTP_TTL_MINUTES = 5


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


class StaffLoginView(TokenObtainPairView):
    """POST /api/v1/auth/login/ — RF-USR-01"""

    serializer_class = StaffLoginSerializer


class OTPRequestView(APIView):
    """
    POST /api/v1/auth/otp/request/ — RF-USR-02, RF-WSP-01.

    Genera un OTP, lo guarda hasheado, y le pide al microservicio de
    WhatsApp (FastAPI) que lo envíe — Django decide *cuándo/qué*,
    FastAPI decide *cómo* llega a Meta (Arquitectura v1.2, sección 2).
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]

        user, _ = User.objects.get_or_create(
            phone=phone,
            defaults={"role": User.Role.PATIENT, "tenant_id": self._default_tenant_id()},
        )

        code = f"{secrets.randbelow(1_000_000):06d}"
        OTPCode.objects.create(
            user=user,
            code_hash=_hash_code(code),
            purpose=OTPCode.Purpose.LOGIN,
            expires_at=timezone.now() + timedelta(minutes=OTP_TTL_MINUTES),
        )

        send_whatsapp_template(
            to_phone=phone,
            template_name="otp_login",
            language="es",
            variables={"1": code},
            patient_id=str(user.id),
        )

        return Response({"detail": "Código enviado por WhatsApp."}, status=status.HTTP_202_ACCEPTED)

    @staticmethod
    def _default_tenant_id():
        from apps.common.models import Tenant

        tenant = Tenant.objects.filter(is_active=True).first()
        return tenant.id if tenant else None


class OTPVerifyView(APIView):
    """POST /api/v1/auth/otp/verify/ — RF-USR-02"""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        code = serializer.validated_data["code"]

        try:
            user = User.objects.get(phone=phone, role=User.Role.PATIENT)
        except User.DoesNotExist:
            return Response(
                {"detail": "Teléfono o código inválido."}, status=status.HTTP_400_BAD_REQUEST
            )

        otp = (
            OTPCode.objects.filter(user=user, purpose=OTPCode.Purpose.LOGIN, used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if not otp or not otp.is_valid or otp.code_hash != _hash_code(code):
            return Response(
                {"detail": "Teléfono o código inválido."}, status=status.HTTP_400_BAD_REQUEST
            )

        otp.used_at = timezone.now()
        otp.save(update_fields=["used_at"])

        refresh = RefreshToken.for_user(user)
        refresh["role"] = user.role
        refresh["tenant_id"] = str(user.tenant_id)

        return Response(
            {"access": str(refresh.access_token), "refresh": str(refresh), "role": user.role}
        )


class UserListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/users/ — RF-USR-03. Solo Admin gestiona staff."""

    serializer_class = UserSerializer
    permission_classes = [HasRole.for_roles("admin")]

    def get_queryset(self):
        return User.objects.filter(tenant=self.request.tenant).exclude(role=User.Role.PATIENT)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)


class UserDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/users/{id}/ — incluye baja lógica (RF-USR-06)."""

    serializer_class = UserSerializer
    permission_classes = [HasRole.for_roles("admin")]

    def get_queryset(self):
        return User.objects.filter(tenant=self.request.tenant)


class AuditLogListView(generics.ListAPIView):
    """GET /api/v1/audit-logs/ — RF-USR-05"""

    serializer_class = None  # se define en la Fase de implementación completa (serializer simple pendiente)
    permission_classes = [HasRole.for_roles("admin")]
    filterset_fields = ["user", "entity_type", "action"]

    def get_queryset(self):
        return AuditLog.objects.filter(tenant=self.request.tenant).order_by("-created_at")


class DeviceTokenRegisterView(generics.CreateAPIView):
    """POST /me/device-tokens/ — RF-APP-05"""

    serializer_class = DeviceTokenSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
