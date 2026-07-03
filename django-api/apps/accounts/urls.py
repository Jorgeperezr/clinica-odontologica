from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts import views

urlpatterns = [
    path("auth/login/", views.StaffLoginView.as_view(), name="staff-login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/otp/request/", views.OTPRequestView.as_view(), name="otp-request"),
    path("auth/otp/verify/", views.OTPVerifyView.as_view(), name="otp-verify"),
    path("users/", views.UserListCreateView.as_view(), name="user-list"),
    path("users/<uuid:pk>/", views.UserDetailView.as_view(), name="user-detail"),
    path("audit-logs/", views.AuditLogListView.as_view(), name="audit-log-list"),
    path("me/device-tokens/", views.DeviceTokenRegisterView.as_view(), name="device-token-register"),
]
