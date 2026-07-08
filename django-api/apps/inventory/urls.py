from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("products/", views.ProductListCreateView.as_view(), name="product-list"),
    path("products/<uuid:pk>/", views.ProductDetailView.as_view(), name="product-detail"),
    path("products/<uuid:pk>/batches/", views.BatchListCreateView.as_view(), name="batch-list"),
    path("inventory/alerts/low-stock/", views.LowStockAlertView.as_view(), name="low-stock-alert"),
    path("inventory/alerts/expiring/", views.ExpiringBatchAlertView.as_view(), name="expiring-alert"),
    path("inventory/movements/", views.InventoryMovementListView.as_view(), name="inventory-movements"),
]
