import hashlib
import secrets
from datetime import timedelta

from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts.models import (
    AuditLog,
    DeviceToken,
    OTPCode,
    PasswordResetToken,
    User,
)
from apps.accounts.serializers import (
    AuditLogSerializer,
    DeviceTokenSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    StaffLoginSerializer,
    StaffRecoveryConfirmSerializer,
    StaffRecoveryRequestSerializer,
    UserSerializer,
)
from apps.common.permissions import HasRole
from apps.whatsapp.gateway_client import send_whatsapp_template

OTP_TTL_MINUTES = 5
RESET_TTL_MINUTES = 30


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class StaffLoginView(TokenObtainPairView):
    """POST /api/v1/auth/login/ — RF-USR-01"""

    serializer_class = StaffLoginSerializer


class OTPRequestView(APIView):
    """
    POST /api/v1/auth/otp/request/ — RF-USR-02, RF-WSP-01.

    Django decide *cuándo/qué* enviar; el microservicio FastAPI decide
    *cómo* llega a Meta (Arquitectura v1.2, sección 2).
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
        self._issue_and_send_otp(user, phone, OTPCode.Purpose.LOGIN)
        return Response({"detail": "Código enviado por WhatsApp."}, status=status.HTTP_202_ACCEPTED)

    @staticmethod
    def _issue_and_send_otp(user, phone, purpose):
        code = f"{secrets.randbelow(1_000_000):06d}"
        OTPCode.objects.create(
            user=user,
            code_hash=_hash_value(code),
            purpose=purpose,
            expires_at=timezone.now() + timedelta(minutes=OTP_TTL_MINUTES),
        )
        template = "otp_login" if purpose == OTPCode.Purpose.LOGIN else "otp_recovery"
        send_whatsapp_template(
            to_phone=phone,
            template_name=template,
            language="es",
            variables={"1": code},
            patient_id=str(user.id),
        )

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
            return self._invalid()

        otp = (
            OTPCode.objects.filter(user=user, used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if not otp or not otp.is_valid or otp.code_hash != _hash_value(code):
            return self._invalid()

        otp.used_at = timezone.now()
        otp.save(update_fields=["used_at"])

        refresh = RefreshToken.for_user(user)
        refresh["role"] = user.role
        refresh["tenant_id"] = str(user.tenant_id)
        return Response(
            {"access": str(refresh.access_token), "refresh": str(refresh), "role": user.role}
        )

    @staticmethod
    def _invalid():
        return Response(
            {"detail": "Teléfono o código inválido."}, status=status.HTTP_400_BAD_REQUEST
        )


class PatientRecoveryView(OTPRequestView):
    """
    POST /api/v1/auth/patient-recovery/ — RF-USR-04 (paciente).
    La recuperación de acceso de un paciente es simplemente reenviar un
    OTP; reutiliza toda la lógica de OTPRequestView pero solo para un
    paciente que ya existe (no crea usuarios nuevos).
    """

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        try:
            user = User.objects.get(phone=phone, role=User.Role.PATIENT)
        except User.DoesNotExist:
            # No revelamos si el teléfono existe o no (buena práctica de seguridad).
            return Response({"detail": "Si el número está registrado, recibirás un código."})
        self._issue_and_send_otp(user, phone, OTPCode.Purpose.RECOVERY)
        return Response({"detail": "Si el número está registrado, recibirás un código."})


class StaffRecoveryRequestView(APIView):
    """POST /api/v1/auth/recovery/request/ — RF-USR-04 (staff, por correo)."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = StaffRecoveryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            return Response({"detail": "Si el correo existe, recibirás instrucciones."})

        if user.role == User.Role.PATIENT:
            return Response({"detail": "Si el correo existe, recibirás instrucciones."})

        raw_token = secrets.token_urlsafe(32)
        PasswordResetToken.objects.create(
            user=user,
            token_hash=_hash_value(raw_token),
            expires_at=timezone.now() + timedelta(minutes=RESET_TTL_MINUTES),
        )
        # En producción, el enlace apunta al panel Next.js; por ahora se
        # envía el token para que el frontend arme la URL de reseteo.
        send_mail(
            subject="Recuperación de acceso — Clínica",
            message=f"Usa este código para restablecer tu contraseña: {raw_token}",
            from_email=None,
            recipient_list=[email],
            fail_silently=True,
        )
        return Response({"detail": "Si el correo existe, recibirás instrucciones."})


class StaffRecoveryConfirmView(APIView):
    """POST /api/v1/auth/recovery/confirm/ — RF-USR-04."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = StaffRecoveryConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        reset = (
            PasswordResetToken.objects.filter(
                token_hash=_hash_value(raw_token), used_at__isnull=True
            )
            .order_by("-created_at")
            .first()
        )
        if not reset or not reset.is_valid:
            return Response(
                {"detail": "El enlace de recuperación es inválido o expiró."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = reset.user
        user.set_password(new_password)
        user.save(update_fields=["password"])
        reset.used_at = timezone.now()
        reset.save(update_fields=["used_at"])
        return Response({"detail": "Contraseña actualizada correctamente."})


class UserListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/users/ — RF-USR-03. Solo Admin gestiona staff."""

    serializer_class = UserSerializer
    permission_classes = [HasRole.for_roles("admin")]
    filterset_fields = ["role", "is_active"]

    def get_queryset(self):
        return User.objects.filter(tenant=self.request.tenant).exclude(role=User.Role.PATIENT).order_by("email")

    def perform_create(self, serializer):
        user = serializer.save(tenant=self.request.tenant)
        # Si el nuevo usuario es doctor, crear su perfil Doctor para que
        # aparezca en la agenda y pueda registrar actos clínicos atribuidos.
        if user.role == User.Role.DOCTOR:
            from apps.agenda.models import Doctor

            Doctor.objects.get_or_create(tenant=self.request.tenant, user=user)


class UserDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/users/{id}/ — incluye baja lógica (RF-USR-06)."""

    serializer_class = UserSerializer
    permission_classes = [HasRole.for_roles("admin")]

    def get_queryset(self):
        return User.objects.filter(tenant=self.request.tenant)


class AuditLogListView(generics.ListAPIView):
    """GET /api/v1/audit-logs/ — RF-USR-05"""

    serializer_class = AuditLogSerializer
    permission_classes = [HasRole.for_roles("admin")]
    filterset_fields = ["user", "entity_type", "action"]

    def get_queryset(self):
        return AuditLog.objects.filter(tenant=self.request.tenant).order_by("-created_at")


class DeviceTokenRegisterView(generics.CreateAPIView):
    """POST /me/device-tokens/ — RF-APP-05"""

    serializer_class = DeviceTokenSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # upsert: si el token ya existe, lo reactiva en vez de duplicar
        token = serializer.validated_data["fcm_token"]
        DeviceToken.objects.update_or_create(
            fcm_token=token,
            defaults={
                "user": self.request.user,
                "platform": serializer.validated_data["platform"],
                "is_active": True,
            },
        )


class MeView(APIView):
    """
    GET /api/v1/auth/me/ — perfil del usuario autenticado.
    El panel web lo usa tras el login para conocer nombre y rol
    (la navegación se filtra por rol en el cliente).
    """

    def get(self, request):
        u = request.user
        return Response({
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
        })
