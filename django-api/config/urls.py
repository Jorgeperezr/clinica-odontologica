from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.common.urls")),
    path("api/v1/", include("apps.accounts.urls")),
    # Las siguientes apps exponen sus propias rutas a medida que se
    # implementan en los próximos sprints del Roadmap (Sprints 1-11).
    path("api/v1/", include("apps.patients.urls")),
    path("api/v1/", include("apps.agenda.urls")),
    path("api/v1/", include("apps.clinical.urls")),
    path("api/v1/", include("apps.specialties.urls")),
    path("api/v1/", include("apps.billing.urls")),
    path("api/v1/", include("apps.inventory.urls")),
    path("api/v1/", include("apps.configuration.urls")),
    path("api/v1/", include("apps.whatsapp.urls")),
    path("internal/", include("apps.whatsapp.internal_urls")),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/v1/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]

# Archivos subidos (logos, documentos, firmas) servidos por Django en
# desarrollo; en producción los sirve el proxy o el bucket.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
