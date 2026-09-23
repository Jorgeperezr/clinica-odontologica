from django.urls import path

from apps.whatsapp import config_views, views

urlpatterns = [
    path("config/whatsapp/", config_views.ConfiguracionWhatsAppView.as_view(),
         name="whatsapp-configuracion"),
    path("config/whatsapp-templates/", views.WhatsAppTemplateListCreateView.as_view(), name="whatsapp-template-list"),
    path("patients/<uuid:pk>/whatsapp-optin/", views.WhatsAppOptInListCreateView.as_view(), name="whatsapp-optin-list"),
    path("whatsapp-optin/<uuid:pk>/revoke/", views.WhatsAppOptInRevokeView.as_view(), name="whatsapp-optin-revoke"),
]
