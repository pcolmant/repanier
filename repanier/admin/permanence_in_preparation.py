import logging
import threading

import repanier.apps
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.checks import messages
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.template import Context as TemplateContext, Template
from django.urls import reverse_lazy, reverse, path
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from repanier.admin.admin_filter import AdminFilterPermanenceInPreparationStatus
from repanier.admin.forms import (
    OpenAndSendOfferForm,
    CloseAndSendOrderForm,
    GeneratePermanenceForm,
)
from repanier.admin.sale import (
    ProducerAutocomplete,
    SaleAdmin,
)
from repanier.admin.tools import (
    check_cancel_in_post,
    check_permanence,
)
from repanier.const import *
from repanier.email.email import RepanierEmail
from repanier.fields.RepanierMoneyField import RepanierMoney
from repanier.middleware import add_filter
from repanier.models.deliveryboard import DeliveryBoard
from repanier.models.permanenceboard import PermanenceBoard
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.models.staff import Staff
from repanier.task import task_order
from repanier.task.task_order import open_order, close_order
from repanier.tools import get_recurrence_dates, get_repanier_template_name
from repanier.xlsx.xlsx_offer import export_offer
from repanier.xlsx.xlsx_order import generate_producer_xlsx, generate_customer_xlsx

logger = logging.getLogger(__name__)


