import json

from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from repanier.preparation_sync import (
    apply_preparation_sync,
    resolve_preparation_token,
)
from repanier.models.purchase import Purchase
from repanier.models.distribution import DistributionEvent


def _uncertain_arrival(permanence):
    return DistributionEvent.objects.filter(
        permanence=permanence, offer__is_uncertain_arrival=True
    ).exists()


def _resolve(token):
    permanence = resolve_preparation_token(token)
    if permanence is None:
        raise Http404
    if permanence.is_demo:
        pass
    return permanence


@require_GET
def preparation_page(request, token):
    permanence = _resolve(token)
    if "application/json" not in request.META.get("HTTP_ACCEPT", ""):
        return render(
            request,
            "repanier/preparation/preparation_page.html",
            {
                "permanence": permanence,
                "token": token,
                "snapshot_url": "/permanence/{}/snapshot/".format(token),
                "sync_url": "/permanence/{}/sync/".format(token),
                "is_demo": permanence.is_demo,
                "uncertain_arrival": _uncertain_arrival(permanence),
            },
        )
    return JsonResponse(
        {
            "permanence_id": permanence.id,
            "is_demo": permanence.is_demo,
            "uncertain_arrival": _uncertain_arrival(permanence),
            "server_timestamp": timezone.now().isoformat(),
        }
    )


@require_GET
def preparation_snapshot(request, token):
    permanence = _resolve(token)
    purchases = []
    from repanier.models.customer import Customer
    from repanier.models.offeritem import OfferItem
    from repanier.models.preparation import DepositContainerType

    customer_queryset = Customer.objects.filter(
        is_active=True, is_anonymized=False,
    )
    if permanence.is_demo:
        customer_queryset = customer_queryset.filter(purchase__permanence=permanence).distinct()
    else:
        customer_queryset = customer_queryset.filter(may_order=True)
    customers = [
        {
            "id": customer.id,
            "name": customer.short_basket_name,
        }
        for customer in customer_queryset.order_by("short_basket_name")
    ]
    available_offers = [
        {
            "id": offer.id,
            "name": offer.get_long_name_with_customer_price(),
        }
        for offer in OfferItem.objects.filter(
            permanence=permanence,
        ).select_related("product").order_by("long_name_v2")
    ]
    container_queryset = DepositContainerType.objects.filter(is_active=True)
    if permanence.is_demo:
        container_queryset = container_queryset.filter(code="DEMO-CONTAINER")
    else:
        container_queryset = container_queryset.exclude(code="DEMO-CONTAINER")
    deposit_types = [
        {
            "id": container.id,
            "name": container.label,
        }
        for container in container_queryset.order_by("sort_order", "label")
    ]
    queryset = (
        Purchase.objects.filter(permanence_id=permanence.id)
        .select_related(
            "offer_item",
            "offer_item__product",
            "producer",
            "customer",
            "customer_invoice__delivery__delivery_point",
        )
        .order_by(
            "producer__short_profile_name",
            "offer_item__producer_sort_order_v2",
            "-offer_item__order_average_weight",
            "customer__preparation_order",
            "customer__short_basket_name",
        )
    )
    for purchase in queryset.iterator(chunk_size=500):
        if permanence.is_demo:
            pass
        purchases.append(
            {
                "purchase_id": purchase.id,
                "offer_item_id": purchase.offer_item_id,
                "producer": purchase.producer.short_profile_name,
                "product": purchase.offer_item.get_long_name_with_customer_price(),
                "customer": purchase.customer.short_basket_name,
                "customer_id": purchase.customer.id,
                "department": (
                    purchase.offer_item.department_for_customer.short_name_v2
                    if purchase.offer_item.department_for_customer
                    else ""
                ),
                "order_unit": purchase.offer_item.order_unit,
                "order_average_weight": str(purchase.offer_item.order_average_weight),
                "producer_sort_order": purchase.offer_item.producer_sort_order_v2,
                "quantity_ordered": str(purchase.quantity_ordered),
                "quantity_prepared": str(purchase.quantity_prepared),
                "quantity_received": str(purchase.quantity_received),
                "quantity_invoiced": str(purchase.quantity_invoiced),
                "preparation_status": purchase.preparation_status,
                "origin": purchase.origin,
                "substitution_source_id": (
                    purchase.substitution_source_id
                    if hasattr(purchase, "substitution_source_id")
                    else None
                ),
                "wrapped": purchase.offer_item.wrapped,
                "invoice_by_basket": purchase.producer.invoice_by_basket,
                "in_group": bool(
                    purchase.customer_invoice
                    and purchase.customer_invoice.delivery
                    and purchase.customer_invoice.delivery.delivery_point.group_id
                ),
                "group_id": (
                    purchase.customer_invoice.delivery.delivery_point.group_id
                    if purchase.customer_invoice and purchase.customer_invoice.delivery
                    else None
                ),
                "regime": (
                    "basket"
                    if purchase.producer.invoice_by_basket
                    else "wrapped"
                    if purchase.offer_item.wrapped
                    else "standard"
                ),
            }
        )
    return JsonResponse(
        {
            "permanence_id": permanence.id,
            "is_demo": permanence.is_demo,
            "uncertain_arrival": _uncertain_arrival(permanence),
            "server_timestamp": timezone.now().isoformat(),
            "purchases": purchases,
            "customers": customers,
            "offers": available_offers,
            "deposit_types": deposit_types,
        }
    )


@csrf_exempt
@require_POST
def preparation_sync(request, token):
    permanence = _resolve(token)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "invalid_json"},
            status=400,
        )

    if isinstance(payload, list):
        results = [
            apply_preparation_sync(
                permanence,
                event,
                validated_by=getattr(request.user, "customer", None),
            )
            for event in payload
        ]
        return JsonResponse(
            {
                "server_timestamp": timezone.now().isoformat(),
                "results": results,
            }
        )
    result = apply_preparation_sync(
        permanence,
        payload,
        validated_by=getattr(request.user, "customer", None),
    )
    return JsonResponse(
        {
            "server_timestamp": timezone.now().isoformat(),
            "result": result,
        }
    )
