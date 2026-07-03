from django.urls import path

from apps.configuration import views

urlpatterns = [
    path("config/treatments/", views.TreatmentListCreateView.as_view(), name="treatment-list"),
    path("config/treatments/<uuid:pk>/", views.TreatmentDetailView.as_view(), name="treatment-detail"),
    path("config/agreements/", views.AgreementListCreateView.as_view(), name="agreement-list"),
    path("config/agreements/<uuid:pk>/", views.AgreementDetailView.as_view(), name="agreement-detail"),
    path("config/tarifarios/", views.TariffListCreateView.as_view(), name="tariff-list"),
    path("config/tarifarios/<uuid:pk>/", views.TariffDetailView.as_view(), name="tariff-detail"),
    path("config/parameters/", views.SystemParameterListView.as_view(), name="parameter-list"),
    path("config/parameters/<uuid:pk>/", views.SystemParameterDetailView.as_view(), name="parameter-detail"),
]
