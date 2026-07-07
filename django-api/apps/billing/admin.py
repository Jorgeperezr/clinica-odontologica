from django.contrib import admin

from apps.billing.models import (
    Budget,
    BudgetItem,
    DoctorFee,
    Installment,
    Payment,
    PaymentPlan,
)


class BudgetItemInline(admin.TabularInline):
    model = BudgetItem
    extra = 0


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ["patient", "status", "total_amount", "created_at"]
    list_filter = ["status", "tenant"]
    inlines = [BudgetItemInline]


class InstallmentInline(admin.TabularInline):
    model = Installment
    extra = 0


@admin.register(PaymentPlan)
class PaymentPlanAdmin(admin.ModelAdmin):
    list_display = ["patient", "installment_count", "total_amount", "created_at"]
    list_filter = ["tenant"]
    inlines = [InstallmentInline]


@admin.register(Installment)
class InstallmentAdmin(admin.ModelAdmin):
    list_display = ["patient", "number", "due_date", "amount", "status"]
    list_filter = ["status", "tenant"]
    date_hierarchy = "due_date"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["patient", "amount", "method", "date"]
    list_filter = ["method", "tenant"]
    date_hierarchy = "date"


admin.site.register(DoctorFee)
