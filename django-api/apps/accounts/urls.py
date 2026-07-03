from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts import views

urlpatterns = [
    # Autenticación — RF-USR-01, 02, 04
    path("auth/login/", views.StaffLoginView.as_view(), name="staff-login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/otp/request/", views.OTPRequestView.as_view(), name="otp-request"),
    path("auth/otp/verify/", views.OTPVerifyView.as_view(), name="otp-verify"),
    path("auth/patient-recovery/", views.PatientRecoveryView.as_view(), name="patient-recovery"),
    path("auth/recovery/request/", views.StaffRecoveryRequestView.as_view(), name="recovery-request"),
    path("auth/recovery/confirm/", views.StaffRecoveryConfirmView.as_view(), name="recovery-confirm"),
    # Gestión de usuarios — RF-USR-03, 06
    path("users/", views.UserListCreateView.as_view(), name="user-list"),
    path("users/<uuid:pk>/", views.UserDetailView.as_view(), name="user-detail"),
    # Auditoría — RF-USR-05
    path("audit-logs/", views.AuditLogListView.as_view(), name="audit-log-list"),
    # App móvil — RF-APP-05
    path("me/device-tokens/", views.DeviceTokenRegisterView.as_view(), name="device-token-register"),
]
