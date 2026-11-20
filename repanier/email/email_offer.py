from collections import defaultdict
from email.mime.image import MIMEImage

from django.conf import settings
from django.template import Context as TemplateContext, Template
from django.urls import reverse
from django.utils import formats, timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from repanier import apps
from repanier.const import EmailNature, OrderUnit
from repanier.email.email import RepanierEmail
from repanier.models.customer import Customer
from repanier.models.offeritem import OfferItemReadOnly
from repanier.models.permanence import Permanence
from repanier.models.permanence_reminder import PermanenceReminder
from repanier.models.permanenceboard import PermanenceBoard
from repanier.models.staff import Staff


def _attach_permanence_picture(email, permanence):
    if permanence.picture:
        with open(settings.MEDIA_ROOT / permanence.picture.name, "rb") as fp:
            msg_image = MIMEImage(fp.read(), name="repanier.jpg")
            msg_image.add_header("Content-ID", "<id1>")
            email.attach(msg_image)


def _get_roles_by_customer(permanence_id):
    roles_by_customer = defaultdict(list)
    for board in (
        PermanenceBoard.objects.filter(
            permanence_id=permanence_id,
            customer__isnull=False,
        )
        .select_related("permanence_role")
        .order_by("permanence_role__tree_id", "permanence_role__lft")
    ):
        roles_by_customer[board.customer_id].append(str(board.permanence_role))
    return roles_by_customer


def _build_board_task_notice(roles):
    if not roles:
        return ""
    roles_label = ", ".join(roles)
    return format_html(
        '<div style="margin: 16px 0; padding: 12px 16px; '
        "background-color: #fff3cd; border-left: 4px solid #ffc107; "
        'border-radius: 4px; color: #664d03;">'
        '<p style="margin: 0 0 4px 0; font-size: 0.95em;">'
        "<strong>{title}</strong>"
        "</p>"
        '<p style="margin: 0; font-size: 0.92em;">'
        "{body}"
        "</p>"
        "</div>",
        title=_("Reminder: you are registered for a task for this permanence!"),
        body=_(
            "Registered task(s): %(roles)s. Don't forget to place your own order before closing."
        )
        % {"roles": roles_label},
    )


