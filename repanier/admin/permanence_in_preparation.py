# -*- coding: utf-8
from __future__ import unicode_literals

import datetime

from django.conf import settings
from django.contrib import admin
from django.shortcuts import render
from django.utils import timezone
from django.core.checks import messages
from django.db.models import F, Q
from django.http import HttpResponseRedirect
from django.template import Context as TemplateContext, Template
from django.utils import translation
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _
from parler.admin import TranslatableAdmin, TranslatableTabularInline
from parler.models import TranslationDoesNotExist
from parler.utils.context import switch_language

import repanier.apps
from repanier.admin.fkey_choice_cache_mixin import ForeignKeyCacheMixin
from repanier.admin.forms import OpenAndSendOfferForm, CloseAndSendOrderForm, GeneratePermanenceForm
from repanier.const import *
from repanier.fields.RepanierMoneyField import RepanierMoney
from repanier.models import Customer, Purchase, Producer, PermanenceBoard, LUT_PermanenceRole, PermanenceInPreparation, \
    Box, OfferItem, DeliveryBoard, LUT_DeliveryPoint, ProducerInvoice, Product
from repanier.task import task_order, task_purchase
from repanier.tools import send_email_to_who, get_signature, get_board_composition
from repanier.xlsx import xlsx_offer, xlsx_order


class PermanenceBoardInline(ForeignKeyCacheMixin, admin.TabularInline):
    model = PermanenceBoard
    ordering = ("permanence_role__tree_id", "permanence_role__lft")
    fields = ['permanence_role', 'customer']
    extra = 0
    has_add_or_delete_permission = None

    def has_delete_permission(self, request, obj=None):
        if self.has_add_or_delete_permission is None:
            try:
                parent_object = PermanenceInPreparation.objects.filter(id=request.resolver_match.args[0]).only(
                    "status").order_by('?').first()
                if parent_object is not None and parent_object.status > PERMANENCE_PLANNED:
                    self.has_add_or_delete_permission = False
                else:
                    self.has_add_or_delete_permission = True
            except:
                self.has_add_or_delete_permission = True
        return self.has_add_or_delete_permission

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "customer":
            kwargs["queryset"] = Customer.objects.filter(may_order=True)
        if db_field.name == "permanence_role":
            kwargs["queryset"] = LUT_PermanenceRole.objects.filter(is_active=True, rght=F('lft') + 1).order_by(
                "tree_id", "lft")
        return super(PermanenceBoardInline, self).formfield_for_foreignkey(db_field, request, **kwargs)


class DeliveryBoardInline(ForeignKeyCacheMixin, TranslatableTabularInline):
    model = DeliveryBoard
    ordering = ("id",)
    # ordering = ("delivery_date", "delivery_point__tree_id", "delivery_point__lft",)
    fields = ['delivery_date', 'delivery_comment', 'delivery_point', 'status', ]
    extra = 0
    readonly_fields = ['status', ]
    has_add_or_delete_permission = None

    def has_delete_permission(self, request, obj=None):
        if self.has_add_or_delete_permission is None:
            try:
                parent_object = PermanenceInPreparation.objects.filter(id=request.resolver_match.args[0]).only(
                    "highest_status").order_by('?').first()
                if parent_object is not None and parent_object.highest_status > PERMANENCE_PLANNED:
                    self.has_add_or_delete_permission = False
                else:
                    self.has_add_or_delete_permission = True
            except:
                self.has_add_or_delete_permission = True
        return self.has_add_or_delete_permission

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "delivery_point":
            kwargs["queryset"] = LUT_DeliveryPoint.objects.filter(is_active=True, rght=F('lft') + 1).order_by("tree_id",
                                                                                                              "lft")
        return super(DeliveryBoardInline, self).formfield_for_foreignkey(db_field, request, **kwargs)


