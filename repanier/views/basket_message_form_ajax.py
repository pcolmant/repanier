from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice


@never_cache
@require_GET
@login_required
def customer_basket_message_form_ajax(request, customer_invoice_id):
    user = request.user
    if user.is_repanier_staff:
        customer = (
            CustomerInvoice.objects.filter(id=customer_invoice_id).first().customer
        )
    else:
        customer = Customer.objects.filter(id=request.user.customer_id).first()
    json = {"#basket_message": customer.get_html_on_hold_movement()}
    return JsonResponse(json)
