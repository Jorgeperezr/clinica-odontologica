"""
Lógica de negocio de inventario: descuento automático de stock al
completar un tratamiento (RF-INV-05). Centralizado para que la
historia clínica (al marcar un ítem como 'done') lo invoque sin
duplicar reglas.
"""

from django.db import transaction


@transaction.atomic
def consume_inventory_for_treatment_item(treatment_plan_item):
    """
    Descuenta del inventario los insumos que consume el tratamiento de un
    TreatmentPlanItem que se marcó como realizado. Usa FEFO (primero el
    lote que vence antes). Registra cada consumo como InventoryMovement.
    Silencioso si el tratamiento no consume insumos.
    """
    from apps.inventory.models import Batch, InventoryMovement

    treatment = treatment_plan_item.treatment
    tenant = treatment_plan_item.treatment_plan.tenant

    # ¿Este tratamiento tiene insumos asociados? (TreatmentInventoryItem
    # se define en configuration; si no existe la relación, no hay consumo)
    inventory_items = getattr(treatment, "inventory_items", None)
    if inventory_items is None:
        return {"consumed": 0}

    consumed_count = 0
    for inv_item in inventory_items.all():
        product = inv_item.product
        needed = inv_item.quantity_used

        # FEFO: descontar de los lotes que vencen primero
        batches = Batch.objects.filter(
            product=product, tenant=tenant, quantity__gt=0
        ).order_by("expiration_date")

        for batch in batches:
            if needed <= 0:
                break
            take = min(batch.quantity, needed)
            batch.quantity -= take
            batch.save(update_fields=["quantity"])
            InventoryMovement.objects.create(
                tenant=tenant, product=product, batch=batch,
                movement_type=InventoryMovement.MovementType.OUT,
                quantity=take,
                reason=InventoryMovement.Reason.CONSUMPTION,
                related_treatment_plan_item=treatment_plan_item,
            )
            needed -= take
            consumed_count += 1

    return {"consumed": consumed_count}
