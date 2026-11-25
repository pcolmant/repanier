import datetime
from decimal import Decimal

from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from repanier.const import DECIMAL_ZERO, OrderUnit, SaleStatus, Vat
from repanier.models.customer import Customer
from repanier.models.offeritem import OfferItem
from repanier.models.permanence import Permanence
from repanier.models.preparation import DepositContainerType
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.preparation_sync import make_preparation_token


@transaction.atomic
def create_demo_preparation():
    permanence = Permanence.objects.create(
        permanence_date=timezone.now().date(),
        status=SaleStatus.SEND,
        is_demo=True,
        preparation_enabled=True,
        short_name_v2="GSM TEST",
    )

    producer = Producer.objects.create(
        short_profile_name="Producer test",
        long_profile_name="Producer test",
        is_active=True,
    )
    permanence.producers.add(producer)

    group_user = get_user_model().objects.create(
        username="demo-group",
        email="demo-group@example.invalid",
        is_active=True,
    )
    group = Customer.objects.create(
        user=group_user,
        short_basket_name="Group test",
        long_basket_name="Group test",
        is_group=True,
        may_order=False,
    )

    container = DepositContainerType.objects.create(
        code="DEMO-CONTAINER",
        label="Demo container",
        unit_credit=Decimal("1.25"),
        is_active=True,
        sort_order=1,
    )

    products = []
    for name, unit, weight, price in (
        ("Heavy product", OrderUnit.KG, Decimal("5"), Decimal("4.00")),
        ("Wrapped product", OrderUnit.PC, Decimal("1"), Decimal("3.00")),
        ("Standard product", OrderUnit.PC, Decimal("1"), Decimal("2.00")),
    ):
        product = Product.objects.create(
            producer=producer,
            long_name_v2=name,
            order_unit=unit,
            order_average_weight=weight,
            producer_unit_price=price,
            customer_unit_price=price,
            vat_level=Vat.VAT_100,
            stock=Decimal("99"),
            wrapped=name == "Wrapped product",
            is_active=True,
        )
        offer_item = OfferItem.objects.create(
            permanence=permanence,
            product=product,
            producer=producer,
            long_name_v2=name,
            order_unit=unit,
            order_average_weight=weight,
            producer_unit_price=price,
            customer_unit_price=price,
            quantity_invoiced=Decimal("0"),
        )
        products.append((product, offer_item))

    for offer_item in (item[1] for item in products):
        from repanier.models.purchase import Purchase
        Purchase.objects.create(
            permanence=permanence,
            offer_item=offer_item,
            producer=producer,
            customer=group,
            status=SaleStatus.SEND,
            quantity_ordered=Decimal("1"),
            quantity_prepared=Decimal("0"),
            quantity_received=Decimal("0"),
            quantity_invoiced=Decimal("0"),
            purchase_price=offer_item.producer_unit_price,
            selling_price=offer_item.customer_unit_price,
        )

    token = make_preparation_token(permanence.id)
    return {
        "permanence": permanence,
        "producer": producer,
        "group": group,
        "container": container,
        "products": products,
        "token": token,
    }


@transaction.atomic
def reset_demo_preparation(permanence_id):
    from repanier.models.preparation import (
        DepositReceipt,
        PreparationSyncEvent,
    )
    from repanier.models.purchase import Purchase
    from repanier.models.offeritem import OfferItem

    permanence = (
        Permanence.objects.select_for_update()
        .filter(id=permanence_id, is_demo=True)
        .first()
    )
    if permanence is None:
        return None

    PreparationSyncEvent.objects.filter(permanence=permanence).delete()
    DepositReceipt.objects.filter(permanence=permanence).delete()
    Purchase.objects.filter(permanence=permanence).delete()
    OfferItem.objects.filter(permanence=permanence).delete()
    permanence.preparation_enabled = True
    permanence.status = SaleStatus.SEND
    permanence.save(update_fields=["preparation_enabled", "status"])

    producer = permanence.producers.first()
    if producer is not None:
        group = Customer.objects.filter(
            is_group=True,
            short_basket_name="Group test",
            user__username="demo-group",
        ).first()
        for name, unit, weight, price in (
            ("Heavy product", OrderUnit.KG, Decimal("5"), Decimal("4.00")),
            ("Wrapped product", OrderUnit.PC, Decimal("1"), Decimal("3.00")),
            ("Standard product", OrderUnit.PC, Decimal("1"), Decimal("2.00")),
        ):
            product = Product.objects.filter(
                producer=producer,
                long_name_v2=name,
            ).first()
            if product is None:
                continue
            offer_item = OfferItem.objects.create(
                permanence=permanence,
                product=product,
                producer=producer,
                long_name_v2=name,
                order_unit=unit,
                order_average_weight=weight,
                producer_unit_price=price,
                customer_unit_price=price,
                quantity_invoiced=Decimal("0"),
                wrapped=name == "Wrapped product",
            )
            if group is not None:
                Purchase.objects.create(
                    permanence=permanence,
                    offer_item=offer_item,
                    producer=producer,
                    customer=group,
                    status=SaleStatus.SEND,
                    quantity_ordered=Decimal("1"),
                    quantity_prepared=Decimal("0"),
                    quantity_received=Decimal("0"),
                    quantity_invoiced=Decimal("0"),
                    purchase_price=price,
                    selling_price=price,
                )

    return permanence
