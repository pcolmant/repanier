from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from repanier.models.product import Product
from repanier.tools import sint, update_offer_item


@never_cache
@require_GET
@transaction.atomic
@login_required
def is_into_offer(request, product_id):
    user = request.user
    if user.is_order_manager:
        product_id = sint(product_id)
        product = Product.objects.filter(id=product_id).first()
        if product is not None:
            product.is_into_offer = not product.is_into_offer
            product.save(update_fields=["is_into_offer"])
            update_offer_item(product=product)
            return HttpResponse(product.get_html_is_into_offer())
    raise Http404
