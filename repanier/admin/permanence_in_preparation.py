# -*- coding: utf-8
import logging
import threading

from django import forms
from django.contrib import admin
from django.core.checks import messages
from django.db import transaction
from django.db.models import F
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.template import Context as TemplateContext, Template
from django.utils import timezone
from django.utils import translation
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from parler.admin import TranslatableAdmin, TranslatableTabularInline
from parler.forms import TranslatableModelForm
from parler.utils.context import switch_language

import repanier.apps
from repanier.admin.forms import OpenAndSendOfferForm, CloseAndSendOrderForm, GeneratePermanenceForm
from repanier.admin.inline_foreign_key_cache_mixin import InlineForeignKeyCacheMixin
from repanier.const import *
from repanier.email.email import RepanierEmail
from repanier.fields.RepanierMoneyField import RepanierMoney
from repanier.models import Contract
from repanier.models.box import Box
from repanier.models.customer import Customer
from repanier.models.deliveryboard import DeliveryBoard
from repanier.models.lut import LUT_PermanenceRole, LUT_DeliveryPoint
from repanier.models.permanence import PermanenceInPreparation, Permanence
from repanier.models.permanenceboard import PermanenceBoard
from repanier.models.producer import Producer
from repanier.models.product import Product
from repanier.models.staff import Staff
from repanier.task import task_order
from repanier.task.task_order import pre_open_order, open_order, close_and_send_order
from repanier.tools import get_board_composition, get_recurrence_dates, get_repanier_template_name
from repanier.xlsx.xlsx_offer import export_offer
from repanier.xlsx.xlsx_order import generate_producer_xlsx, generate_customer_xlsx

logger = logging.getLogger(__name__)


class PermanenceBoardInline(InlineForeignKeyCacheMixin, admin.TabularInline):
    model = PermanenceBoard
    ordering = ("permanence_role__tree_id", "permanence_role__lft")
    fields = ['permanence_role', 'customer']
    extra = 0
    _has_add_or_delete_permission = None

    def has_delete_permission(self, request, obj=None):
        if self._has_add_or_delete_permission is None:
            try:
                parent_object = PermanenceInPreparation.objects.filter(id=request.resolver_match.args[0]).only(
                    "status").order_by('?').first()
                if parent_object is not None and parent_object.status == PERMANENCE_PLANNED:
                    self._has_add_or_delete_permission = True
                else:
                    self._has_add_or_delete_permission = False
            except:
                self._has_add_or_delete_permission = True
        return self._has_add_or_delete_permission

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_delete_permission(request)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super(PermanenceBoardInline, self).get_formset(request, obj, **kwargs)
        form = formset.form
        widget = form.base_fields['permanence_role'].widget
        widget.can_add_related = True
        widget.can_change_related = True
        widget.can_delete_related = False
        widget = form.base_fields['customer'].widget
        widget.can_add_related = False
        widget.can_change_related = False
        widget.can_delete_related = False
        return formset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "customer":
            kwargs["queryset"] = Customer.objects.filter(may_order=True)
        if db_field.name == "permanence_role":
            kwargs["queryset"] = LUT_PermanenceRole.objects.filter(is_active=True, rght=F('lft') + 1).order_by(
                "tree_id", "lft")
        return super(PermanenceBoardInline, self).formfield_for_foreignkey(db_field, request, **kwargs)


