from django.utils import timezone
from datetime import timedelta

from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import HasRole
from apps.inventory.models import Batch, InventoryMovement, Product
from apps.inventory.serializers import (
    BatchSerializer,
    InventoryMovementSerializer,
    ProductSerializer,
)

CAN_MANAGE = HasRole.for_roles("admin", "auxiliary")
CAN_VIEW = HasRole.for_roles("admin", "auxiliary", "doctor", "reception")


class ProductListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/products/ — RF-INV-01."""

    serializer_class = ProductSerializer
    filterset_fields = ["is_active"]

    def get_permissions(self):
        return [CAN_MANAGE()] if self.request.method == "POST" else [CAN_VIEW()]

    def get_queryset(self):
        return Product.objects.filter(
            tenant=self.request.tenant
        ).prefetch_related("batches").order_by("name")

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)


class ProductDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [CAN_MANAGE]

    def get_queryset(self):
        return Product.objects.filter(tenant=self.request.tenant).prefetch_related("batches")


class BatchListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/products/{id}/batches/ — RF-INV-02."""

    serializer_class = BatchSerializer
    permission_classes = [CAN_MANAGE]

    def get_queryset(self):
        return Batch.objects.filter(
            product_id=self.kwargs["pk"], tenant=self.request.tenant
        ).order_by("expiration_date")

    def perform_create(self, serializer):
        product = generics.get_object_or_404(
            Product, pk=self.kwargs["pk"], tenant=self.request.tenant
        )
        batch = serializer.save(tenant=self.request.tenant, product=product)
        # Registrar el ingreso como movimiento de entrada
        InventoryMovement.objects.create(
            tenant=self.request.tenant, product=product, batch=batch,
            movement_type=InventoryMovement.MovementType.IN,
            quantity=batch.quantity, reason=InventoryMovement.Reason.PURCHASE,
        )


class LowStockAlertView(APIView):
    """GET /api/v1/inventory/alerts/low-stock/ — RF-INV-03."""

    permission_classes = [CAN_VIEW]

    def get(self, request):
        products = Product.objects.filter(
            tenant=request.tenant, is_active=True
        ).prefetch_related("batches")
        low = [
            {
                "product_id": str(p.id),
                "name": p.name,
                "current_stock": str(p.current_stock),
                "min_stock": str(p.min_stock),
            }
            for p in products if p.is_low_stock
        ]
        return Response({"low_stock_products": low})


class ExpiringBatchAlertView(APIView):
    """GET /api/v1/inventory/alerts/expiring/?days=30 — RF-INV-04."""

    permission_classes = [CAN_VIEW]

    def get(self, request):
        try:
            days = int(request.query_params.get("days", 30))
        except ValueError:
            days = 30
        limit_date = timezone.now().date() + timedelta(days=days)

        batches = Batch.objects.filter(
            tenant=request.tenant,
            quantity__gt=0,
            expiration_date__isnull=False,
            expiration_date__lte=limit_date,
        ).select_related("product").order_by("expiration_date")

        result = [
            {
                "batch_id": str(b.id),
                "product_name": b.product.name,
                "batch_number": b.batch_number,
                "quantity": str(b.quantity),
                "expiration_date": str(b.expiration_date),
                "days_to_expiry": (b.expiration_date - timezone.now().date()).days,
            }
            for b in batches
        ]
        return Response({"expiring_batches": result})


class InventoryMovementListView(generics.ListAPIView):
    """GET /api/v1/inventory/movements/ — historial completo."""

    serializer_class = InventoryMovementSerializer
    permission_classes = [CAN_VIEW]
    filterset_fields = ["product", "movement_type", "reason"]

    def get_queryset(self):
        return InventoryMovement.objects.filter(
            tenant=self.request.tenant
        ).select_related("product").order_by("-date")
