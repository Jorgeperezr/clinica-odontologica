from django.urls import path

from apps.patients import views

urlpatterns = [
    path("patients/", views.PatientListCreateView.as_view(), name="patient-list"),
    path("patients/<uuid:pk>/", views.PatientDetailView.as_view(), name="patient-detail"),
    path(
        "patients/<uuid:pk>/medical-background/",
        views.MedicalBackgroundView.as_view(),
        name="patient-medical-background",
    ),
    path(
        "patients/<uuid:pk>/documents/<int:doc_id>/file/",
        views.PatientDocumentFileView.as_view(),
        name="patient-document-file",
    ),
    path(
        "patients/<uuid:pk>/documents/<int:doc_id>/",
        views.PatientDocumentDeleteView.as_view(),
        name="patient-document-delete",
    ),
    path(
        "patients/<uuid:pk>/documents/",
        views.PatientDocumentListCreateView.as_view(),
        name="patient-documents",
    ),
    path(
        "patients/<uuid:pk>/treatment-history/",
        views.PatientTreatmentHistoryView.as_view(),
        name="patient-treatment-history",
    ),
]
