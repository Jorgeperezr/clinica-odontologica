from django.urls import path

from apps.billing import views

urlpatterns = [
    # Presupuestos
    path("patients/<uuid:pk>/budgets/", views.BudgetListCreateView.as_view(), name="budget-list"),
    path("budgets/<uuid:pk>/", views.BudgetDetailView.as_view(), name="budget-detail"),
    path("budgets/<uuid:pk>/items/", views.BudgetItemCreateView.as_view(), name="budget-item-create"),
    path("budgets/<uuid:pk>/approve/", views.BudgetApproveView.as_view(), name="budget-approve"),
    path("budgets/<uuid:pk>/generate-payment-plan/", views.GeneratePaymentPlanView.as_view(), name="generate-payment-plan"),
    # Planes de pago y cuotas
    path("payment-plans/<uuid:pk>/installments/", views.PaymentPlanInstallmentsView.as_view(), name="payment-plan-installments"),
    path("installments/<uuid:pk>/pay/", views.PayInstallmentView.as_view(), name="installment-pay"),
    # Estado de cuenta
    path("patients/<uuid:pk>/account-statement/", views.PatientAccountStatementView.as_view(), name="account-statement"),
    # Honorarios
    path("doctors/<uuid:pk>/fees/", views.DoctorFeeListCreateView.as_view(), name="doctor-fees"),
]
