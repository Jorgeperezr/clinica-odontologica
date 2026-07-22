from django.urls import path

from apps.clinical import form033_views, sprint22_views, views

urlpatterns = [
    # Historia clínica
    path("patients/<uuid:pk>/clinical-record/", views.ClinicalRecordView.as_view(), name="clinical-record"),
    path("patients/<uuid:pk>/clinical-record/export-pdf/", views.ClinicalHistoryExportView.as_view(), name="clinical-history-export"),
    path("patients/<uuid:pk>/evolutions/", views.EvolutionListCreateView.as_view(), name="evolution-list"),
    path("evolutions/<uuid:pk>/", views.EvolutionDetailView.as_view(), name="evolution-detail"),
    # Sprint 22
    # Formulario MSP 033 (Sprint 23)
    path("patients/<uuid:pk>/form033/", form033_views.Form033ListCreateView.as_view(), name="form033-list"),
    path("form033/<uuid:pk>/", form033_views.Form033DetailView.as_view(), name="form033-detail"),
    path("cie10/", form033_views.Cie10SearchView.as_view(), name="cie10-search"),
    path("patients/<uuid:pk>/cpo-ceo/", form033_views.CpoCeoIndexView.as_view(), name="cpo-ceo-index"),
    path("patients/<uuid:pk>/exam-requests/<uuid:exam_id>/pdf/", form033_views.ExamRequestPDFView.as_view(), name="exam-request-pdf"),
    path("patients/<uuid:pk>/form033/export-pdf/", form033_views.Form033PDFExportView.as_view(), name="form033-export-pdf"),
    path("patients/<uuid:pk>/form033/export-xlsx/", form033_views.Form033XlsxExportView.as_view(), name="form033-export-xlsx"),
    path("patients/<uuid:pk>/exam-requests/", form033_views.ExamRequestListCreateView.as_view(), name="exam-request-list"),
    path("exam-requests/<uuid:pk>/report/", form033_views.ExamRequestReportView.as_view(), name="exam-request-report"),
    path("clinical/plan-templates/", sprint22_views.TemplateListCreateView.as_view(), name="plan-templates"),
    path("clinical/plan-templates/<uuid:pk>/items/", sprint22_views.TemplateItemCreateView.as_view(), name="plan-template-item-create"),
    path("clinical/plan-template-items/<uuid:pk>/", sprint22_views.TemplateItemDeleteView.as_view(), name="plan-template-item-delete"),
    path("patients/<uuid:pk>/apply-plan-template/", sprint22_views.ApplyTemplateView.as_view(), name="apply-plan-template"),
    path("treatment-plans/<uuid:pk>/generate-budget/", sprint22_views.PlanToBudgetView.as_view(), name="plan-to-budget"),
    path("clinical/follow-ups/", sprint22_views.FollowUpAlertsView.as_view(), name="follow-up-alerts"),
    path("evolutions/<uuid:pk>/prescription-pdf/", sprint22_views.PrescriptionPDFView.as_view(), name="prescription-pdf"),
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
    path("consents/<uuid:pk>/detail/", views.ConsentDetailView.as_view(), name="consent-detail"),
    path("consents/<uuid:pk>/pdf/", form033_views.ConsentPDFView.as_view(), name="consent-pdf"),
    path("consent-templates/", views.ConsentTemplateListCreateView.as_view(), name="consent-template-list"),
    path("consent-templates/<uuid:pk>/", views.ConsentTemplateDetailView.as_view(), name="consent-template-detail"),
]
