from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.utils import translation
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import (
    LIMIT_ORDER_QTY_ITEM,
    DECIMAL_ZERO,
    EMPTY_STRING,
    RoundUpTo, SaleStatus,
)
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice
from repanier.models.offeritem import OfferItemReadOnly
from repanier.models.purchase import PurchaseWoReceiver
from repanier.tools import sint

@never_cache
@require_GET
@login_required
def order_select_ajax(request):
    """Génère les options de quantité sous forme de <li><a> pour le dropdown Bootstrap 5."""
    user = request.user
    customer = Customer.can_place_an_order.filter(user_id=user.id).first()
    if customer is None:
        raise Http404

    translation.activate(customer.language)

    offer_item_id = sint(request.GET.get("offer_item", 0))
    offer_item = OfferItemReadOnly.objects.filter(id=offer_item_id).first()
    if offer_item is None:
        raise Http404

    customer_invoice = CustomerInvoice.objects.filter(
        permanence_id=offer_item.permanence_id, customer_id=customer.id
    ).first()
    if customer_invoice is None:
        raise Http404

    purchase = (
        PurchaseWoReceiver.objects.filter(
            customer_id=customer.id, offer_item_id=offer_item_id
        )
        .only("quantity_ordered")
        .first()
    )

    status = customer_invoice.status
    html = EMPTY_STRING

    if offer_item.may_order and status == SaleStatus.OPENED:
        product = offer_item.product
        price_list_multiplier = offer_item.get_price_list_multiplier(customer_invoice)
        customer_unit_price = offer_item.get_customer_unit_price(price_list_multiplier)
        unit_deposit = offer_item.get_unit_deposit()
        unit_price_amount = (customer_unit_price + unit_deposit).quantize(RoundUpTo.TWO_DECIMALS)

        q_min = product.customer_minimum_order_quantity
        if purchase is not None:
            q_previous_order = purchase.quantity_ordered
        else:
            q_previous_order = DECIMAL_ZERO

        if status == SaleStatus.OPENED and product.stock > DECIMAL_ZERO:
            q_alert = offer_item.get_q_alert() + q_previous_order
        else:
            q_alert = offer_item.get_q_alert()

        q_step = product.customer_increment_order_quantity
        q_order_is_displayed = False
        q_select_id = 0

        if q_previous_order <= 0:
            q_order_is_displayed = True

        q_valid = q_min
        if q_valid <= q_alert:
            # Option "---" ou "Sold out"
            display_text = "---" if q_valid <= q_alert else _("Sold out")
            html += '<li><a class="dropdown-item quantity-option" href="#" data-offer-item-id="{}" data-quantity="0" onclick="event.preventDefault(); selectQuantity({}, 0, this);">{}</a></li>'.format(
                offer_item.id, offer_item.id, display_text
            )
        else:
            html += '<li><a class="dropdown-item quantity-option" href="#" data-offer-item-id="{}" data-quantity="0" onclick="event.preventDefault(); selectQuantity({}, 0, this);">{}</a></li>'.format(
                offer_item.id, offer_item.id, _("Sold out")
            )

        q_counter = 0
        while q_valid <= q_alert and q_counter <= LIMIT_ORDER_QTY_ITEM:
            q_select_id += 1
            q_counter += 1
            if not q_order_is_displayed:
                if q_previous_order <= q_valid:
                    q_order_is_displayed = True

            display = product.get_display(
                qty=q_valid,
                order_unit=product.order_unit,
                unit_price_amount=unit_price_amount,
            )
            html += '<li><a class="dropdown-item quantity-option" href="#" data-offer-item-id="{}" data-quantity="{}" onclick="event.preventDefault(); selectQuantity({}, {}, this);">{}</a></li>'.format(
                offer_item.id, q_select_id, offer_item.id, q_select_id, display
            )

            if q_valid < q_step:
                q_valid = q_step
            else:
                q_valid = q_valid + q_step

        if not q_order_is_displayed:
            q_select_id += 1
            display = product.get_display(
                qty=q_previous_order,
                order_unit=product.order_unit,
                unit_price_amount=unit_price_amount,
            )
            html += '<li><a class="dropdown-item quantity-option" href="#" data-offer-item-id="{}" data-quantity="{}" onclick="event.preventDefault(); selectQuantity({}, {}, this);">{}</a></li>'.format(
                offer_item.id, q_select_id, offer_item.id, q_select_id, display
            )

        if status == SaleStatus.OPENED:
            # Option "Autre qté" avec gestion spéciale
            html += '<li><a class="dropdown-item quantity-option other-qty-option" href="#" data-offer-item-id="{}" data-quantity="other_qty" data-product-name="{}" onclick="event.preventDefault(); showOtherQtyModal({}, this);">{}</a></li>'.format(
                offer_item.id, offer_item.get_long_name_with_customer_price(), offer_item.id, _("Other qty")
            )

    else:
        # Commande fermée
        if purchase is not None and purchase.quantity_ordered != DECIMAL_ZERO:
            display = _("Closed")
        else:
            display = "---"
        html += '<li><a class="dropdown-item" href="#" disabled>{}</a></li>'.format(display)

    return HttpResponse(mark_safe(html))