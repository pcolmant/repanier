from django.template import Template, Context as TemplateContext

# AttributeError: 'Context' object has no attribute 'render_context'
# OK, i got the solution:
# from decimal import *
# is the "bad One" this lib has a Context object too. Thanks for anyone reading!

from repanier.const import PRODUCT_ORDER_UNIT_DEPOSIT
from repanier.email.email import RepanierEmail
from repanier.models.customer import Customer
from repanier.models.offeritem import OfferItemWoReceiver
from repanier.models.permanence import Permanence
from repanier.models.staff import Staff
from repanier.tools import *


def send_open_order(permanence_id):
    from repanier.apps import REPANIER_SETTINGS_CONFIG

    permanence = Permanence.objects.get(id=permanence_id)
    config = REPANIER_SETTINGS_CONFIG

    order_responsible = Staff.get_or_create_order_responsible()

    to_email = []
    for customer in Customer.objects.filter(
        represent_this_buyinggroup=False,
        may_order=True,
    ):
        to_email.append(customer.user.email)
        if customer.email2:
            to_email.append(customer.email2)
    offer_description = permanence.offer_description_v2
    offer_customer_mail = config.offer_customer_mail_v2
    offer_customer_mail_subject = "{} - {}".format(
        settings.REPANIER_SETTINGS_GROUP_NAME, permanence
    )
    offer_producer = ", ".join(
        [p.short_profile_name for p in permanence.producers.all()]
    )
    qs = OfferItemWoReceiver.objects.filter(
        permanence_id=permanence_id,
        is_active=True,
        order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,  # Don't display technical products.
    ).order_by("order_sort_order_v2")
    offer_detail = "<ul>{}</ul>".format(
        "".join(
            "<li>{}, {}, {}</li>".format(
                o.get_long_name(),
                o.producer.short_profile_name,
                o.email_offer_price_with_vat,
            )
            for o in qs
        ),
    )
    if permanence.picture:
        permanence_picture = format_html(
            """
             <img
                alt="{0}" title="{0}"
                style="float: left; margin: 5px;"
                src="https:/{1}{2}{3}"/>
            """,
            permanence.get_permanence_display(),
            settings.ALLOWED_HOSTS[0],
            settings.MEDIA_URL,
            permanence.picture,
        )
        offer_description = "<hr/>{}<hr/>{}".format(
            permanence_picture, offer_description
        )

    template = Template(offer_customer_mail)
    context = TemplateContext(
        {
            "permanence_link": mark_safe(
                '<a href="https://{}{}">{}</a>'.format(
                    settings.ALLOWED_HOSTS[0],
                    reverse("repanier:order_view", args=(permanence.id,)),
                    permanence,
                )
            ),
            "offer_description": mark_safe(offer_description),
            "offer_detail": mark_safe(offer_detail),
            "offer_recent_detail": mark_safe(permanence.get_new_products),
            "offer_producer": offer_producer,
            "signature": order_responsible["html_signature"],
        }
    )
    # logger.debug("send_open_order before html_body = template.render(context)")
    html_body = template.render(context)
    # logger.debug("send_open_order after html_body = template.render(context)")
    to_email = list(set(to_email + order_responsible["to_email"]))
    email = RepanierEmail(
        subject=offer_customer_mail_subject,
        html_body=html_body,
        to=to_email,
        show_customer_may_unsubscribe=True,
    )
    email.send_email()
