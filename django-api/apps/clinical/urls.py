from django.urls import path

from apps.clinical import views

urlpatterns = [
    # Historia clínica
    path("patients/<uuid:pk>/clinical-record/", views.ClinicalRecordView.as_view(), name="clinical-record"),
    path("patients/<uuid:pk>/clinical-record/export-pdf/", views.ClinicalHistoryExportView.as_view(), name="clinical-history-export"),
    path("patients/<uuid:pk>/evolutions/", views.EvolutionListCreateView.as_view(), name="evolution-list"),
    path("evolutions/<uuid:pk>/", views.EvolutionDetailView.as_view(), name="evolution-detail"),
    path("patients/<uuid:pk>/diagnoses/", views.DiagnosisListCreateView.as_view(), name="diagnosis-list"),
    # Planes de tratamiento
    path("patients/<uuid:pk>/treatment-plans/", views.TreatmentPlanListCreateView.as_view(), name="treatment-plan-list"),
    path("treatment-plans/<uuid:pk>/", views.TreatmentPlanDetailView.as_view(), name="treatment-plan-detail"),
    path("treatment-plans/<uuid:pk>/items/", views.TreatmentPlanItemCreateView.as_view(), name="treatment-plan-item-create"),
    path("treatment-plan-items/<uuid:pk>/", views.TreatmentPlanItemUpdateView.as_view(), name="treatment-plan-item-update"),
    # Odontograma
    path("odontogram-states/", views.OdontogramStateListView.as_view(), name="odontogram-state-list"),
    path("patients/<uuid:pk>/tooth-records/", views.ToothRecordListCreateView.as_view(), name="tooth-record-list"),
    path("patients/<uuid:pk>/odontogram/current/", views.CurrentOdontogramView.as_view(), name="odontogram-current"),
    path("tooth-records/<uuid:pk>/", views.ToothRecordDeleteView.as_view(), name="tooth-record-delete"),
    # Radiografías y consentimientos (Sprint 6)
    path("patients/<uuid:pk>/radiographs/", views.RadiographPhotoListCreateView.as_view(), name="radiograph-list"),
    path("patients/<uuid:pk>/consents/", views.InformedConsentListCreateView.as_view(), name="consent-list"),
    path("consents/<uuid:pk>/sign/", views.ConsentSignView.as_view(), name="consent-sign"),
]
