from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.const import PERMANENCE_OPENED, DECIMAL_ZERO, EMPTY_STRING
from repanier.models.box import BoxContent
from repanier.models.customer import Customer
from repanier.models.invoice import ProducerInvoice, CustomerInvoice
from repanier.models.offeritem import OfferItemWoReceiver
from repanier.models.permanence import Permanence
from repanier.models.purchase import PurchaseWoReceiver
from repanier.tools import (
    create_or_update_one_cart_item,
    sint,
    sboolean,
    my_basket,
    get_html_selected_value,
    get_html_selected_box_value,
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

    if not request.is_ajax():
        raise Http404
    user = request.user
    customer = Customer.objects.filter(user_id=user.id, may_order=True).first()
    if customer is None:
        raise Http404
    offer_item_id = sint(request.GET.get("offer_item", 0))
    value_id = sint(request.GET.get("value", 0))
    is_basket = sboolean(request.GET.get("is_basket", False))
    qs = CustomerInvoice.objects.filter(
        permanence__offeritem=offer_item_id,
        customer_id=customer.id,
        status=PERMANENCE_OPENED,
    )
    json_dict = {}
    if qs.exists():
        qs = ProducerInvoice.objects.filter(
            permanence__offeritem=offer_item_id,
            producer__offeritem=offer_item_id,
            status=PERMANENCE_OPENED,
        )
        if qs.exists():
            purchase, updated = create_or_update_one_cart_item(
                customer=customer,
                offer_item_id=offer_item_id,
                value_id=value_id,
                batch_job=False,
                comment=EMPTY_STRING,
            )
            offer_item = OfferItemWoReceiver.objects.filter(id=offer_item_id).first()
            if purchase is None:
                json_dict[
                    "#offer_item{}".format(offer_item.id)
                ] = get_html_selected_value(offer_item, DECIMAL_ZERO, is_open=True)
            else:
                json_dict[
                    "#offer_item{}".format(offer_item.id)
                ] = get_html_selected_value(
                    offer_item, purchase.qty_ordered, is_open=True
                )
            if updated and offer_item.is_box:
                # update the content
                for content in BoxContent.objects.filter(
                    box=offer_item.product_id
                ).only("product_id"):
                    box_offer_item = OfferItemWoReceiver.objects.filter(
                        product_id=content.product_id,
                        permanence_id=offer_item.permanence_id,
                    ).first()
                    if box_offer_item is not None:
                        # Select one purchase
                        purchase = (
                            PurchaseWoReceiver.objects.filter(
                                customer_id=customer.id,
                                offer_item_id=box_offer_item.id,
                                is_box_content=False,
                            )
                            .only("qty_ordered")
                            .first()
                        )
                        if purchase is not None:
                            json_dict[
                                "#offer_item{}".format(box_offer_item.id)
                            ] = get_html_selected_value(
                                box_offer_item, purchase.qty_ordered, is_open=True
                            )
                        box_purchase = (
                            PurchaseWoReceiver.objects.filter(
                                customer_id=customer.id,
                                offer_item_id=box_offer_item.id,
                                is_box_content=True,
                            )
                            .only("qty_ordered")
                            .first()
                        )
                        if box_purchase is not None:
                            json_dict[
                                "#box_offer_item{}".format(box_offer_item.id)
                            ] = get_html_selected_box_value(
                                box_offer_item, box_purchase.qty_ordered
                            )

            if settings.REPANIER_SETTINGS_SHOW_PRODUCER_ON_ORDER_FORM:
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
            invoice_confirm_status_is_changed = customer_invoice.cancel_confirm_order()
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

            if is_basket:
                basket_message = get_html_basket_message(
                    customer, permanence, PERMANENCE_OPENED
                )
            else:
                basket_message = EMPTY_STRING
            json_dict.update(
                customer_invoice.get_html_my_order_confirmation(
                    permanence=permanence,
                    is_basket=is_basket,
                    basket_message=basket_message,
                )
            )
    return JsonResponse(json_dict)