class PermanenceInPreparationAdmin(TranslatableAdmin):
    exclude = ['invoice_description']
    list_per_page = 10
    list_max_show_all = 10
    filter_horizontal = ('producers',)
    inlines = [DeliveryBoardInline, PermanenceBoardInline]
    date_hierarchy = 'permanence_date'
    list_display = (
    '__str__', 'all_languages_column', 'get_producers', 'get_customers', 'get_board', 'get_full_status_display')
    ordering = ('permanence_date',)
    if settings.DJANGO_SETTINGS_ENV == "dev":
        actions = [
            'export_xlsx_offer',
            'open_and_send_offer',
            'back_to_planned',
            'undo_back_to_planned',
            'close_order',
            'export_xlsx_customer_order',
            'export_xlsx_producer_order',
            'delete_purchases',  # DEV Only
            'send_order',
            'generate_permanence'
        ]
    else:
        actions = [
            'export_xlsx_offer',
            'open_and_send_offer',
            'back_to_planned',
            'undo_back_to_planned',
            'close_order',
            'export_xlsx_customer_order',
            'export_xlsx_producer_order',
            'send_order',
            'generate_permanence'
        ]

    def has_delete_permission(self, request, obj=None):
        if request.user.groups.filter(
                name__in=[ORDER_GROUP, INVOICE_GROUP, COORDINATION_GROUP]).exists() or request.user.is_superuser:
            return True
        return False

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def has_change_permission(self, request, obj=None):
        if request.user.groups.filter(
                name__in=[ORDER_GROUP, INVOICE_GROUP, COORDINATION_GROUP]).exists() or request.user.is_superuser:
            return True
        return False

    def get_fields(self, request, permanence=None):
        fields = [
            ('permanence_date', 'short_name',),
            'automatically_closed',
            'offer_description',
            'producers',
            'get_boxes'
        ]
        return fields

    def get_readonly_fields(self, request, permanence=None):
        if permanence is not None:
            if permanence.status > PERMANENCE_PLANNED:
                return ['status', 'producers', 'get_boxes']
        return ['status', 'get_boxes']

    def get_boxes(self, obj=None):
        if obj is None or obj.status == PERMANENCE_PLANNED:
            qs = Box.objects.filter(
                is_box=True,
                is_into_offer=True,
                translations__language_code=translation.get_language()
            ).order_by(
                "customer_unit_price",
                "unit_deposit",
                "translations__long_name"
            )
            result = ", ".join(o.long_name for o in qs)
        else:
            qs = OfferItem.objects.filter(
                permanence_id=obj.id,
                is_box=True,
                may_order=True,
                translations__language_code=translation.get_language()
            ).order_by(
                "translations__preparation_sort_order"
            )
            result = ", ".join(o.long_name for o in qs)
        return result if result is not None else _("None")

    get_boxes.short_description = _("boxes")

    def export_xlsx_offer(self, request, queryset):
        permanence = queryset.order_by('?').first()
        if permanence is None or permanence.status not in [PERMANENCE_PLANNED, PERMANENCE_OPENED]:
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return None
        return xlsx_offer.admin_export(request, permanence)

    export_xlsx_offer.short_description = _("Export planned xlsx")

    def export_xlsx_customer_order(self, request, queryset):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return None
        permanence = queryset.order_by('?').first()
        if permanence is None or permanence.status not in [PERMANENCE_OPENED, PERMANENCE_CLOSED, PERMANENCE_SEND]:
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return None
        if not permanence.with_delivery_point:
            # Perform the action directly. Do not ask to select any delivery point.
            return xlsx_order.admin_customer_export(
                permanence, deliveries_id=None
            )
        if 'apply' in request.POST:
            if admin.ACTION_CHECKBOX_NAME in request.POST:
                deliveries_to_be_exported = request.POST.getlist("deliveries")
                if len(deliveries_to_be_exported) == 0:
                    user_message = _("You must select at least one delivery to export.")
                    user_message_level = messages.WARNING
                    self.message_user(request, user_message, user_message_level)
                    return None
            else:
                deliveries_to_be_exported = None
            return xlsx_order.admin_customer_export(
                permanence, deliveries_id=deliveries_to_be_exported
            )
        return render(
            request,
            'repanier/confirm_admin_export_customer_order.html', {
                'sub_title'           : _("Please, confirm the action : export customers orders"),
                'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
                'action'              : 'export_xlsx_customer_order',
                'permanence'          : permanence,
                'deliveries'          : DeliveryBoard.objects.filter(
                    permanence_id=permanence.id
                ).order_by("id"),
            })

    export_xlsx_customer_order.short_description = _("Export xlsx customers orders")

    def export_xlsx_producer_order(self, request, queryset):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return None
        permanence = queryset.order_by('?').first()
        if permanence is None or permanence.status not in [PERMANENCE_OPENED, PERMANENCE_CLOSED, PERMANENCE_SEND]:
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return None
        # The export producer order use the offer item qty ordered
        # So that, this export is for all deliveries points
        # Perform the action directly. Do not ask to select any delivery point.
        return xlsx_order.admin_producer_export(
            permanence
        )

    export_xlsx_producer_order.short_description = _("Export xlsx producers orders")

    def open_and_send_offer(self, request, queryset):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return None
        permanence = queryset.order_by('?').first()
        if permanence is None or not (PERMANENCE_PLANNED <= permanence.status <= PERMANENCE_WAIT_FOR_OPEN):
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return None
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
                sender_email, sender_function, signature, cc_email_staff = get_signature(is_reply_to_order_email=True)
                with switch_language(permanence, language_code):
                    try:
                        offer_description = permanence.offer_description
                    except TranslationDoesNotExist:
                        offer_description = EMPTY_STRING
                context = TemplateContext({
                    'name'             : _('long_profile_name'),
                    'long_profile_name': _('long_profile_name'),
                    'permanence_link'  : mark_safe('<a href="#">%s</a>' % _("offer")),
                    'offer_description': mark_safe(offer_description),
                    'offer_link'       : mark_safe('<a href="#">%s</a>' % _("offer")),
                    'signature'        : mark_safe(
                        '%s<br/>%s<br/>%s' % (signature, sender_function, repanier.apps.REPANIER_SETTINGS_GROUP_NAME)),
                })
                template_offer_mail.append(language_code)
                template_offer_mail.append(template.render(context))
            translation.activate(cur_language)
            email_will_be_sent, email_will_be_sent_to = send_email_to_who(True)
        else:
            template_offer_mail = []
            template_cancel_order_mail = []
            cur_language = translation.get_language()
            for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
                language_code = language["code"]
                translation.activate(language_code)

                with switch_language(repanier.apps.REPANIER_SETTINGS_CONFIG, language_code):
                    template = Template(repanier.apps.REPANIER_SETTINGS_CONFIG.offer_customer_mail)
                sender_email, sender_function, signature, cc_email_staff = get_signature(is_reply_to_order_email=True)
                with switch_language(permanence, language_code):
                    try:
                        offer_description = permanence.offer_description
                    except TranslationDoesNotExist:
                        offer_description = EMPTY_STRING

                offer_producer = ', '.join([p.short_profile_name for p in permanence.producers.all()])
                qs = Product.objects.filter(
                    producer=permanence.producers.first(),
                    is_into_offer=True,
                    order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT  # Don't display technical products.
                ).order_by(
                    "translations__long_name"
                )[:5]
                offer_detail = '<ul>%s</ul>' % ("".join('<li>%s, %s</li>' % (
                    p.get_long_name(box_unicode=EMPTY_STRING),
                    p.producer.short_profile_name
                )
                                                        for p in qs
                                                        ),)
                context = TemplateContext({
                    'offer_description': mark_safe(offer_description),
                    'offer_detail'     : offer_detail,
                    'offer_producer'   : offer_producer,
                    'permanence_link'  : mark_safe('<a href="#">%s</a>' % permanence),
                    'signature'        : mark_safe(
                        '%s<br/>%s<br/>%s' % (signature, sender_function, repanier.apps.REPANIER_SETTINGS_GROUP_NAME)),
                })
                template_offer_mail.append(language_code)
                template_offer_mail.append(template.render(context))
                if repanier.apps.REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
                    context = TemplateContext({
                        'name'             : _('long_basket_name'),
                        'long_basket_name' : _('long_basket_name'),
                        'basket_name'      : _('short_basket_name'),
                        'short_basket_name': _('short_basket_name'),
                        'permanence_link'  : mark_safe('<a href=#">%s</a>' % permanence),
                        'signature'        : mark_safe(
                            '%s<br/>%s<br/>%s' % (signature, sender_function, repanier.apps.REPANIER_SETTINGS_GROUP_NAME)),
                    })
                    template_cancel_order_mail.append(language_code)
                    template_cancel_order_mail.append(template.render(context))
            translation.activate(cur_language)
            email_will_be_sent, email_will_be_sent_to = send_email_to_who(
                repanier.apps.REPANIER_SETTINGS_SEND_OPENING_MAIL_TO_CUSTOMER
            )
        if 'apply' in request.POST:
            form = OpenAndSendOfferForm(request.POST)
            if form.is_valid():
                user_message, user_message_level = task_order.admin_open_and_send(
                    request, permanence
                )
                self.message_user(request, user_message, user_message_level)
            return HttpResponseRedirect(request.get_full_path())
        else:
            form = OpenAndSendOfferForm(
                initial={
                    'template_offer_customer_mail': mark_safe("<br/>==============<br/>".join(template_offer_mail)),
                    'template_cancel_order_customer_mail': mark_safe("<br/>==============<br/>".join(template_cancel_order_mail)),
                }
            )
        return render(
            request,
            'repanier/confirm_admin_open_and_send_offer.html', {
                'sub_title'            : _("Please, confirm the action : open and send offers"),
                'action_checkbox_name' : admin.ACTION_CHECKBOX_NAME,
                'action'               : 'open_and_send_offer',
                'permanence'           : permanence,
                'pre_open'             : pre_open,
                'form'                 : form,
                'email_will_be_sent'   : email_will_be_sent,
                'email_will_be_sent_to': email_will_be_sent_to
            })

    open_and_send_offer.short_description = _('open and send offers')

    def close_order(self, request, queryset):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return None
        permanence = queryset.order_by('?').first()
        if permanence is None or permanence.status != PERMANENCE_OPENED:
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return None
        if 'apply' in request.POST:
            deliveries_to_be_closed = []
            producers_to_be_closed = []
            producer_qs = Producer.objects.filter(permanence=permanence.id)
            if "deliveries" in request.POST:
                deliveries_to_be_closed = request.POST.getlist("deliveries")
                if len(deliveries_to_be_closed) == 0:
                    user_message = _("You must select at least one delivery point.")
                    user_message_level = messages.WARNING
                    self.message_user(request, user_message, user_message_level)
                    return None
            # whole_permanence = "all-deliveries" in request.POST and "all-producer-invoices" in request.POST
            all_producers = "all-producer-invoices" in request.POST
            # Do not send order twice
            producers_invoices_to_be_closed = []
            if "producer-invoices" in request.POST:
                producers_invoices_to_be_closed = request.POST.getlist("producer-invoices")
            if not all_producers and len(producers_invoices_to_be_closed) == 0:
                user_message = _("You must select at least one producer.")
                user_message_level = messages.WARNING
                self.message_user(request, user_message, user_message_level)
                return None
            producer_qs = producer_qs.filter(
                producerinvoice__in=producers_invoices_to_be_closed)
            for producer in producer_qs.only("id").order_by('?'):
                producers_to_be_closed.append(producer.id)
            user_message, user_message_level = task_order.admin_close(
                permanence_id=permanence.id,
                all_producers=all_producers,
                deliveries_id=deliveries_to_be_closed,
                producers_id=producers_to_be_closed
            )
            self.message_user(request, user_message, user_message_level)
            return None
        if repanier.apps.REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS or DeliveryBoard.objects.filter(
                permanence_id=permanence.id,
                status__gt=PERMANENCE_OPENED
        ).order_by('?').exists():
            # /!\ If one delivery point has been closed, I may not close anymore by producer
            producer_invoices = ProducerInvoice.objects.none()
        else:
            producer_invoices = ProducerInvoice.objects.filter(
                permanence=permanence.id,
                status=PERMANENCE_OPENED,
                producer__represent_this_buyinggroup=False
            ).order_by("producer")
        return render(
            request,
            'repanier/confirm_admin_close_order.html', {
                'sub_title'           : _("Please, confirm the action : close orders"),
                'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
                'action'              : 'close_order',
                'permanence'          : permanence,
                'deliveries'          : DeliveryBoard.objects.filter(
                    permanence_id=permanence.id,
                    status=PERMANENCE_OPENED
                ).order_by("id"),
                'producer_invoices'   : producer_invoices,
            })

    close_order.short_description = _('close orders')

    def send_order(self, request, queryset):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return None
        permanence = queryset.order_by('?').first()
        if permanence is None or permanence.status not in [PERMANENCE_OPENED, PERMANENCE_CLOSED]:
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return None
        if 'apply' in request.POST:
            deliveries_to_be_send = []
            producers_to_be_send = []
            producer_qs = Producer.objects.filter(permanence=permanence.id)
            if "deliveries" in request.POST:
                deliveries_to_be_send = request.POST.getlist("deliveries")
                if len(deliveries_to_be_send) == 0:
                    user_message = _("You must select at least one delivery point.")
                    user_message_level = messages.WARNING
                    self.message_user(request, user_message, user_message_level)
                    return None
            all_producers = "all-producer-invoices" in request.POST
            producers_invoices_to_be_send = []
            if "producer-invoices" in request.POST:
                producers_invoices_to_be_send = request.POST.getlist("producer-invoices")
            if not all_producers and len(producers_invoices_to_be_send) == 0:
                user_message = _("You must select at least one producer.")
                user_message_level = messages.WARNING
                self.message_user(request, user_message, user_message_level)
                return None
            producer_qs = producer_qs.filter(
                producerinvoice__in=producers_invoices_to_be_send)
            for producer in producer_qs.only("id").order_by('?'):
                producers_to_be_send.append(producer.id)

            user_message, user_message_level = task_order.admin_send(
                permanence_id=permanence.id,
                all_producers=all_producers,
                deliveries_id=deliveries_to_be_send,
                producers_id=producers_to_be_send
            )
            self.message_user(request, user_message, user_message_level)
            return None

        template_order_customer_mail = []
        template_order_producer_mail = []
        template_order_staff_mail = []
        cur_language = translation.get_language()
        for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
            language_code = language["code"]
            translation.activate(language_code)

            template = Template(repanier.apps.REPANIER_SETTINGS_CONFIG.order_customer_mail)
            sender_email, sender_function, signature, cc_email_staff = get_signature(is_reply_to_order_email=True)
            customer_last_balance = \
                _('The balance of your account as of %(date)s is %(balance)s.') % {
                    'date'   : timezone.now().strftime(settings.DJANGO_SETTINGS_DATE),
                    'balance': RepanierMoney(123.45)
                }
            customer_on_hold_movement = \
                _(
                    'This balance does not take account of any unrecognized payments %(bank)s and any unbilled order %(other_order)s.') \
                % {
                    'bank'       : RepanierMoney(123.45),
                    'other_order': RepanierMoney(123.45)
                }

            bank_account_number = repanier.apps.REPANIER_SETTINGS_BANK_ACCOUNT
            if bank_account_number is not None:
                group_name = repanier.apps.REPANIER_SETTINGS_GROUP_NAME
                if permanence.short_name:
                    communication = "%s (%s)" % (_('short_basket_name'), permanence.short_name)
                else:
                    communication = _('short_basket_name')
                customer_payment_needed = '<font color="#bd0926">%s</font>' % (
                    _(
                        'Please pay %(payment)s to the bank account %(name)s %(number)s with communication %(communication)s.') % {
                        'payment'      : RepanierMoney(123.45),
                        'name'         : group_name,
                        'number'       : bank_account_number,
                        'communication': communication
                    }
                )
            else:
                customer_payment_needed = EMPTY_STRING
            context = TemplateContext({
                'name'             : _('long_basket_name'),
                'long_basket_name' : _('long_basket_name'),
                'basket_name'      : _('short_basket_name'),
                'short_basket_name': _('short_basket_name'),
                'permanence_link'  : mark_safe('<a href=#">%s</a>' % permanence),
                'last_balance'     : mark_safe('<a href="#">%s</a>' % customer_last_balance),
                'order_amount'     : RepanierMoney(123.45),
                'on_hold_movement' : mark_safe(customer_on_hold_movement),
                'payment_needed'   : mark_safe(customer_payment_needed),
                'delivery_point'   : _('delivery point').upper(),
                'signature'        : mark_safe(
                    '%s<br/>%s<br/>%s' % (signature, sender_function, repanier.apps.REPANIER_SETTINGS_GROUP_NAME)),
            })

            template_order_customer_mail.append(language_code)
            template_order_customer_mail.append(template.render(context))

            template = Template(repanier.apps.REPANIER_SETTINGS_CONFIG.order_producer_mail)
            context = TemplateContext({
                'name'             : _('long_profile_name'),
                'long_profile_name': _('long_profile_name'),
                'order_empty'      : False,
                'duplicate'        : True,
                'permanence_link'  : mark_safe('<a href=#">%s</a>' % permanence),
                'signature'        : mark_safe(
                    '%s<br/>%s<br/>%s' % (signature, sender_function, repanier.apps.REPANIER_SETTINGS_GROUP_NAME)),
            })

            template_order_producer_mail.append(language_code)
            template_order_producer_mail.append(template.render(context))

            board_composition, board_composition_and_description = get_board_composition(permanence.id)
            template = Template(repanier.apps.REPANIER_SETTINGS_CONFIG.order_staff_mail)
            context = TemplateContext({
                'permanence_link'                  : mark_safe('<a href=#">%s</a>' % permanence),
                'board_composition'                : mark_safe(board_composition),
                'board_composition_and_description': mark_safe(board_composition_and_description),
                'signature'                        : mark_safe(
                    '%s<br/>%s<br/>%s' % (signature, sender_function, repanier.apps.REPANIER_SETTINGS_GROUP_NAME)),
            })

            template_order_staff_mail.append(language_code)
            template_order_staff_mail.append(template.render(context))



        translation.activate(cur_language)

        order_customer_email_will_be_sent, order_customer_email_will_be_sent_to = send_email_to_who(
            repanier.apps.REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_CUSTOMER
        )
        order_producer_email_will_be_sent, order_producer_email_will_be_sent_to = send_email_to_who(
            repanier.apps.REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_PRODUCER
        )
        order_board_email_will_be_sent, order_board_email_will_be_sent_to = send_email_to_who(
            repanier.apps.REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_BOARD, board=True
        )

        form = CloseAndSendOrderForm(
            initial={
                'template_order_customer_mail': mark_safe("<br/>==============<br/>".join(template_order_customer_mail)),
                'template_order_producer_mail': mark_safe("<br/>==============<br/>".join(template_order_producer_mail)),
                'template_order_staff_mail'   : mark_safe("<br/>==============<br/>".join(template_order_staff_mail)),
            }
        )
        if repanier.apps.REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS or DeliveryBoard.objects.filter(
                permanence_id=permanence.id,
                status__gt=PERMANENCE_OPENED
        ).order_by('?').exists():
            # /!\ If one delivery point has been closed, I may not close anymore by producer:
            producer_invoices = ProducerInvoice.objects.none()
        else:
            producer_invoices = ProducerInvoice.objects.filter(
                Q(
                    permanence=permanence.id,
                    status=PERMANENCE_OPENED,
                    producer__represent_this_buyinggroup=False
                ) | Q(
                    permanence=permanence.id,
                    status=PERMANENCE_CLOSED,
                    producer__represent_this_buyinggroup=False
                )
            ).order_by("producer")
        return render(
            request,
            'repanier/confirm_admin_send_order.html', {
                'sub_title'                           : _("Please, confirm the action : send orders"),
                'action_checkbox_name'                : admin.ACTION_CHECKBOX_NAME,
                'action'                              : 'send_order',
                'permanence'                          : permanence,
                'deliveries'                          : DeliveryBoard.objects.filter(
                    permanence_id=permanence.id,
                    status__in=[PERMANENCE_OPENED, PERMANENCE_CLOSED]
                ).order_by("id"),
                'producer_invoices'                   : producer_invoices,
                'form'                                : form,
                'order_customer_email_will_be_sent'   : order_customer_email_will_be_sent,
                'order_customer_email_will_be_sent_to': order_customer_email_will_be_sent_to,
                'order_producer_email_will_be_sent'   : order_producer_email_will_be_sent,
                'order_producer_email_will_be_sent_to': order_producer_email_will_be_sent_to,
                'order_board_email_will_be_sent'      : order_board_email_will_be_sent,
                'order_board_email_will_be_sent_to'   : order_board_email_will_be_sent_to
            })

    send_order.short_description = _('send orders2')

    def back_to_planned(self, request, queryset):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return None
        permanence = queryset.order_by('?').first()
        if Purchase.objects.filter(
                permanence_id=permanence.id
        ).exclude(
            status__in=[PERMANENCE_PRE_OPEN, PERMANENCE_OPENED]
        ).order_by('?').exists():
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return None
        if 'apply' in request.POST:
            user_message, user_message_level = task_order.admin_back_to_planned(request, permanence)
            self.message_user(request, user_message, user_message_level)
            return None
        return render(request, 'repanier/confirm_admin_action.html', {
            'sub_title'           : _("Please, confirm the action : back to planned"),
            'action'              : 'back_to_planned',
            'permanence'          : permanence,
            'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
        })

    back_to_planned.short_description = _('back to planned')

    def undo_back_to_planned(self, request, queryset):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return None
        permanence = queryset.order_by('?').first()
        if permanence is None or not (PERMANENCE_PLANNED == permanence.status):
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return None
        if 'apply' in request.POST:
            user_message, user_message_level = task_order.admin_undo_back_to_planned(request, permanence)
            self.message_user(request, user_message, user_message_level)
            return None
        return render(request, 'repanier/confirm_admin_action.html', {
            'sub_title'           : _("Please, confirm the action : undo back to planned"),
            'action'              : 'undo_back_to_planned',
            'permanence'          : permanence,
            'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
        })

    undo_back_to_planned.short_description = _('undo back to planned')

    def delete_purchases(self, request, queryset):
        if not request.user.is_superuser:
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return None
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.WARNING
            self.message_user(request, user_message, user_message_level)
            return None
        permanence = queryset.order_by('?').first()
        if permanence is None or not (PERMANENCE_SEND == permanence.status):
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return None
        if 'apply' in request.POST:
            user_message, user_message_level = task_purchase.admin_delete(permanence_id=permanence.id)
            self.message_user(request, user_message, user_message_level)
            return None
        return render(request, 'repanier/confirm_admin_action.html', {
            'sub_title'           : _(
                "Please, confirm the action : delete purchases. Be carefull : !!! THERE IS NO WAY TO RESTORE THEM AUTOMATICALY !!!!"),
            'action'              : 'delete_purchases',
            'permanence'          : permanence,
            'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
        })

    delete_purchases.short_description = _('DEV - Delete purchases')

    def generate_permanence(self, request, queryset):
        if 'cancel' in request.POST:
            user_message = _("Action canceled by the user.")
            user_message_level = messages.INFO
            self.message_user(request, user_message, user_message_level)
            return None
        permanence = queryset.order_by('?').first()
        if permanence is None or permanence.status not in [
            PERMANENCE_PLANNED, PERMANENCE_PRE_OPEN, PERMANENCE_OPENED, PERMANENCE_CLOSED, PERMANENCE_SEND
        ]:
            user_message = _("Action canceled by the system.")
            user_message_level = messages.ERROR
            self.message_user(request, user_message, user_message_level)
            return None
        if 'apply' in request.POST:
            form = GeneratePermanenceForm(request.POST)
            if form.is_valid():
                repeat_counter = form.cleaned_data['repeat_counter']
                repeat_step = form.cleaned_data['repeat_step']
                if 1 <= repeat_counter * repeat_step <= 54:
                    creation_counter = self.perform_generate_permanence(permanence, repeat_counter=int(repeat_counter),
                                                                        repeat_step=int(repeat_step))
                    if creation_counter == 0:
                        user_message = _("Nothing to do.")
                    elif creation_counter == 1:
                        user_message = _("%d permanence generated.") % creation_counter
                    else:
                        user_message = _("%d permanences generated.") % creation_counter
                    user_message_level = messages.INFO
                else:
                    user_message = _("Action canceled by the system.")
                    user_message_level = messages.ERROR
                self.message_user(request, user_message, user_message_level)
            return HttpResponseRedirect(request.get_full_path())
        else:
            form = GeneratePermanenceForm(
                initial={
                    'repeat_counter': DECIMAL_ZERO,
                    'repeat_step'   : DECIMAL_ZERO
                }
            )
        return render(request, 'repanier/confirm_admin_generate_permanence.html', {
            'sub_title'           : _("How many weekly permanence(s) do you want to generate from this ?"),
            'action'              : 'generate_permanence',
            'permanence'          : permanence,
            'form'                : form,
            'action_checkbox_name': admin.ACTION_CHECKBOX_NAME,
        })

    generate_permanence.short_description = _("Generate permanence")

    def perform_generate_permanence(self, permanence, repeat_counter=0, repeat_step=1):
        creation_counter = 0
        if 1 <= repeat_counter * repeat_step <= 54:
            # 54 weeks in a year
            repeat_counter += 1
            starting_date = permanence.permanence_date
            try:
                short_name = permanence.short_name
            except TranslationDoesNotExist:
                short_name = EMPTY_STRING
            cur_language = translation.get_language()
            every_x_days = 7 * int(repeat_step)
            for i in range(1, repeat_counter):
                new_date = starting_date + datetime.timedelta(days=every_x_days * i)
                # Mandatory because of Parler
                if short_name != EMPTY_STRING:
                    already_exists = PermanenceInPreparation.objects.filter(
                        permanence_date=new_date,
                        translations__language_code=cur_language,
                        translations__short_name=short_name
                    ).exists()
                else:
                    already_exists = False
                    for existing_permanence in PermanenceInPreparation.objects.filter(
                            permanence_date=new_date
                    ):
                        try:
                            short_name = existing_permanence.short_name
                            already_exists = short_name == EMPTY_STRING
                        except TranslationDoesNotExist:
                            already_exists = True
                        if already_exists:
                            break
                if not already_exists:
                    creation_counter += 1
                    new_permanence = PermanenceInPreparation.objects.create(
                        permanence_date=new_date
                    )
                    for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
                        language_code = language["code"]
                        translation.activate(language_code)
                        new_permanence.set_current_language(language_code)
                        permanence.set_current_language(language_code)
                        try:
                            new_permanence.short_name = permanence.short_name
                            new_permanence.save()
                        except TranslationDoesNotExist:
                            pass
                    translation.activate(cur_language)
                    for permanence_board in PermanenceBoard.objects.filter(
                            permanence=permanence
                    ):
                        PermanenceBoard.objects.create(
                            permanence=new_permanence,
                            permanence_role=permanence_board.permanence_role
                        )
                    for delivery_board in DeliveryBoard.objects.filter(
                            permanence=permanence
                    ):
                        new_delivery_board = DeliveryBoard.objects.create(
                            permanence=new_permanence,
                            delivery_point=delivery_board.delivery_point,
                            delivery_date=delivery_board.delivery_date + datetime.timedelta(days=every_x_days * i)
                        )
                        for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
                            language_code = language["code"]
                            translation.activate(language_code)
                            new_delivery_board.set_current_language(language_code)
                            delivery_board.set_current_language(language_code)
                            try:
                                new_delivery_board.delivery_comment = delivery_board.delivery_comment
                                new_delivery_board.save()
                            except TranslationDoesNotExist:
                                pass
                        translation.activate(cur_language)
                    for producer in permanence.producers.all():
                        new_permanence.producers.add(producer)
        return creation_counter

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "producers":
            kwargs["queryset"] = Producer.objects.filter(is_active=True)
        return super(PermanenceInPreparationAdmin, self).formfield_for_manytomany(
            db_field, request, **kwargs)

    def get_queryset(self, request):
        qs = super(PermanenceInPreparationAdmin, self).get_queryset(request)
        return qs.filter(status__lte=PERMANENCE_SEND)

    def save_model(self, request, permanence, form, change):
        if change and ('permanence_date' in form.changed_data):
            PermanenceBoard.objects.filter(permanence_id=permanence.id).update(
                permanence_date=permanence.permanence_date)
            Purchase.objects.filter(permanence_id=permanence.id).update(
                permanence_date=permanence.permanence_date)
        super(PermanenceInPreparationAdmin, self).save_model(
            request, permanence, form, change)

    def get_actions(self, request):
        actions = super(PermanenceInPreparationAdmin, self).get_actions(request)
        actions['send_order'] = list(actions['send_order'])
        if not repanier.apps.REPANIER_SETTINGS_CLOSE_WO_SENDING:
            del actions['close_order']
            actions['send_order'][2] = _('send orders2')
        else:
            actions['send_order'][2] = _('send orders1')
        return actions
