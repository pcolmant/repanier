from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from repanier.models.customer import Customer
from repanier.tools import get_repanier_template_name


@csrf_protect
@never_cache
def unsubscribe_view(request, customer_id, token):
    """The self service switch of the general mails.

    A click on the mail footer link stops the general mails without
    login: the token signs the click. The landing page offers the
    reverse action with the same token, because a customer who hit
    the wrong link, or changed his mind, must be able to come back
    alone - the announcement mails are the only ones carrying the
    link. The order confirmations are transactional: they keep
    arriving in both states.
    """

    customer = Customer.objects.filter(id=customer_id).first()

    if customer is None or not customer.check_token(token):
        return HttpResponseRedirect("/")

    template_name = get_repanier_template_name("registration/unsubscribe.html")
    if request.method == "POST":
        # Re-subscribe.
        # customer.save(update_fields=['subscribe_to_email'])
        # use vvvv because ^^^^^ will call "pre_save" function which reset valid_email to None
        Customer.objects.filter(id=customer.id).update(subscribe_to_email=True)
        return render(request, template_name, context={"resubscribed": True})

    if customer.subscribe_to_email:
        # Unsubscribe.
        # customer.save(update_fields=['subscribe_to_email'])
        # use vvvv because ^^^^^ will call "pre_save" function which reset valid_email to None
        Customer.objects.filter(id=customer.id).update(subscribe_to_email=False)
    return render(request, template_name)
