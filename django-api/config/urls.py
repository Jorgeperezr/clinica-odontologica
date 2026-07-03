from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.accounts.urls")),
    # Las siguientes apps exponen sus propias rutas a medida que se
    # implementan en los próximos sprints del Roadmap (Sprints 1-11).
    # path("api/v1/", include("apps.patients.urls")),
    # path("api/v1/", include("apps.agenda.urls")),
    # path("api/v1/", include("apps.clinical.urls")),
    # path("api/v1/", include("apps.specialties.urls")),
    # path("api/v1/", include("apps.billing.urls")),
    # path("api/v1/", include("apps.inventory.urls")),
    # path("api/v1/", include("apps.configuration.urls")),
    path("internal/", include("apps.whatsapp.internal_urls")),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/v1/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]