class DeliveryBoardInline(InlineForeignKeyCacheMixin, TranslatableTabularInline):
    model = DeliveryBoard
    ordering = ("id",)
    fields = ['delivery_comment', 'delivery_point', 'status', ]
    extra = 0
    readonly_fields = ['status', ]
    _has_add_or_delete_permission = None

    def has_delete_permission(self, request, obj=None):
        if self._has_add_or_delete_permission is None:
            try:
                parent_object = PermanenceInPreparation.objects.filter(
                    id=request.resolver_match.args[0]
                ).only("status").order_by('?').first()
                if parent_object is not None and parent_object.status == PERMANENCE_PLANNED:
                    self._has_add_or_delete_permission = True
                else:
                    self._has_add_or_delete_permission = False
            except:
                self._has_add_or_delete_permission = True
        return self._has_add_or_delete_permission

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_delete_permission(request)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super(DeliveryBoardInline, self).get_formset(request, obj, **kwargs)
        form = formset.form
        widget = form.base_fields['delivery_comment'].widget
        widget.attrs['size'] = "100%"
        widget = form.base_fields['delivery_point'].widget
        widget.can_add_related = False
        widget.can_change_related = False
        widget.can_delete_related = False
        return formset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "delivery_point":
            kwargs["queryset"] = LUT_DeliveryPoint.objects.filter(
                is_active=True, rght=F('lft') + 1
            ).order_by("tree_id", "lft")
        return super(DeliveryBoardInline, self).formfield_for_foreignkey(db_field, request, **kwargs)


class PermanenceInPreparationForm(TranslatableModelForm):
    short_name = forms.CharField(
        label=_("Offer name"),
        widget=forms.TextInput(attrs={'style': "width:100% !important"}),
        required=False
    )

    def __init__(self, *args, **kwargs):
        super(PermanenceInPreparationForm, self).__init__(*args, **kwargs)
        if settings.REPANIER_SETTINGS_CONTRACT:
            if "contract" in self.fields:
                contract_field = self.fields["contract"]
                contract_field.widget.can_add_related = False
                contract_field.widget.can_change_related = False
                contract_field.widget.can_delete_related = False

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        if settings.REPANIER_SETTINGS_CONTRACT:
            contract = self.cleaned_data.get("contract", None)
            if contract is not None:
                producers = self.cleaned_data.get("producers", None)
                if producers:
                    self.add_error('producers', _('No producer may be selected if a contract is also selected.'))
                if settings.REPANIER_SETTINGS_BOX:
                    boxes = self.cleaned_data.get("boxes", None)
                    if boxes:
                        self.add_error('boxes', _('No box may be selected if a contract is also selected.'))
        return

    class Meta:
        model = PermanenceInPreparation
        fields = "__all__"


