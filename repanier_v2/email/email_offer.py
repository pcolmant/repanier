from django.template import Template, Context as TemplateContext

from repanier_v2.const import EMPTY_STRING, PRODUCT_ORDER_UNIT_DEPOSIT
from repanier_v2.email.email import RepanierEmail
from repanier_v2.models.customer import Customer
from repanier_v2.models.offeritem import OfferItemWoReceiver
from repanier_v2.models.permanence import Permanence
from repanier_v2.models.staff import Staff
from repanier_v2.tools import *


# AttributeError: 'Context' object has no attribute 'render_context'
# OK, i got the solution:
# from decimal import *
# is the "bad One" this lib has a Context object too. Thanks for anyone reading!


def send_open_order(permanence_id):
    from repanier_v2.globals import REPANIER_SETTINGS_CONFIG

    cur_language = translation.get_language()
    for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
        language_code = language["code"]
        translation.activate(language_code)
        permanence = Permanence.objects.get(id=permanence_id)
        config = REPANIER_SETTINGS_CONFIG

        order_responsible = Staff.get_or_create_order_responsible()

        to_email = []
        for customer in Customer.objects.filter(
            is_default=False, may_order=True, language=language_code
        ).order_by("?"):
            to_email.append(customer.user.email)
            if customer.email2:
                to_email.append(customer.email2)
        offer_description = permanence.safe_translation_getter(
            "offer_description", any_language=True, default=EMPTY_STRING
        )
        offer_customer_mail = config.safe_translation_getter(
            "offer_customer_mail", any_language=True, default=EMPTY_STRING
        )
        offer_customer_mail_subject = "{} - {}".format(
            settings.REPANIER_SETTINGS_GROUP_NAME, permanence
        )
        offer_producer = ", ".join([p.short_name for p in permanence.producers.all()])
        qs = OfferItemWoReceiver.objects.filter(
            permanence_id=permanence_id,
            is_active=True,
            order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,  # Don't display technical products.
            translations__language_code=language_code,
        ).order_by("translations__order_sort_order")
        offer_detail = "<ul>{}</ul>".format(
            "".join(
                "<li>{}, {}, {}</li>".format(
                    o.get_long_name(),
                    o.producer.short_name,
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
                        reverse("repanier_v2:order_view", args=(permanence.id,)),
                        permanence,
                    )
                ),
                "offer_description": mark_safe(offer_description),
                "offer_detail": mark_safe(offer_detail),
                "offer_recent_detail": mark_safe(permanence.get_html_new_products),
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
    translation.activate(cur_language)
