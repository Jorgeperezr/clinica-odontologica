from django.urls import path

from apps.clinical import views

urlpatterns = [
    path("patients/<uuid:pk>/clinical-record/", views.ClinicalRecordView.as_view(), name="clinical-record"),
    path("patients/<uuid:pk>/evolutions/", views.EvolutionListCreateView.as_view(), name="evolution-list"),
    path("patients/<uuid:pk>/diagnoses/", views.DiagnosisListCreateView.as_view(), name="diagnosis-list"),
    path("patients/<uuid:pk>/treatment-plans/", views.TreatmentPlanListCreateView.as_view(), name="treatment-plan-list"),
    path("treatment-plans/<uuid:pk>/", views.TreatmentPlanDetailView.as_view(), name="treatment-plan-detail"),
    path("treatment-plans/<uuid:pk>/items/", views.TreatmentPlanItemCreateView.as_view(), name="treatment-plan-item-create"),
    path("treatment-plan-items/<uuid:pk>/", views.TreatmentPlanItemUpdateView.as_view(), name="treatment-plan-item-update"),
]
