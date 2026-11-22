from datetime import timedelta
import logging
import threading

from django.conf import settings
from django.contrib import admin, messages
from django.db import close_old_connections, models
from django.db.models import Count
from django import forms
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

from repanier.email.email import RepanierEmail, in_customer_language
from repanier.models.customer import Customer
from repanier.models.poll import Poll, PollChoice, PollResponse, is_new_poll_enabled
from repanier.xlsx.xlsx_poll import export_poll_xlsx

logger = logging.getLogger(__name__)

MIN_DELETE_AGE = timedelta(days=365)


class PollChoiceInline(admin.TabularInline):
    model = PollChoice
    extra = 3
    fields = ("label",)
    formfield_overrides = {
        models.CharField: {
            "widget": forms.TextInput(attrs={"style": "width: 98%; max-width: none;"})
        },
    }


class PollResponseInline(admin.TabularInline):
    model = PollResponse
    extra = 0
    can_delete = False
    fields = ("customer", "selected_display", "comment", "answered_at")
    readonly_fields = ("customer", "selected_display", "comment", "answered_at")

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related("customer", "choice")
            .prefetch_related("choices")
        )
        return qs.order_by(
            models.F("answered_at").desc(nulls_last=True),
            "customer__short_basket_name",
        )

    @admin.display(description=_("Selected choices"))
    def selected_display(self, obj):
        if not obj.answered_at:
            return ""
        multi_labels = [c.label for c in obj.choices.all()]
        if multi_labels:
            return ", ".join(multi_labels)
        if obj.choice:
            return obj.choice.label
        return ""


@in_customer_language
def _render_invitation_for_customer(
    customer,
    poll,
    response_obj,
    base_url,
    is_reminder=False,
    show_unsubscribe=True,
):
    email_to = getattr(customer.user, "email", "") if customer.user else ""
    if not email_to:
        return None

    relative_url = reverse(
        "repanier:poll_vote", kwargs={"token": str(response_obj.token)}
    )
    form_url = f"{base_url.rstrip('/')}{relative_url}"

    subject = (
        _("[Reminder] %(title)s") % {"title": poll.title}
        if is_reminder
        else poll.title
    )

    html_body = render_to_string(
        "repanier/email/poll_invitation.html",
        {
            "poll": poll,
            "customer": customer,
            "form_url": form_url,
            "is_reminder": is_reminder,
        },
    )

    return RepanierEmail(
        subject=subject,
        html_body=html_body,
        to=[email_to],
        show_customer_may_unsubscribe=show_unsubscribe,
    )


def _send_poll_emails_worker(
    poll_id,
    base_url,
    *,
    is_reminder=False,
    only_customer_id=None,
    mark_sent=False,
    stop_on_first_in_debug=False,
):
    close_old_connections()
    try:
        poll = Poll.objects.filter(pk=poll_id).first()
        if poll is None:
            return

        if only_customer_id is not None:
            customer = (
                Customer.objects.filter(pk=only_customer_id)
                .select_related("user")
                .first()
            )
            if customer is None:
                return
            response_obj, _created = PollResponse.objects.get_or_create(
                poll=poll,
                customer=customer,
            )
            email = _render_invitation_for_customer(
                response_obj.customer,
                poll,
                response_obj,
                base_url,
                is_reminder=is_reminder,
                show_unsubscribe=True,
            )
            if email is not None:
                email.send_email()
            return

        if is_reminder:
            targets = list(
                poll.responses.filter(
                    answered_at__isnull=True,
                    customer__subscribe_to_email=True,
                    customer__represent_this_buyinggroup=False,
                ).select_related("customer__user")
            )
            for response_obj in targets:
                email = _render_invitation_for_customer(
                    response_obj.customer,
                    poll,
                    response_obj,
                    base_url,
                    is_reminder=True,
                    show_unsubscribe=True,
                )
                if email is not None and email.send_email():
                    if stop_on_first_in_debug:
                        break
            return

        eligible_customers = list(
            Customer.objects.filter(
                is_active=True,
                may_order=True,
                subscribe_to_email=True,
                represent_this_buyinggroup=False,
            ).select_related("user")
        )

        sent_count = 0
        for customer in eligible_customers:
            response_obj, _created = PollResponse.objects.get_or_create(
                poll=poll,
                customer=customer,
            )
            email = _render_invitation_for_customer(
                response_obj.customer,
                poll,
                response_obj,
                base_url,
                is_reminder=False,
                show_unsubscribe=True,
            )
            if email is not None and email.send_email():
                sent_count += 1
                if stop_on_first_in_debug:
                    break

        if mark_sent and sent_count > 0:
            poll.sent_at = timezone.now()
            poll.save(update_fields=["sent_at"])
    except Exception:
        logger.exception("Error while sending poll emails in background thread")
    finally:
        close_old_connections()

