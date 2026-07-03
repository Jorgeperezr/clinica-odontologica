from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import DeviceToken, User


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


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "phone", "role", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ["id", "fcm_token", "platform", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]