class PermanenceInPreparationAdmin(SaleAdmin):
    list_display = (
        "get_permanence_admin_display",
        "get_row_actions",
        "get_producers_with_download",
        "get_customers_with_download",
        "get_board",
        "get_html_status_display",
    )
    change_list_url = reverse_lazy("admin:repanier_permanenceinpreparation_changelist")
    description = "offer_description_v2"
    list_filter = (AdminFilterPermanenceInPreparationStatus,)
    ordering = (
        "invoice_sort_order",
        "canceled_invoice_sort_order",
        "permanence_date",
        "id",
    )

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return False
        if request.user.is_order_manager:
            if obj.highest_status == SaleStatus.PLANNED.value:
                return True
        return False

    def has_add_permission(self, request):
        return request.user.is_order_manager

    def has_change_permission(self, request, permanence=None):
        return request.user.is_order_manager

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "producer_autocomplete/",
                ProducerAutocomplete.as_view(),
                name="producer-autocomplete",
            ),
            path(
                "<int:permanence_id>/export-offer/",
                self.admin_site.admin_view(self.export_offer),
                name="permanence-export-offer",
            ),
            path(
                "<int:permanence_id>/export-customer-opened-order/",
                self.admin_site.admin_view(self.export_customer_opened_order),
                name="permanence-export-customer-opened-order",
            ),
            path(
                "<int:permanence_id>/export-customer-closed-order/",
                self.admin_site.admin_view(self.export_customer_closed_order),
                name="permanence-export-customer-closed-order",
            ),
            path(
                "<int:permanence_id>/export-producer-opened-order/",
                self.admin_site.admin_view(self.export_producer_opened_order),
                name="permanence-export-producer-opened-order",
            ),
            path(
                "<int:permanence_id>/export-producer-closed-order/",
                self.admin_site.admin_view(self.export_producer_closed_order),
                name="permanence-export-producer-closed-order",
            ),
            path(
                "<int:permanence_id>/open-order/",
                self.admin_site.admin_view(self.open_order),
                name="permanence-open-order",
            ),
            path(
                "<int:permanence_id>/close-order/",
                self.admin_site.admin_view(self.close_order),
                name="permanence-close-order",
            ),
            path(
                "<int:permanence_id>/back-to-scheduled/",
                self.admin_site.admin_view(self.back_to_scheduled),
                name="permanence-back-to-scheduled",
            ),
            path(
                "<int:permanence_id>/generate-permanence/",
                self.admin_site.admin_view(self.generate_permanence),
                name="generate-permanence",
            ),
        ]
        return custom_urls + urls

    @check_permanence(SaleStatus.PLANNED)
    def export_offer(self, request, permanence_id, permanence=None):
        wb = export_offer(permanence=permanence, wb=None)
        if wb is not None:
            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response[
                "Content-Disposition"
            ] = "attachment; filename={0}-{1}.xlsx".format(
                _("Preview report"), permanence
            )
            wb.save(response)
            return response
        else:
            return HttpResponseRedirect(self.get_redirect_to_change_list_url())

    export_offer.short_description = _("1 --- Check the offer")

    @check_cancel_in_post
    @check_permanence(SaleStatus.OPENED)
    def export_customer_opened_order(self, request, permanence_id, permanence=None):
        return self.export_customer_order(
            request, permanence, action="export_customer_opened_order"
        )

    @check_cancel_in_post
    @check_permanence(SaleStatus.SEND)
    def export_customer_closed_order(self, request, permanence_id, permanence=None):
        return self.export_customer_order(
            request, permanence, action="export_customer_closed_order"
        )

    def export_customer_order(self, request, permanence, action):
        if not permanence.with_delivery_point:
            # Perform the action directly. Do not ask to select any delivery point.
            response = None
            wb = generate_customer_xlsx(permanence=permanence)[0]
            if wb is not None:
                response = HttpResponse(
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                response[
                    "Content-Disposition"
                ] = "attachment; filename={0}-{1}.xlsx".format(
                    _("Customers"), permanence
                )
                wb.save(response)
            return response
        if "apply" in request.POST:
            if ACTION_CHECKBOX_NAME in request.POST:
                deliveries_to_be_exported = request.POST.getlist("deliveries", [])
                if len(deliveries_to_be_exported) == 0:
                    user_message = _("You must select at least one delivery point.")
                    user_message_level = messages.WARNING
                    self.message_user(request, user_message, user_message_level)
                    return HttpResponseRedirect(self.get_redirect_to_change_list_url())
                    # Also display order without delivery point -> The customer has not selected it yet
                    # deliveries_to_be_exported.append(None)
            else:
                deliveries_to_be_exported = ()
            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response[
                "Content-Disposition"
            ] = "attachment; filename={0}-{1}.xlsx".format(_("Customers"), permanence)
            wb = generate_customer_xlsx(
                permanence=permanence, deliveries_id=deliveries_to_be_exported
            )[0]
            if wb is not None:
                wb.save(response)
            return response
        template_name = get_repanier_template_name(
            "admin/confirm_export_customer_order.html"
        )
        return render(
            request,
            template_name,
            {
                **self.admin_site.each_context(request),
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
                "action": "export_customer_order",
                "permanence": permanence,
                "deliveries": DeliveryBoard.objects.filter(permanence_id=permanence.id),
            },
        )

    @check_permanence(SaleStatus.OPENED)
    def export_producer_opened_order(self, request, permanence_id, permanence=None):
        return self.export_producer_order(request, permanence)

    @check_permanence(SaleStatus.SEND)
    def export_producer_closed_order(self, request, permanence_id, permanence=None):
        return self.export_producer_order(request, permanence)

    def export_producer_order(self, request, permanence):
        # The export producer order use the offer item qty ordered
        # So that, this export is for all deliveries points
        # Perform the action directly. Do not ask to select any delivery point.
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename={0}-{1}.xlsx".format(
            _("Producers"), permanence
        )
        wb = None
        producer_set = Producer.objects.filter(permanence=permanence).order_by(
            "short_profile_name"
        )
        for producer in producer_set:
            wb = generate_producer_xlsx(permanence, producer=producer, wb=wb)
        if wb is not None:
            wb.save(response)
        return response

    @check_cancel_in_post
    @check_permanence(SaleStatus.PLANNED)
    def open_order(self, request, permanence_id, permanence=None):
        if "apply" in request.POST or "apply-wo-mail" in request.POST:
            send_mail = not ("apply-wo-mail" in request.POST)
            # open_order(permanence.id, send_mail)
            t = threading.Thread(target=open_order, args=(permanence.id, send_mail))
            t.start()
            user_message = _("The offers are being generated.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return HttpResponseRedirect(self.get_redirect_to_change_list_url())

        template_offer_mail = []
        template_cancel_order_mail = []
        email_will_be_sent, email_will_be_sent_to = RepanierEmail.send_email_to_who()

        if email_will_be_sent:
            order_responsible = Staff.get_or_create_order_responsible()

            template = Template(
                repanier.apps.REPANIER_SETTINGS_CONFIG.offer_customer_mail_v2
            )
            offer_description = permanence.offer_description_v2
            offer_producer = ", ".join(
                [p.short_profile_name for p in permanence.producers.all()]
            )
            qs = Product.objects.filter(
                producer=permanence.producers.first(),
                is_into_offer=True,
                order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,  # Don't display technical products.
            ).order_by("long_name_v2")[:5]
            offer_detail = "<ul>{}</ul>".format(
                "".join(
                    "<li>{producer}, {product}</li>".format(
                        producer=p.producer.short_profile_name,
                        product=p.get_long_name_with_customer_price(),
                    )
                    for p in qs
                )
            )
            context = TemplateContext(
                {
                    "offer_description": mark_safe(offer_description),
                    "offer_detail": offer_detail,
                    "offer_recent_detail": offer_detail,
                    "offer_producer": offer_producer,
                    "permanence_link": mark_safe(
                        '<a href="#">{}</a>'.format(permanence)
                    ),
                    "signature": order_responsible["html_signature"],
                }
            )
            template_offer_mail.append(template.render(context))

            if settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
                template = Template(
                    repanier.apps.REPANIER_SETTINGS_CONFIG.cancel_order_customer_mail_v2
                )

                context = TemplateContext(
                    {
                        "name": _("Long name"),
                        "long_basket_name": _("Long name"),
                        "basket_name": _("Short name"),
                        "short_basket_name": _("Short name"),
                        "permanence_link": mark_safe(
                            '<a href="#">{}</a>'.format(permanence)
                        ),
                        "signature": order_responsible["html_signature"],
                    }
                )
                template_cancel_order_mail.append(template.render(context))

        form = OpenAndSendOfferForm(
            initial={
                "template_offer_customer_mail": mark_safe(
                    "<br>==============<br>".join(template_offer_mail)
                ),
                "template_cancel_order_customer_mail": mark_safe(
                    "<br>==============<br>".join(template_cancel_order_mail)
                ),
            }
        )
        template_name = get_repanier_template_name("admin/confirm_open_order.html")
        return render(
            request,
            template_name,
            {
                **self.admin_site.each_context(request),
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
                "action": "open_order",
                "permanence": permanence,
                "form": form,
                "email_will_be_sent": email_will_be_sent,
                "email_will_be_sent_to": email_will_be_sent_to,
            },
        )

    @check_cancel_in_post
    @check_permanence(SaleStatus.OPENED)
    def close_order(self, request, permanence_id, permanence=None):

        if "apply" in request.POST or "apply-wo-mail" in request.POST:
            # request.POST.get("all-deliveries") return None if not set and "on" if set
            everything = not permanence.with_delivery_point or (
                True if request.POST.get("all-deliveries") else False
            )
            deliveries_to_be_send = request.POST.getlist("deliveries", [])
            # logger.debug(
            #     "all_deliveries : {}".format(request.POST.get("all-deliveries"))
            # )
            # logger.debug("everything : {}".format(everything))
            # logger.debug("deliveries_to_be_send : {}".format(deliveries_to_be_send))
            if (
                permanence.with_delivery_point
                and not everything
                and len(deliveries_to_be_send) == 0
            ):
                user_message = _("You must select at least one delivery point.")
                user_message_level = messages.WARNING
                self.message_user(request, user_message, user_message_level)
                return HttpResponseRedirect(self.get_redirect_to_change_list_url())
            send_mail = not ("apply-wo-mail" in request.POST)
            # close_order(permanence.id, everything, deliveries_to_be_send, send_mail)
            t = threading.Thread(
                target=close_order,
                args=(permanence.id, everything, deliveries_to_be_send, send_mail),
            )
            t.start()
            user_message = _("The orders are being send.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return HttpResponseRedirect(self.get_redirect_to_change_list_url())

        template_order_customer_mail = []
        template_order_producer_mail = []
        template_order_staff_mail = []
        email_will_be_sent, email_will_be_sent_to = RepanierEmail.send_email_to_who()
        (
            order_customer_email_will_be_sent,
            order_customer_email_will_be_sent_to,
        ) = RepanierEmail.send_email_to_who(is_email_send=True)
        (
            order_producer_email_will_be_sent,
            order_producer_email_will_be_sent_to,
        ) = RepanierEmail.send_email_to_who(is_email_send=True)
        (
            order_board_email_will_be_sent,
            order_board_email_will_be_sent_to,
        ) = RepanierEmail.send_email_to_who(
            is_email_send=repanier.apps.REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_BOARD,
            board=True,
        )

        if email_will_be_sent:

            order_responsible = Staff.get_or_create_order_responsible()

            if order_customer_email_will_be_sent:
                template = Template(
                    repanier.apps.REPANIER_SETTINGS_CONFIG.order_customer_mail_v2
                )

                customer_last_balance = _(
                    "The balance of your account as of %(date)s is %(balance)s."
                ) % {
                    "date": timezone.now().strftime(settings.DJANGO_SETTINGS_DATE),
                    "balance": RepanierMoney(123.45),
                }
                customer_on_hold_movement = _(
                    "This balance does not take account of any unrecognized payments %(bank)s and any unbilled order %(other_order)s."
                ) % {
                    "bank": RepanierMoney(123.45),
                    "other_order": RepanierMoney(123.45),
                }

                bank_account_number = repanier.apps.REPANIER_SETTINGS_BANK_ACCOUNT
                if bank_account_number is not None:
                    group_name = settings.REPANIER_SETTINGS_GROUP_NAME

                    if permanence.short_name_v2:
                        communication = "{} ({})".format(
                            _("Short name"), permanence.short_name_v2
                        )
                    else:
                        communication = _("Short name")
                    customer_payment_needed = '<font color="#bd0926">{}</font>'.format(
                        _(
                            "Please pay a provision of %(payment)s to the bank account %(name)s %(number)s with communication %(communication)s."
                        )
                        % {
                            "payment": RepanierMoney(123.45),
                            "name": group_name,
                            "number": bank_account_number,
                            "communication": communication,
                        }
                    )
                else:
                    customer_payment_needed = EMPTY_STRING
                context = TemplateContext(
                    {
                        "name": _("Long name"),
                        "long_basket_name": _("Long name"),
                        "basket_name": _("Short name"),
                        "short_basket_name": _("Short name"),
                        "permanence_link": mark_safe(
                            '<a href="#">{}</a>'.format(permanence)
                        ),
                        "last_balance": mark_safe(
                            '<a href="#">{}</a>'.format(customer_last_balance)
                        ),
                        "order_amount": RepanierMoney(123.45),
                        "on_hold_movement": mark_safe(customer_on_hold_movement),
                        "payment_needed": mark_safe(customer_payment_needed),
                        "delivery_point": _("Delivery point").upper(),
                        "signature": order_responsible["html_signature"],
                    }
                )

                template_order_customer_mail.append(template.render(context))

            if order_producer_email_will_be_sent:
                template = Template(
                    repanier.apps.REPANIER_SETTINGS_CONFIG.order_producer_mail_v2
                )
                context = TemplateContext(
                    {
                        "name": _("Long name"),
                        "long_profile_name": _("Long name"),
                        "order_empty": False,
                        "duplicate": True,
                        "permanence_link": format_html(
                            '<a href="#">{}</a>', permanence
                        ),
                        "signature": order_responsible["html_signature"],
                    }
                )

                template_order_producer_mail.append(template.render(context))

            if order_board_email_will_be_sent:
                board_composition = permanence.get_html_board_composition()
                template = Template(
                    repanier.apps.REPANIER_SETTINGS_CONFIG.order_staff_mail_v2
                )
                context = TemplateContext(
                    {
                        "permanence_link": format_html(
                            '<a href="#">{}</a>', permanence
                        ),
                        "board_composition": board_composition,
                        "board_composition_and_description": board_composition,
                        "signature": order_responsible["html_signature"],
                    }
                )

                template_order_staff_mail.append(template.render(context))

        form = CloseAndSendOrderForm(
            initial={
                "template_order_customer_mail": mark_safe(
                    "<br>==============<br>".join(template_order_customer_mail)
                ),
                "template_order_producer_mail": mark_safe(
                    "<br>==============<br>".join(template_order_producer_mail)
                ),
                "template_order_staff_mail": mark_safe(
                    "<br>==============<br>".join(template_order_staff_mail)
                ),
            }
        )
        if permanence.with_delivery_point:
            deliveries = DeliveryBoard.objects.filter(
                permanence_id=permanence.id,
                status__in=[SaleStatus.OPENED, SaleStatus.CLOSED],
            )
        else:
            deliveries = DeliveryBoard.objects.none()
        template_name = get_repanier_template_name("admin/confirm_close_order.html")
        return render(
            request,
            template_name,
            {
                **self.admin_site.each_context(request),
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
                "action": "close_order",
                "permanence": permanence,
                "deliveries": deliveries,
                "form": form,
                "email_will_be_sent": email_will_be_sent,
                "order_customer_email_will_be_sent_to": order_customer_email_will_be_sent_to,
                "order_producer_email_will_be_sent_to": order_producer_email_will_be_sent_to,
                "order_board_email_will_be_sent_to": order_board_email_will_be_sent_to,
            },
        )

    @check_cancel_in_post
    @check_permanence(SaleStatus.OPENED)
    def back_to_scheduled(self, request, permanence_id, permanence=None):
        if "apply" in request.POST:
            task_order.back_to_scheduled(permanence)
            user_message = _('The permanence is back to "Scheduled".')
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return HttpResponseRedirect(self.get_redirect_to_change_list_url())
        template_name = get_repanier_template_name("admin/confirm_action.html")
        return render(
            request,
            template_name,
            {
                **self.admin_site.each_context(request),
                "model_verbose_name_plural": _("Offers in preparation"),
                "sub_title": _("Please, confirm the action : back to scheduled"),
                "action": "back_to_scheduled",
                "permanence": permanence,
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
            },
        )

    @check_cancel_in_post
    @check_permanence(SaleStatus.PLANNED)
    def generate_permanence(self, request, permanence_id, permanence=None):
        if "apply" in request.POST:
            form = GeneratePermanenceForm(request.POST)
            if form.is_valid():
                recurrences = form.cleaned_data["recurrences"]
                dates = get_recurrence_dates(permanence.permanence_date, recurrences)
                creation_counter = permanence.duplicate(dates)
                if creation_counter == 0:
                    user_message = _("Nothing to do.")
                elif creation_counter == 1:
                    user_message = _("{} duplicate created.").format(creation_counter)
                else:
                    user_message = _("{} duplicates created.").format(creation_counter)
                user_message_level = messages.INFO
                self.message_user(request, user_message, user_message_level)
            return HttpResponseRedirect(self.get_redirect_to_change_list_url())
        else:
            form = GeneratePermanenceForm()
        template_name = get_repanier_template_name(
            "admin/confirm_generate_permanence.html"
        )
        return render(
            request,
            template_name,
            {
                **self.admin_site.each_context(request),
                "action": "generate_permanence",
                "permanence": permanence,
                "permanenceboard": PermanenceBoard.objects.filter(
                    permanence=permanence_id
                ).order_by("permanence_role"),
                "deliverypoint": DeliveryBoard.objects.filter(
                    permanence=permanence_id
                ).order_by("delivery_point"),
                "form": form,
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
            },
        )

    def get_row_actions(self, permanence):

        if permanence.status == SaleStatus.PLANNED.value:
            return format_html(
                '<div class="repanier-button-row">'
                '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-retweet"></i></a> '
                '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-play" style="color: #32CD32;"></i></a>'
                "</div>",
                add_filter(reverse("admin:generate-permanence", args=[permanence.pk])),
                _("Duplicate"),
                add_filter(
                    reverse("admin:permanence-open-order", args=[permanence.pk])
                ),
                _("Open orders"),
            )
        elif permanence.status == SaleStatus.OPENED.value:
            return format_html(
                '<div class="repanier-button-row">'
                '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-pencil-alt"></i></a> '
                '<a class="repanier-a-tooltip repanier-a-info" href="{}" data-repanier-tooltip="{}"><i class="fas fa-stop" style="color: red;"></i></a>'
                "</div>",
                add_filter(
                    reverse("admin:permanence-back-to-scheduled", args=[permanence.pk])
                ),
                _("Modify the offer"),
                add_filter(
                    reverse("admin:permanence-close-order", args=[permanence.pk])
                ),
                _("Close orders"),
            )
        return EMPTY_STRING

    get_row_actions.short_description = EMPTY_STRING

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(status__lte=SaleStatus.SEND.value)