def send_open_order(permanence_id):
    permanence = Permanence.objects.get(id=permanence_id)
    config = apps.REPANIER_SETTINGS_CONFIG
    order_responsible = Staff.get_or_create_order_responsible()

    customers = list(
        Customer.objects.filter(
            represent_this_buyinggroup=False,
            may_order=True,
        ).select_related("user")
    )
    roles_by_customer = _get_roles_by_customer(permanence_id)

    offer_description = permanence.offer_description_v2
    offer_customer_mail = config.offer_customer_mail_v2
    offer_customer_mail_subject = "{} - {}".format(
        settings.REPANIER_SETTINGS_GROUP_NAME, permanence
    )
    offer_producer = ", ".join(
        [p.short_profile_name for p in permanence.producers.all()]
    )
    qs = OfferItemReadOnly.objects.filter(
        permanence_id=permanence_id,
        is_active=True,
        order_unit__lt=OrderUnit.DEPOSIT,
    ).order_by("order_sort_order_v2")
    offer_detail = "<ul>{}</ul>".format(
        "".join(
            "<li>{producer}, {product}</li>".format(
                producer=o.producer.short_profile_name,
                product=o.get_long_name_with_customer_price(),
            )
            for o in qs
        ),
    )
    if permanence.picture:
        offer_description = format_html(
            """
            <hr/>
            <img
                alt="{label}" title="{label}"
                style="float: left; margin: 5px;"
                src="cid:id1"/>
            <hr/>
            {body}
            """,
            label=permanence.get_permanence_display(),
            body=offer_description,
        )

    closing_dt = permanence.get_automatic_closing_datetime()
    has_reminder_feature = (
        closing_dt is not None
        and apps.REPANIER_SETTINGS_REMINDER_HOURS_BEFORE_CLOSING > 0
    )
    closing_label = ""
    if closing_dt is not None:
        local_closing = timezone.localtime(closing_dt)
        closing_label = formats.date_format(local_closing, "DATETIME_FORMAT")

    base_url = f"https://{settings.ALLOWED_HOSTS[0]}"
    permanence_link = mark_safe(
        '<a href="{}{}">{}</a>'.format(
            base_url,
            permanence.get_order_url(),
            permanence,
        )
    )
    template = Template(offer_customer_mail)
    has_custom_board_placeholder = (
        "{{ permanence_board_reminder }}" in offer_customer_mail
        or "{{permanence_board_reminder}}" in offer_customer_mail
    )
    has_custom_reminder_placeholder = (
        "{{ reminder_link }}" in offer_customer_mail
        or "{{reminder_link}}" in offer_customer_mail
    )

    if not has_reminder_feature:
        customers_without_tasks = [
            c for c in customers if not roles_by_customer.get(c.id)
        ]
        customers_with_tasks = [
            c for c in customers if roles_by_customer.get(c.id)
        ]

        if customers_without_tasks:
            html_body = template.render(
                TemplateContext(
                    {
                        "permanence_link": permanence_link,
                        "offer_description": mark_safe(offer_description),
                        "offer_detail": mark_safe(offer_detail),
                        "offer_recent_detail": mark_safe(permanence.get_new_products),
                        "offer_producer": offer_producer,
                        "closing_datetime": closing_label,
                        "reminder_link": "",
                        "permanence_board_reminder": "",
                        "signature": order_responsible["html_signature"],
                    }
                )
            )
            email = RepanierEmail(
                email_nature=EmailNature.OPENING,
                permanence=permanence,
                subject=offer_customer_mail_subject,
                html_body=html_body,
                to=[c.user.email for c in customers_without_tasks],
                show_customer_may_unsubscribe=True,
            )
            _attach_permanence_picture(email, permanence)
            email.send_email()

        for customer in customers_with_tasks:
            board_notice_html = _build_board_task_notice(
                roles_by_customer[customer.id]
            )
            html_body = template.render(
                TemplateContext(
                    {
                        "permanence_link": permanence_link,
                        "offer_description": mark_safe(offer_description),
                        "offer_detail": mark_safe(offer_detail),
                        "offer_recent_detail": mark_safe(permanence.get_new_products),
                        "offer_producer": offer_producer,
                        "closing_datetime": closing_label,
                        "reminder_link": "",
                        "permanence_board_reminder": mark_safe(board_notice_html),
                        "signature": order_responsible["html_signature"],
                    }
                )
            )
            if not has_custom_board_placeholder:
                html_body = f"{board_notice_html}{html_body}"

            email = RepanierEmail(
                email_nature=EmailNature.OPENING,
                permanence=permanence,
                subject=offer_customer_mail_subject,
                html_body=html_body,
                to=[customer.user.email],
                show_customer_may_unsubscribe=True,
            )
            _attach_permanence_picture(email, permanence)
            email.send_email()
            if settings.DEBUG:
                break
        return

    # Generate a personal reminder link (and task reminder if registered) for each member.
    for customer in customers:
        token = PermanenceReminder.make_token(permanence.id, customer.id)
        reminder_path = reverse("repanier:reminder_view", kwargs={"token": token})
        reminder_url = f"{base_url}{reminder_path}"
        reminder_button_html = format_html(
            '<div style="margin: 16px 0; padding: 12px 16px; '
            "background-color: #f8f9fa; border-left: 4px solid #198754; "
            'border-radius: 4px;">'
            '<p style="margin: 0 0 6px 0; font-size: 0.95em;">'
            "<strong>{closing_title} :</strong> {closing}"
            "</p>"
            '<p style="margin: 0 0 10px 0; font-size: 0.92em; color: #495057;">'
            "{reassurance}"
            "</p>"
            '<p style="margin: 0 0 6px 0;">'
            '<a href="{url}" style="display: inline-block; padding: 9px 16px; '
            "background-color: #198754; color: #ffffff; text-decoration: none; "
            'border-radius: 4px; font-weight: bold;">'
            "{cta}"
            "</a>"
            "</p>"
            "</div>",
            closing_title=_("Order closing"),
            closing=closing_label,
            reassurance=_(
                "Short on time today? "
                "We will only remind you if you have not placed an order yet."
            ),
            url=reminder_url,
            cta=_("Remind me before orders close (if I have not ordered)"),
        )
        board_notice_html = _build_board_task_notice(
            roles_by_customer.get(customer.id)
        )
        context = TemplateContext(
            {
                "permanence_link": permanence_link,
                "offer_description": mark_safe(offer_description),
                "offer_detail": mark_safe(offer_detail),
                "offer_recent_detail": mark_safe(permanence.get_new_products),
                "offer_producer": offer_producer,
                "closing_datetime": closing_label,
                "reminder_link": mark_safe(reminder_button_html),
                "permanence_board_reminder": mark_safe(board_notice_html),
                "signature": order_responsible["html_signature"],
            }
        )
        html_body = template.render(context)
        if board_notice_html and not has_custom_board_placeholder:
            html_body = f"{board_notice_html}{html_body}"
        if not has_custom_reminder_placeholder:
            html_body = f"{html_body}{reminder_button_html}"

        email = RepanierEmail(
            email_nature=EmailNature.OPENING,
            permanence=permanence,
            subject=offer_customer_mail_subject,
            html_body=html_body,
            to=[customer.user.email],
            show_customer_may_unsubscribe=True,
        )
        _attach_permanence_picture(email, permanence)
        email.send_email()

        if settings.DEBUG:
            break