@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "allow_multiple",
        "deadline",
        "sent_at",
        "response_summary",
    )
    ordering = ("-deadline", "-created_at")
    readonly_fields = ("created_at", "sent_at", "results_board")
    fields = (
        "title",
        "description",
        "allow_multiple",
        "deadline",
        "created_at",
        "sent_at",
        "results_board",
    )
    inlines = [PollChoiceInline, PollResponseInline]
    actions = [
        "send_test_poll_to_me",
        "send_poll_emails",
        "remind_unanswered_members",
        "export_results_xlsx",
    ]

    def has_module_permission(self, request):
        return is_new_poll_enabled() and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return is_new_poll_enabled() and super().has_view_permission(request, obj=obj)

    def has_add_permission(self, request):
        return is_new_poll_enabled() and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return is_new_poll_enabled() and super().has_change_permission(request, obj=obj)

    def has_delete_permission(self, request, obj=None):
        if not (is_new_poll_enabled() and super().has_delete_permission(request, obj=obj)):
            return False
        if obj is not None and getattr(obj, "created_at", None):
            if timezone.now() - obj.created_at < MIN_DELETE_AGE:
                return False
        return True

    def delete_queryset(self, request, queryset):
        cutoff = timezone.now() - MIN_DELETE_AGE
        protected = queryset.filter(created_at__gte=cutoff)
        allowed = queryset.filter(created_at__lt=cutoff)
        if protected.exists():
            self.message_user(
                request,
                _(
                    "Polls created less than one year ago cannot be deleted."
                ),
                level=messages.WARNING,
            )
        if allowed.exists():
            super().delete_queryset(request, allowed)

    @admin.display(description=_("Responses"))
    def response_summary(self, obj):
        total = obj.responses.count()
        answered = obj.responses.filter(answered_at__isnull=False).count()
        return f"{answered} / {total}"

    @admin.display(description=_("Results summary"))
    def results_board(self, obj):
        if not obj or not obj.pk:
            return _("Save the poll first to see results.")

        total_invited = obj.responses.count()
        if total_invited == 0:
            return _("No invitations sent yet.")

        answered_count = obj.responses.filter(answered_at__isnull=False).count()
        unanswered_count = total_invited - answered_count

        if getattr(obj, "allow_multiple", False):
            choices_with_counts = obj.choices.annotate(
                votes=Count(
                    "multi_responses",
                    filter=models.Q(multi_responses__answered_at__isnull=False),
                )
            )
        else:
            choices_with_counts = obj.choices.annotate(
                votes=Count(
                    "responses",
                    filter=models.Q(responses__answered_at__isnull=False),
                )
            )

        rows = []
        for choice in choices_with_counts:
            pct = round((choice.votes / total_invited) * 100) if total_invited else 0
            rows.append((choice.label, choice.votes, pct))

        unanswered_pct = (
            round((unanswered_count / total_invited) * 100) if total_invited else 0
        )

        rows_html = format_html_join(
            "",
            '<tr><td style="padding:6px 12px;">{}</td>'
            '<td style="padding:6px 12px; text-align:right; font-weight:bold;">{}</td>'
            '<td style="padding:6px 12px; text-align:right; color:#555;">{}%</td></tr>',
            rows,
        )

        return format_html(
            '<table style="border-collapse:collapse; min-width:360px; border:1px solid #ddd;">'
            '<thead><tr style="background:#f5f5f5; border-bottom:1px solid #ddd;">'
            '<th style="padding:6px 12px; text-align:left;">{}</th>'
            '<th style="padding:6px 12px; text-align:right;">{}</th>'
            '<th style="padding:6px 12px; text-align:right;">%</th>'
            "</tr></thead>"
            "<tbody>{}"
            '<tr style="border-top:1px solid #ddd; color:#777; font-style:italic;">'
            '<td style="padding:6px 12px;">{}</td>'
            '<td style="padding:6px 12px; text-align:right;">{}</td>'
            '<td style="padding:6px 12px; text-align:right;">{}%</td>'
            "</tr></tbody></table>",
            _("Choice"),
            _("Votes"),
            rows_html,
            _("No response yet"),
            unanswered_count,
            unanswered_pct,
        )

    @admin.action(description=_("Send test poll to me"))
    def send_test_poll_to_me(self, request, queryset):
        if not is_new_poll_enabled():
            return

        if queryset.count() != 1:
            self.message_user(
                request,
                _("Please select exactly one poll."),
                level=messages.WARNING,
            )
            return

        poll = queryset.first()
        if poll.choices.count() < 2:
            self.message_user(
                request,
                _("Please define at least two choices before sending."),
                level=messages.ERROR,
            )
            return

        customer_id = getattr(request.user, "customer_id", None)
        if customer_id is None and hasattr(request.user, "customer"):
            customer_id = getattr(request.user.customer, "id", None)

        if not customer_id:
            self.message_user(
                request,
                _("No customer profile is linked to your user account."),
                level=messages.ERROR,
            )
            return

        customer = (
            Customer.objects.filter(pk=customer_id).select_related("user").first()
        )
        if not customer or not getattr(customer.user, "email", ""):
            self.message_user(
                request,
                _("Your customer account has no email address."),
                level=messages.ERROR,
            )
            return

        base_url = request.build_absolute_uri("/")
        t = threading.Thread(
            target=_send_poll_emails_worker,
            args=(poll.id, base_url),
            kwargs={
                "is_reminder": False,
                "only_customer_id": customer.id,
                "mark_sent": False,
                "stop_on_first_in_debug": False,
            },
        )
        t.start()

        self.message_user(
            request,
            _("Test poll email is being sent to %(email)s.")
            % {"email": customer.user.email},
            level=messages.INFO,
        )

    @admin.action(description=_("Send poll email to active members"))
    def send_poll_emails(self, request, queryset):
        if not is_new_poll_enabled():
            return

        if queryset.count() != 1:
            self.message_user(
                request,
                _("Please select exactly one poll to send."),
                level=messages.WARNING,
            )
            return

        poll = queryset.first()
        if poll.choices.count() < 2:
            self.message_user(
                request,
                _("Please define at least two choices before sending."),
                level=messages.ERROR,
            )
            return

        base_url = request.build_absolute_uri("/")
        t = threading.Thread(
            target=_send_poll_emails_worker,
            args=(poll.id, base_url),
            kwargs={
                "is_reminder": False,
                "only_customer_id": None,
                "mark_sent": True,
                "stop_on_first_in_debug": bool(settings.DEBUG),
            },
        )
        t.start()

        self.message_user(
            request,
            _("Poll emails are being sent in the background."),
            level=messages.INFO,
        )

    @admin.action(description=_("Remind only members who haven't answered"))
    def remind_unanswered_members(self, request, queryset):
        if not is_new_poll_enabled():
            return

        if queryset.count() != 1:
            self.message_user(
                request,
                _("Please select exactly one poll."),
                level=messages.WARNING,
            )
            return

        poll = queryset.first()
        if not poll.is_open:
            self.message_user(
                request,
                _("This poll is already closed."),
                level=messages.WARNING,
            )
            return

        if poll.choices.count() < 2:
            self.message_user(
                request,
                _("Please define at least two choices before sending."),
                level=messages.ERROR,
            )
            return

        base_url = request.build_absolute_uri("/")
        t = threading.Thread(
            target=_send_poll_emails_worker,
            args=(poll.id, base_url),
            kwargs={
                "is_reminder": True,
                "only_customer_id": None,
                "mark_sent": False,
                "stop_on_first_in_debug": bool(settings.DEBUG),
            },
        )
        t.start()

        self.message_user(
            request,
            _("Reminder emails are being sent in the background."),
            level=messages.INFO,
        )

    @admin.action(description=_("Export results to Excel (.xlsx)"))
    def export_results_xlsx(self, request, queryset):
        if not is_new_poll_enabled():
            return

        if queryset.count() != 1:
            self.message_user(
                request,
                _("Please select exactly one poll to export."),
                level=messages.WARNING,
            )
            return

        poll = queryset.first()
        return export_poll_xlsx(poll)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .order_by(models.F("deadline").desc(nulls_last=True), "-created_at")
        )