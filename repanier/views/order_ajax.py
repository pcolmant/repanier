from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import DECIMAL_ZERO, EMPTY_STRING, RoundUpTo, SaleStatus
from repanier.models.customer import Customer
from repanier.models.invoice import ProducerInvoice, CustomerInvoice
from repanier.models.offeritem import OfferItemReadOnly
from repanier.models.permanence import Permanence
from repanier.tools import (
    create_or_update_one_cart_item,
    sint,
    sboolean,
    my_basket,
    get_html_selected_value,
    get_html_basket_message,
    get_repanier_template_name,
)


@never_cache
@require_GET
@login_required
def order_ajax(request):
    """
    Add a selected offer item to a customer order (i.e. update the customer's invoice and the producer's invoice)
    """
    # print("####### order_ajax")
    user = request.user
    customer = Customer.objects.filter(id=user.customer_id, may_order=True).first()
    if customer is None:
        raise Http404
    offer_item_id = sint(request.GET.get("offer_item", 0))
    value_id = sint(request.GET.get("value", 0))
    qs = CustomerInvoice.objects.filter(
        permanence__offeritem=offer_item_id,
        customer_id=customer.id,
        status=SaleStatus.OPENED,
    )
    json_dict = {}
    if qs.exists():
        qs = ProducerInvoice.objects.filter(
            permanence__offeritem=offer_item_id,
            producer__offeritem=offer_item_id,
            status=SaleStatus.OPENED,
        )
        if qs.exists():
            purchase, updated = create_or_update_one_cart_item(
                customer=customer,
                offer_item_id=offer_item_id,
                value_id=value_id,
                batch_job=False,
                comment=EMPTY_STRING,
            )
            offer_item = OfferItemReadOnly.objects.filter(id=offer_item_id).first()
            if purchase is not None:
                offer_item = purchase.offer_item
                price_list_multiplier = offer_item.get_price_list_multiplier(
                    purchase.customer_invoice
                )
                customer_unit_price = offer_item.get_customer_unit_price(
                    price_list_multiplier
                )
                unit_deposit = offer_item.get_unit_deposit()
                unit_price_amount = (customer_unit_price + unit_deposit).quantize(
                    RoundUpTo.TWO_DECIMALS
                )
                json_dict[
                    "#offer_item{}".format(offer_item.id)
                ] = get_html_selected_value(
                    offer_item,
                    purchase.quantity_ordered,
                    unit_price_amount=unit_price_amount,
                    is_open=True,
                )
            else:
                json_dict[
                    "#offer_item{}".format(offer_item.id)
                ] = get_html_selected_value(
                    offer_item, DECIMAL_ZERO, DECIMAL_ZERO, is_open=True
                )

            producer_invoice = (
                ProducerInvoice.objects.filter(
                    producer_id=offer_item.producer_id,
                    permanence_id=offer_item.permanence_id,
                )
                .only("total_price_with_tax")
                .first()
            )
            json_dict.update(producer_invoice.get_order_json())

            customer_invoice = CustomerInvoice.objects.filter(
                permanence_id=offer_item.permanence_id, customer_id=customer.id
            ).first()
            customer_invoice.calculate_order_amount()
            invoice_confirm_status_is_changed = customer_invoice.cancel_confirm_order()
            customer_invoice.save()
            if invoice_confirm_status_is_changed:
                if settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
                    template_name = get_repanier_template_name(
                        "communication_confirm_order.html"
                    )
                    html = render_to_string(template_name)
                    json_dict["#communicationModal"] = mark_safe(html)
                customer_invoice.save()
            json_dict.update(
                my_basket(
                    customer_invoice.is_order_confirm_send,
                    customer_invoice.get_total_price_with_tax(),
                )
            )

            permanence = Permanence.objects.filter(id=offer_item.permanence_id).first()
            is_basket = sboolean(request.GET.get("is_basket", False))
            delivery_message = customer_invoice.get_html_select_delivery_point(
                permanence, SaleStatus.OPENED
            )
            if is_basket:
                basket_message = get_html_basket_message(
                    customer, permanence, SaleStatus.OPENED, customer_invoice
                )
            else:
                basket_message = EMPTY_STRING

            json_dict.update(
                customer_invoice.get_html_my_order_confirmation(
                    permanence=permanence,
                    is_basket=is_basket,
                    delivery_message=delivery_message,
                    basket_message=basket_message,
                )
            )
    return JsonResponse(json_dict)
