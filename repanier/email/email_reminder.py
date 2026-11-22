from django.conf import settings
from django.db.models import Exists, OuterRef
from django.utils import formats, timezone
from django.utils.html import format_html
from django.utils.translation import gettext as _

from repanier import apps
from repanier.const import EmailNature, OrderUnit, SaleStatus
from repanier.email.email import RepanierEmail
from repanier.email.email_offer import (
    _build_board_task_notice,
    _get_roles_by_customer,
)
from repanier.models.customer import Customer
from repanier.models.invoice import CustomerInvoice
from repanier.models.permanence_reminder import PermanenceReminder
from repanier.models.purchase import Purchase
from repanier.models.staff import Staff


def _customer_has_valid_order(permanence, customer_id: int) -> bool:
    """Return whether the member has a nonempty order and has confirmed it if required."""
    has_purchases = Purchase.objects.filter(
        permanence_id=permanence.id,
        customer_id=customer_id,
        quantity_ordered__gt=0,
        offer_item__order_unit__lt=OrderUnit.DEPOSIT,
    ).exists()
    if not has_purchases:
        return False

    if settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
        return CustomerInvoice.objects.filter(
            permanence_id=permanence.id,
            customer_id=customer_id,
            is_order_confirm_send=True,
        ).exists()

    return True


def _build_reminder_body(
    permanence,
    closing_label,
    order_url,
    signature,
    only_for_callback,
    board_notice_html="",
):
    return format_html(
        "{board_notice}"
        "<p>{intro}</p>"
        "<p>{deadline}</p>"
        '<p style="margin: 18px 0;">'
        '<a href="{url}" style="display: inline-block; padding: 10px 18px; '
        "background-color: #0d6efd; color: #ffffff; text-decoration: none; "
        'border-radius: 4px; font-weight: bold;">{cta}</a>'
        "</p>"
        "{signature}",
        board_notice=board_notice_html,
        intro=_(
            "Hello, you asked for a reminder before orders close for %(perm)s."
        )
        % {"perm": permanence}
        if only_for_callback
        else _(
            "Hello, there is still time to place an order for %(perm)s."
        )
        % {"perm": permanence},
        deadline=_(
            "Orders will close automatically on %(closing)s."
        )
        % {"closing": closing_label},
        url=order_url,
        cta=_("Place my order now"),
        signature=signature,
    )


def send_closing_reminders(permanence):
    if permanence.status != SaleStatus.OPENED:
        return

    closing_dt = permanence.get_automatic_closing_datetime()
    if closing_dt is None:
        return

    # Select members who can order and receive emails.
    candidates = Customer.objects.filter(
        represent_this_buyinggroup=False,
        may_order=True,
        subscribe_to_email=True,
    ).select_related("user")

    only_for_callback = apps.REPANIER_SETTINGS_REMINDER_ONLY_FOR_CALLBACK
    requests = PermanenceReminder.objects.filter(
        permanence_id=permanence.id,
        customer_id=OuterRef("id"),
    )
    candidates = candidates.filter(~Exists(requests.filter(sent_at__isnull=False)))
    if only_for_callback:
        candidates = candidates.filter(Exists(requests.filter(sent_at__isnull=True)))

    roles_by_customer = _get_roles_by_customer(permanence.id)
    standard_recipients = {}
    task_recipients = {}

    for customer in candidates:
        address = customer.user.email.strip()
        if not address or _customer_has_valid_order(permanence, customer.id):
            continue
        roles = roles_by_customer.get(customer.id, [])
        if roles:
            entry = task_recipients.setdefault(
                address, {"customer_ids": [], "roles": []}
            )
            entry["customer_ids"].append(customer.id)
            for role in roles:
                if role not in entry["roles"]:
                    entry["roles"].append(role)
        else:
            standard_recipients.setdefault(address, []).append(customer.id)

    # If two accounts share the same email address and one has a task, keep only the personalized email.
    for address in task_recipients:
        if address in standard_recipients:
            task_recipients[address]["customer_ids"].extend(
                standard_recipients.pop(address)
            )

    if not standard_recipients and not task_recipients:
        return True

    order_responsible = Staff.get_or_create_order_responsible()
    local_closing = timezone.localtime(closing_dt)
    closing_label = formats.date_format(local_closing, "DATETIME_FORMAT")
    order_url = f"https://{settings.ALLOWED_HOSTS[0]}{permanence.get_order_url()}"

    subject = _("Reminder: orders for %(perm)s close at %(hour)s") % {
        "perm": permanence,
        "hour": local_closing.strftime("%H:%M"),
    }

    sent_addresses = set()
    sent_at = timezone.now()

    if standard_recipients:
        html_body = _build_reminder_body(
            permanence=permanence,
            closing_label=closing_label,
            order_url=order_url,
            signature=order_responsible["html_signature"],
            only_for_callback=only_for_callback,
        )
        email = RepanierEmail(
            email_nature=EmailNature.REMINDER,
            permanence=permanence,
            subject=subject,
            html_body=html_body,
            to=list(standard_recipients),
            show_customer_may_unsubscribe=True,
        )
        sent = email.send_email()
        sent_addresses.update(sent)
        for address in sent:
            for customer_id in standard_recipients[address]:
                PermanenceReminder.objects.update_or_create(
                    permanence=permanence,
                    customer_id=customer_id,
                    defaults={"sent_at": sent_at},
                )

    if not (settings.DEBUG and sent_addresses):
        for address, data in task_recipients.items():
            board_notice_html = _build_board_task_notice(data["roles"])
            html_body = _build_reminder_body(
                permanence=permanence,
                closing_label=closing_label,
                order_url=order_url,
                signature=order_responsible["html_signature"],
                only_for_callback=only_for_callback,
                board_notice_html=board_notice_html,
            )
            email = RepanierEmail(
                email_nature=EmailNature.REMINDER,
                permanence=permanence,
                subject=subject,
                html_body=html_body,
                to=[address],
                show_customer_may_unsubscribe=True,
            )
            sent = email.send_email()
            if sent:
                sent_addresses.update(sent)
                for customer_id in data["customer_ids"]:
                    PermanenceReminder.objects.update_or_create(
                        permanence=permanence,
                        customer_id=customer_id,
                        defaults={"sent_at": sent_at},
                    )
                if settings.DEBUG:
                    break

    all_recipients = set(standard_recipients) | set(task_recipients)
    if settings.DEBUG:
        return bool(sent_addresses) or not settings.REPANIER_SETTINGS_BCC_ALL_EMAIL_TO
    return sent_addresses == all_recipients