class PermanenceInPreparationAdmin(TranslatableAdmin):
    form = PermanenceInPreparationForm
    list_per_page = 10
    list_max_show_all = 10
    filter_horizontal = ('producers', 'boxes')
    inlines = [DeliveryBoardInline, PermanenceBoardInline]
    date_hierarchy = 'permanence_date'
    list_display = (
        'get_permanence_admin_display',
    )
    ordering = ('-status', 'permanence_date', 'id')
    # action_form = RepanierActionForm
    actions = [
        'export_xlsx_offer',
        'open_and_send_offer',
        'back_to_scheduled',
        'export_xlsx_customer_order',
        'export_xlsx_producer_order',
        'close_and_send_order',
        'generate_permanence'
    ]

    # def get_changelist(self, request, **kwargs):
    #     return PermanenceInPreparationChangeList

    def has_delete_permission(self, request, obj=None):
        user = request.user
        if user.is_order_manager:
            return True
        return False

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_delete_permission(request, obj)

    def get_list_display(self, request):
        list_display = [
            'get_permanence_admin_display',
        ]
        if settings.DJANGO_SETTINGS_MULTIPLE_LANGUAGE:
            list_display += [
                'language_column',
            ]
        list_display += [
            'get_producers', 'get_customers', 'get_board', 'get_html_status_display',
        ]
        return list_display

    def get_fields(self, request, permanence=None):
        fields = [
            ('permanence_date', 'picture'),
            'automatically_closed',
            'short_name',
            'offer_description'
        ]
        if settings.REPANIER_SETTINGS_CONTRACT:
            fields.append('contract')
        fields += [
            'producers'
        ]
        if settings.REPANIER_SETTINGS_BOX:
            fields.append('boxes')
        return fields

    def get_readonly_fields(self, request, permanence=None):
        if permanence is not None and permanence.status > PERMANENCE_PLANNED:
            readonly_fields = ['status', 'producers']
            if settings.REPANIER_SETTINGS_CONTRACT:
                readonly_fields += ['contract']
            if settings.REPANIER_SETTINGS_BOX:
                readonly_fields += ['boxes']
            return readonly_fields
        return ['status']

    def get_formsets_with_inlines(self, request, obj=None):
        for inline in self.get_inline_instances(request, obj):
            # hide DeliveryBoardInline if no delivery point
            if isinstance(inline, DeliveryBoardInline) \
                    and not LUT_DeliveryPoint.objects.filter(is_active=True).exists():
                continue
            # hide DeliveryBoardInline if no permanence role
            if isinstance(inline, PermanenceBoardInline) \
                    and not LUT_PermanenceRole.objects.filter(is_active=True).exists():
                continue
            yield inline.get_formset(request, obj), inline

    def export_xlsx_offer(self, request, queryset):
        permanence = queryset.first()
        if permanence.status not in [PERMANENCE_PLANNED, PERMANENCE_OPENED]:
            user_message = _("The status of %(permanence)s prohibit you to perform this action.") % {
                'permanence': permanence}
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return
        wb = export_offer(permanence=permanence, wb=None)
        if wb is not None:
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = "attachment; filename={0}-{1}.xlsx".format(
                _("Preview report"),
                permanence
            )
            wb.save(response)
            return response
        else:
            return

    export_xlsx_offer.short_description = _("1 --- Check the offer")

    def export_xlsx_customer_order(self, request, queryset):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return
        permanence = queryset.first()
        if permanence.status not in [PERMANENCE_OPENED, PERMANENCE_CLOSED, PERMANENCE_SEND]:
            user_message = _("The status of %(permanence)s prohibit you to perform this action.") % {
                'permanence': permanence}
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return
        if not permanence.with_delivery_point:
            # Perform the action directly. Do not ask to select any delivery point.
            response = None
            wb = generate_customer_xlsx(permanence=permanence)[0]
            if wb is not None:
                response = HttpResponse(
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                response['Content-Disposition'] = "attachment; filename={0}-{1}.xlsx".format(
                    _("Customers"),
                    permanence
                )
                wb.save(response)
            return response
        if 'apply' in request.POST:
            if admin.ACTION_CHECKBOX_NAME in request.POST:
                deliveries_to_be_exported = request.POST.getlist("deliveries", [])
                if len(deliveries_to_be_exported) == 0:
                    user_message = _("You must select at least one delivery point.")
                    user_message_level = messages.WARNING
                    self.message_user(request, user_message, user_message_level)
                    return
                    # Also display order without delivery point -> The customer has not selected it yet
                    # deliveries_to_be_exported.append(None)
            else:
                deliveries_to_be_exported = ()
            response = None
            wb = generate_customer_xlsx(permanence=permanence, deliveries_id=deliveries_to_be_exported)[0]
            if wb is not None:
                response = HttpResponse(
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                response['Content-Disposition'] = "attachment; filename={0}-{1}.xlsx".format(
                    _("Customers"),
                    permanence
                )
                wb.save(response)
            return response
        template_name = get_repanier_template_name("confirm_admin_export_customer_order.html")
        return render(
            request,
            template_name, {
                'sub_title': _("Please, confirm the action : Export customer orders"),
                'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
                'action': 'export_xlsx_customer_order',
                'permanence': permanence,
                'deliveries': DeliveryBoard.objects.filter(
                    permanence_id=permanence.id
                ),
            })

    export_xlsx_customer_order.short_description = _("Export customer orders")

    def export_xlsx_producer_order(self, request, queryset):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return
        permanence = queryset.first()
        if permanence.status not in [PERMANENCE_OPENED, PERMANENCE_CLOSED, PERMANENCE_SEND]:
            user_message = _("The status of %(permanence)s prohibit you to perform this action.") % {
                'permanence': permanence}
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return
        # The export producer order use the offer item qty ordered
        # So that, this export is for all deliveries points
        # Perform the action directly. Do not ask to select any delivery point.
        wb = None
        producer_set = Producer.objects.filter(permanence=permanence).order_by("short_profile_name")
        for producer in producer_set:
            wb = generate_producer_xlsx(permanence, producer=producer, wb=wb)
        if wb is not None:
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = "attachment; filename={0}-{1}.xlsx".format(
                _("Producers"),
                permanence
            )
            wb.save(response)
            return response
        else:
            return

    export_xlsx_producer_order.short_description = _("Export producer orders")

    def open_and_send_offer(self, request, queryset):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return
        permanence = queryset.first()
        if permanence.status not in [PERMANENCE_PLANNED, PERMANENCE_PRE_OPEN]:
            user_message = _("The status of %(permanence)s prohibit you to perform this action.") % {
                'permanence': permanence}
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return
        pre_open = (permanence.status == PERMANENCE_PLANNED) and Producer.objects.filter(
            permanence__id=permanence.id, is_active=True, producer_pre_opening=True
        ).order_by('?').exists()
        if pre_open:
            template_offer_mail = []
            template_cancel_order_mail = []
            cur_language = translation.get_language()
            for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
                language_code = language["code"]
                translation.activate(language_code)

                with switch_language(repanier.apps.REPANIER_SETTINGS_CONFIG, language_code):
                    template = Template(repanier.apps.REPANIER_SETTINGS_CONFIG.offer_producer_mail)

                staff = Staff.get_or_create_order_responsible()

                with switch_language(permanence, language_code):
                    offer_description = permanence.safe_translation_getter(
                        'offer_description', any_language=True, default=EMPTY_STRING
                    )
                context = TemplateContext({
                    'name': _('Long name'),
                    'long_profile_name': _('Long name'),
                    'permanence_link': mark_safe("<a href=\"#\">{}</a>".format(_("Offers"))),
                    'offer_description': mark_safe(offer_description),
                    'offer_link': mark_safe("<a href=\"#\">{}</a>".format(_("Offers"))),
                    'signature': staff.get_html_signature,
                })
                template_offer_mail.append(language_code)
                template_offer_mail.append(template.render(context))
            translation.activate(cur_language)
            email_will_be_sent, email_will_be_sent_to = RepanierEmail.send_email_to_who()
        else:
            template_offer_mail = []
            template_cancel_order_mail = []
            cur_language = translation.get_language()
            for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
                language_code = language["code"]
                translation.activate(language_code)

                with switch_language(repanier.apps.REPANIER_SETTINGS_CONFIG, language_code):
                    template = Template(repanier.apps.REPANIER_SETTINGS_CONFIG.offer_customer_mail)

                staff = Staff.get_or_create_order_responsible()

                with switch_language(permanence, language_code):
                    offer_description = permanence.safe_translation_getter(
                        'offer_description', any_language=True, default=EMPTY_STRING
                    )
                offer_producer = ', '.join([p.short_profile_name for p in permanence.producers.all()])
                qs = Product.objects.filter(
                    producer=permanence.producers.first(),
                    is_into_offer=True,
                    order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT  # Don't display technical products.
                ).order_by(
                    "translations__long_name"
                )[:5]
                offer_detail = "<ul>{}</ul>".format("".join("<li>{}, {}</li>".format(
                    p.get_long_name(),
                    p.producer.short_profile_name
                )
                                                            for p in qs
                                                            ), )
                context = TemplateContext({
                    'offer_description': mark_safe(offer_description),
                    'offer_detail': offer_detail,
                    'offer_recent_detail': offer_detail,
                    'offer_producer': offer_producer,
                    'permanence_link': mark_safe("<a href=\"#\">{}</a>".format(permanence)),
                    'signature': staff.get_html_signature,
                })
                template_offer_mail.append(language_code)
                template_offer_mail.append(template.render(context))
                if settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
                    context = TemplateContext({
                        'name': _('Long name'),
                        'long_basket_name': _('Long name'),
                        'basket_name': _('Short name'),
                        'short_basket_name': _('Short name'),
                        'permanence_link': mark_safe("<a href=\"#\">{}</a>".format(permanence)),
                        'signature': staff.get_html_signature,
                    })
                    template_cancel_order_mail.append(language_code)
                    template_cancel_order_mail.append(template.render(context))
            translation.activate(cur_language)
            email_will_be_sent, email_will_be_sent_to = RepanierEmail.send_email_to_who()
        if 'apply' in request.POST or 'apply-wo-mail' in request.POST:
            form = OpenAndSendOfferForm(request.POST)
            if form.is_valid():
                do_not_send_any_mail = 'apply-wo-mail' in request.POST
                if pre_open:
                    permanence_already_pre_opened = Permanence.objects.filter(
                        status__in=[PERMANENCE_WAIT_FOR_PRE_OPEN, PERMANENCE_PRE_OPEN]
                    ).order_by("-is_updated_on").only("id").first()
                    if permanence_already_pre_opened is not None:
                        user_message = _("A maximum of one permanence may be pre opened.")
                        user_message_level = messages.ERROR
                    else:
                        # pre_open_order(permanence.id)
                        t = threading.Thread(target=pre_open_order, args=(permanence.id,))
                        t.start()
                        user_message = _("The offers are being generated.")
                        user_message_level = messages.INFO
                else:
                    # open_order(permanence.id, do_not_send_any_mail)
                    t = threading.Thread(target=open_order, args=(permanence.id, do_not_send_any_mail))
                    t.start()
                    user_message = _("The offers are being generated.")
                    user_message_level = messages.INFO
                self.message_user(request, user_message, user_message_level)
            return HttpResponseRedirect(request.get_full_path())
        else:
            form = OpenAndSendOfferForm(
                initial={
                    'template_offer_customer_mail': mark_safe(
                        "<br>==============<br>".join(template_offer_mail)),
                    'template_cancel_order_customer_mail': mark_safe(
                        "<br>==============<br>".join(template_cancel_order_mail)),
                }
            )
        template_name = get_repanier_template_name(
            'confirm_admin_open_and_send_offer.html'
        )
        return render(
            request,
            template_name, {
                'sub_title': _("Please, confirm the action : open and send offers"),
                'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
                'action': 'open_and_send_offer',
                'permanence': permanence,
                'pre_open': pre_open,
                'form': form,
                'email_will_be_sent': email_will_be_sent,
                'email_will_be_sent_to': email_will_be_sent_to
            })

    open_and_send_offer.short_description = _('2 --- Open orders')

    def close_and_send_order(self, request, queryset):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return
        permanence = queryset.first()
        if permanence.status not in [PERMANENCE_OPENED, PERMANENCE_CLOSED]:
            user_message = _("The status of %(permanence)s prohibit you to perform this action.") % {
                'permanence': permanence}
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return
        if 'apply' in request.POST:
            all_deliveries = True if request.POST.get("all-deliveries", True) else False
            deliveries_to_be_send = request.POST.getlist("deliveries", [])
            logger.debug("all_deliveries : {}".format(request.POST.get("all-deliveries")))
            logger.debug("all_deliveries : {}".format(all_deliveries))
            logger.debug("deliveries_to_be_send : {}".format(request.POST.getlist("deliveries", [])))
            if permanence.with_delivery_point and not all_deliveries and len(deliveries_to_be_send) == 0:
                user_message = _("You must select at least one delivery point.")
                user_message_level = messages.WARNING
                self.message_user(request, user_message, user_message_level)
                return
            # close_and_send_order(permanence.id, all_deliveries, deliveries_to_be_send)
            t = threading.Thread(target=close_and_send_order,
                                 args=(permanence.id, all_deliveries, deliveries_to_be_send))
            t.start()
            user_message = _("The orders are being send.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return

        template_order_customer_mail = []
        template_order_producer_mail = []
        template_order_staff_mail = []
        cur_language = translation.get_language()
        for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
            language_code = language["code"]
            translation.activate(language_code)

            template = Template(repanier.apps.REPANIER_SETTINGS_CONFIG.order_customer_mail)

            staff = Staff.get_or_create_order_responsible()

            customer_last_balance = \
                _('The balance of your account as of %(date)s is %(balance)s.') % {
                    'date': timezone.now().strftime(settings.DJANGO_SETTINGS_DATE),
                    'balance': RepanierMoney(123.45)
                }
            customer_on_hold_movement = \
                _(
                    'This balance does not take account of any unrecognized payments %(bank)s and any unbilled order %(other_order)s.') \
                % {
                    'bank': RepanierMoney(123.45),
                    'other_order': RepanierMoney(123.45)
                }

            bank_account_number = repanier.apps.REPANIER_SETTINGS_BANK_ACCOUNT
            if bank_account_number is not None:
                group_name = settings.REPANIER_SETTINGS_GROUP_NAME

                if permanence.short_name:
                    communication = "{} ({})".format(_('Short name'), permanence.short_name)
                else:
                    communication = _('Short name')
                customer_payment_needed = "<font color=\"#bd0926\">{}</font>".format(
                    _(
                        'Please pay a provision of %(payment)s to the bank account %(name)s %(number)s with communication %(communication)s.') % {
                        'payment': RepanierMoney(123.45),
                        'name': group_name,
                        'number': bank_account_number,
                        'communication': communication
                    }
                )
            else:
                customer_payment_needed = EMPTY_STRING
            context = TemplateContext({
                'name': _('Long name'),
                'long_basket_name': _('Long name'),
                'basket_name': _('Short name'),
                'short_basket_name': _('Short name'),
                'permanence_link': mark_safe("<a href=\"#\">{}</a>".format(permanence)),
                'last_balance': mark_safe("<a href=\"#\">{}</a>".format(customer_last_balance)),
                'order_amount': RepanierMoney(123.45),
                'on_hold_movement': mark_safe(customer_on_hold_movement),
                'payment_needed': mark_safe(customer_payment_needed),
                'delivery_point': _('Delivery point').upper(),
                'signature': staff.get_html_signature,
            })

            template_order_customer_mail.append(language_code)
            template_order_customer_mail.append(template.render(context))

            template = Template(repanier.apps.REPANIER_SETTINGS_CONFIG.order_producer_mail)
            context = TemplateContext({
                'name': _('Long name'),
                'long_profile_name': _('Long name'),
                'order_empty': False,
                'duplicate': True,
                'permanence_link': format_html("<a href=\"#\">{}</a>", permanence),
                'signature': staff.get_html_signature,
            })

            template_order_producer_mail.append(language_code)
            template_order_producer_mail.append(template.render(context))

            board_composition, board_composition_and_description = get_board_composition(permanence.id)
            template = Template(repanier.apps.REPANIER_SETTINGS_CONFIG.order_staff_mail)
            context = TemplateContext({
                'permanence_link': format_html("<a href=\"#\">{}</a>", permanence),
                'board_composition': mark_safe(board_composition),
                'board_composition_and_description': mark_safe(board_composition_and_description),
                'signature': staff.get_html_signature,
            })

            template_order_staff_mail.append(language_code)
            template_order_staff_mail.append(template.render(context))

        translation.activate(cur_language)

        order_customer_email_will_be_sent, order_customer_email_will_be_sent_to = RepanierEmail.send_email_to_who(
            is_email_send=True
        )
        order_producer_email_will_be_sent, order_producer_email_will_be_sent_to = RepanierEmail.send_email_to_who(
            is_email_send=True
        )
        order_board_email_will_be_sent, order_board_email_will_be_sent_to = RepanierEmail.send_email_to_who(
            is_email_send=repanier.apps.REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_BOARD,
            board=True
        )

        form = CloseAndSendOrderForm(
            initial={
                'template_order_customer_mail': mark_safe(
                    "<br>==============<br>".join(template_order_customer_mail)),
                'template_order_producer_mail': mark_safe(
                    "<br>==============<br>".join(template_order_producer_mail)),
                'template_order_staff_mail': mark_safe("<br>==============<br>".join(template_order_staff_mail)),
            }
        )
        if permanence.with_delivery_point:
            deliveries = DeliveryBoard.objects.filter(
                permanence_id=permanence.id,
                status__in=[PERMANENCE_OPENED, PERMANENCE_CLOSED]
            )
        else:
            deliveries = DeliveryBoard.objects.none()
        template_name = get_repanier_template_name("confirm_admin_send_order.html")
        return render(
            request,
            template_name, {
                'sub_title': _("Please, confirm the action : send orders"),
                'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
                'action': 'close_and_send_order',
                'permanence': permanence,
                'with_delivery_point': permanence.with_delivery_point,
                'deliveries': deliveries,
                'form': form,
                'order_customer_email_will_be_sent': order_customer_email_will_be_sent,
                'order_customer_email_will_be_sent_to': order_customer_email_will_be_sent_to,
                'order_producer_email_will_be_sent': order_producer_email_will_be_sent,
                'order_producer_email_will_be_sent_to': order_producer_email_will_be_sent_to,
                'order_board_email_will_be_sent': order_board_email_will_be_sent,
                'order_board_email_will_be_sent_to': order_board_email_will_be_sent_to
            })

    close_and_send_order.short_description = _('3 --- Close and transmit orders')

    def back_to_scheduled(self, request, queryset):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return
        permanence = queryset.first()
        if permanence.status != PERMANENCE_OPENED:
            user_message = _("The status of %(permanence)s prohibit you to perform this action.") % {
                'permanence': permanence}
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return
        if 'apply' in request.POST:
            task_order.back_to_scheduled(permanence)
            user_message = _("The permanence is back to scheduled.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return
        template_name = get_repanier_template_name("confirm_admin_action.html")
        return render(request, template_name, {
            'sub_title': _("Please, confirm the action : back to scheduled"),
            'action': 'back_to_scheduled',
            'permanence': permanence,
            'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
        })

    back_to_scheduled.short_description = _('Return to scheduled status to change bid')

    def generate_permanence(self, request, queryset):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return
        permanence = queryset.first()
        if permanence.status not in [
            PERMANENCE_PLANNED, PERMANENCE_PRE_OPEN, PERMANENCE_OPENED, PERMANENCE_CLOSED, PERMANENCE_SEND
        ]:
            user_message = _("The status of %(permanence)s prohibit you to perform this action.") % {
                'permanence': permanence}
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return
        if 'apply' in request.POST:
            form = GeneratePermanenceForm(request.POST)
            if form.is_valid():
                recurrences = form.cleaned_data['recurrences']
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
            return HttpResponseRedirect(request.get_full_path())
        else:
            form = GeneratePermanenceForm()
        template_name = get_repanier_template_name("confirm_admin_generate_permanence.html")
        return render(request, template_name, {
            'sub_title': _("How many weekly permanence(s) do you want to generate from this ?"),
            'action': 'generate_permanence',
            'permanence': permanence,
            'form': form,
            'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
        })

    generate_permanence.short_description = _("Duplicate")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "contract":
            kwargs["queryset"] = Contract.objects.filter(is_active=True)
        return super(PermanenceInPreparationAdmin, self).formfield_for_foreignkey(
            db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "producers":
            kwargs["queryset"] = Producer.objects.filter(is_active=True)
        if db_field.name == "boxes":
            kwargs["queryset"] = Box.objects.filter(is_box=True, is_into_offer=True)
        return super(PermanenceInPreparationAdmin, self).formfield_for_manytomany(
            db_field, request, **kwargs)

    def get_queryset(self, request):
        qs = super(PermanenceInPreparationAdmin, self).get_queryset(request)
        return qs.filter(
            status__lte=PERMANENCE_SEND
        )

    @transaction.atomic
    def save_related(self, request, form, formsets, change):
        super(PermanenceInPreparationAdmin, self).save_related(
            request, form, formsets, change)
        permanence = form.instance
        permanence.with_delivery_point = DeliveryBoard.objects.filter(permanence_id=permanence.id).exists()
        form.instance.save(update_fields=['with_delivery_point'])

    def save_model(self, request, permanence, form, change):
        if change and ('permanence_date' in form.changed_data):
            PermanenceBoard.objects.filter(permanence_id=permanence.id).update(
                permanence_date=permanence.permanence_date)
        super(PermanenceInPreparationAdmin, self).save_model(
            request, permanence, form, change)
