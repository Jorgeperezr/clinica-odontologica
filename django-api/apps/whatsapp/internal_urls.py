from django.urls import path

from apps.whatsapp.internal_views import WhatsAppEventView

urlpatterns = [
    path("whatsapp/events/", WhatsAppEventView.as_view(), name="whatsapp-internal-events"),
]
