"""
Resolución de precios bajo convenio (Sprint 71) — RF-CFG-03 / RF-CFG-04.

Hasta ahora `Agreement` y `Tariff` existían en la base de datos desde el
Sprint 2 y no los leía **nadie**: el presupuesto se calculaba siempre con
`Treatment.base_price`. Es decir, una clínica podía dar de alta el convenio
con una aseguradora, cargar su tarifario entero, y seguir cobrando la tarifa
particular. Este módulo es el único punto por el que se decide qué precio
corresponde, para que esa decisión no vuelva a quedar repartida por las
vistas.

## Precedencia

De lo más específico a lo más general; la primera que existe gana:

1. **Tarifario del convenio** — fila `Tariff(treatment, agreement)`. Es un
   precio pactado y negociado: manda sobre todo lo demás.
2. **Descuento porcentual del convenio** sobre el precio de referencia. Sirve
   para el convenio "10 % a todo el personal de la empresa X", que no quiere
   cargar una fila por tratamiento.
3. **Tarifario general** — fila `Tariff(treatment, agreement=None)`. Precio
   de lista de la clínica cuando difiere del precio base del catálogo.
4. **`Treatment.base_price`** — el catálogo.

El *precio de referencia* sobre el que se aplica el descuento del punto 2 es
el del punto 3 si existe y, si no, el del 4. Así, si la clínica sube su precio
de lista, los convenios porcentuales suben con él sin tocarlos uno a uno.

## Redondeo

A dos decimales con `ROUND_HALF_UP`, el redondeo comercial. `Decimal` en todo
el recorrido: el descuento es una multiplicación por un porcentaje y con
`float` aparecen los 89.99999999 en la hoja del presupuesto.
"""

from decimal import ROUND_HALF_UP, Decimal

from apps.configuration.models import Tariff

CENTS = Decimal("0.01")


def _money(value):
    """Dos decimales, redondeo comercial. Nunca negativo."""
    amount = Decimal(value or 0).quantize(CENTS, rounding=ROUND_HALF_UP)
    return amount if amount > 0 else Decimal("0.00")


def _apply_discount(base, percentage):
    """Aplica un descuento porcentual al precio de referencia."""
    if percentage is None:
        return None
    pct = Decimal(percentage)
    # Un convenio con 0 % es un convenio sin descuento, no un precio cero;
    # y uno mal cargado con 150 % no puede devolver dinero al paciente.
    pct = min(max(pct, Decimal("0")), Decimal("100"))
    return _money(Decimal(base) * (Decimal("100") - pct) / Decimal("100"))


def price_for(treatment, agreement=None, tariffs=None):
    """
    Precio de `treatment` para `agreement` (None = particular).

    `tariffs` permite pasar los tarifarios ya cargados —por ejemplo, al
    presupuestar un plan de diez ítems— y evitar una consulta por línea.
    Debe ser un iterable de `Tariff` del mismo tenant; si es None se
    consulta la base de datos solo para este tratamiento.
    """
    agreement_id = getattr(agreement, "id", agreement)

    if tariffs is None:
        rows = Tariff.objects.filter(
            tenant_id=treatment.tenant_id, treatment_id=treatment.id
        )
    else:
        rows = [t for t in tariffs if t.treatment_id == treatment.id]

    specific = general = None
    for row in rows:
        if agreement_id is not None and row.agreement_id == agreement_id:
            specific = row.price
        elif row.agreement_id is None:
            general = row.price

    # 1. Precio pactado para este convenio.
    if specific is not None:
        return _money(specific)

    # 3/4. Precio de referencia: tarifario general o catálogo.
    reference = general if general is not None else treatment.base_price

    # 2. Descuento porcentual del convenio sobre esa referencia. Solo si
    # se recibió el objeto: con un id suelto no hay porcentaje que aplicar.
    if hasattr(agreement, "discount_percentage") and agreement.is_active:
        discounted = _apply_discount(reference, agreement.discount_percentage)
        if discounted is not None:
            return discounted

    return _money(reference)


def prefetch_tariffs(tenant, agreement=None):
    """
    Tarifarios que hacen falta para presupuestar con `agreement`: los suyos
    y los generales. Pensado para pasarse a `price_for(..., tariffs=...)`.
    """
    from django.db.models import Q

    condition = Q(agreement__isnull=True)
    agreement_id = getattr(agreement, "id", agreement)
    if agreement_id is not None:
        condition |= Q(agreement_id=agreement_id)
    return list(Tariff.objects.filter(condition, tenant=tenant))


def price_matrix(tenant):
    """
    Rejilla completa tratamiento × convenio para la pantalla de tarifarios.

    Se resuelve en tres consultas en vez de en una por celda: con 60
    tratamientos y 8 convenios la versión ingenua son 480 consultas para
    pintar una tabla.

    Devuelve:
      {
        "agreements": [{id, name, discount_percentage, is_active}, …],
        "treatments": [{
            id, name, specialty_name, base_price,
            "prices": {
               "general": {"value": "40.00", "source": "tariff"|"base", "tariff_id": …},
               "<agreement_id>": {"value": "32.00", "source": "tariff"|"discount"|"general"|"base"},
            },
        }, …],
      }

    `source` es lo que permite que la pantalla distinga un precio **cargado**
    de uno **heredado**: sin ese dato la rejilla se vería llena de cifras y
    nadie sabría cuáles ha pactado de verdad con la aseguradora.
    """
    from apps.configuration.models import Agreement, Treatment

    agreements = list(Agreement.objects.filter(tenant=tenant).order_by("name"))
    treatments = list(
        Treatment.objects.filter(tenant=tenant)
        .select_related("specialty")
        .order_by("specialty__name", "name")
    )
    tariffs = list(Tariff.objects.filter(tenant=tenant))

    by_treatment = {}
    for row in tariffs:
        by_treatment.setdefault(row.treatment_id, []).append(row)

    out_treatments = []
    for treatment in treatments:
        rows = by_treatment.get(treatment.id, [])
        general_row = next((r for r in rows if r.agreement_id is None), None)
        reference = general_row.price if general_row else treatment.base_price

        prices = {
            "general": {
                "value": str(_money(reference)),
                "source": "tariff" if general_row else "base",
                "tariff_id": str(general_row.id) if general_row else None,
            }
        }
        for agreement in agreements:
            row = next((r for r in rows if r.agreement_id == agreement.id), None)
            if row:
                source, tariff_id = "tariff", str(row.id)
            elif agreement.is_active and agreement.discount_percentage is not None:
                source, tariff_id = "discount", None
            else:
                source, tariff_id = ("general" if general_row else "base"), None
            prices[str(agreement.id)] = {
                "value": str(price_for(treatment, agreement, tariffs=rows)),
                "source": source,
                "tariff_id": tariff_id,
            }

        out_treatments.append({
            "id": str(treatment.id),
            "name": treatment.name,
            "specialty_name": treatment.specialty.name,
            "base_price": str(_money(treatment.base_price)),
            "is_active": treatment.is_active,
            "prices": prices,
        })

    return {
        "agreements": [
            {
                "id": str(a.id),
                "name": a.name,
                "discount_percentage": (
                    str(a.discount_percentage) if a.discount_percentage is not None else None
                ),
                "is_active": a.is_active,
            }
            for a in agreements
        ],
        "treatments": out_treatments,
    }
