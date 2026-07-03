from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import AuditLog, DeviceToken, User


class StaffLoginSerializer(TokenObtainPairSerializer):
    """POST /auth/login/ — RF-USR-01. Rechaza explícitamente a pacientes:
    ellos usan el flujo de OTP (StaffLoginSerializer no aplica a role=patient)."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["tenant_id"] = str(user.tenant_id)
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        if self.user.role == User.Role.PATIENT:
            raise serializers.ValidationError(
                "Los pacientes deben ingresar con el código OTP enviado por WhatsApp."
            )
        if not self.user.is_active:
            raise serializers.ValidationError("Este usuario está desactivado.")
        data["role"] = self.user.role
        return data


class OTPRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)


class OTPVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=10)


class StaffRecoveryRequestSerializer(serializers.Serializer):
    """POST /auth/recovery/request/ — RF-USR-04 (staff, por correo)."""

    email = serializers.EmailField()


class StaffRecoveryConfirmSerializer(serializers.Serializer):
    """POST /auth/recovery/confirm/ — RF-USR-04."""

    token = serializers.CharField()
    new_password = serializers.CharField(min_length=10, write_only=True)


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=10)

    class Meta:
        model = User
        fields = ["id", "email", "phone", "role", "is_active", "password", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_role(self, value):
        # Un usuario de staff no puede crearse con rol 'patient' desde este
        # endpoint administrativo; los pacientes se crean por el flujo de OTP.
        if value == User.Role.PATIENT:
            raise serializers.ValidationError(
                "Los pacientes no se crean desde la gestión de usuarios de staff."
            )
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
        return user


class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = [
            "id", "user", "user_email", "action", "entity_type",
            "entity_id", "ip_address", "metadata", "created_at",
        ]
        read_only_fields = fields


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ["id", "fcm_token", "platform", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]
