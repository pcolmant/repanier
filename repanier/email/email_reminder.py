from django.conf import settings
from django.db.models import Exists, OuterRef
from django.utils import formats, timezone
from django.utils.html import format_html
from django.utils.translation import gettext as _

from repanier import apps
from repanier.const import EmailNature, OrderUnit, SaleStatus
from repanier.email.email import RepanierEmail
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

    recipients = {}
    for customer in candidates:
        address = customer.user.email.strip()
        if address and not _customer_has_valid_order(permanence, customer.id):
            recipients.setdefault(address, []).append(customer.id)

    if not recipients:
        return True

    order_responsible = Staff.get_or_create_order_responsible()
    local_closing = timezone.localtime(closing_dt)
    closing_label = formats.date_format(local_closing, "DATETIME_FORMAT")
    order_url = f"https://{settings.ALLOWED_HOSTS[0]}{permanence.get_order_url()}"

    subject = _("Reminder: orders for %(perm)s close at %(hour)s") % {
        "perm": permanence,
        "hour": local_closing.strftime("%H:%M"),
    }
    html_body = format_html(
        "<p>{intro}</p>"
        "<p>{deadline}</p>"
        '<p style="margin: 18px 0;">'
        '<a href="{url}" style="display: inline-block; padding: 10px 18px; '
        "background-color: #0d6efd; color: #ffffff; text-decoration: none; "
        'border-radius: 4px; font-weight: bold;">{cta}</a>'
        "</p>"
        "{signature}",
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
        signature=order_responsible["html_signature"],
    )

    email = RepanierEmail(
        email_nature=EmailNature.REMINDER,
        permanence=permanence,
        subject=subject,
        html_body=html_body,
        to=list(recipients),
        show_customer_may_unsubscribe=True,
    )
    sent = email.send_email()
    sent_at = timezone.now()
    for address in sent:
        for customer_id in recipients[address]:
            PermanenceReminder.objects.update_or_create(
                permanence=permanence,
                customer_id=customer_id,
                defaults={"sent_at": sent_at},
            )

    if settings.DEBUG:
        return bool(sent) or not settings.REPANIER_SETTINGS_BCC_ALL_EMAIL_TO
    return sent == recipients.keys()