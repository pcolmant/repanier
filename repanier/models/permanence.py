# -*- coding: utf-8
from __future__ import unicode_literals

import datetime

from django.conf import settings
from django.core import urlresolvers
from django.core.cache import cache
from django.db import models
from django.db.models import F, Sum
from django.utils import timezone, translation
from django.utils.encoding import python_2_unicode_compatible
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from menus.menu_pool import menu_pool
from parler.models import TranslatableModel, TranslatedFields, TranslationDoesNotExist

import customer
import deliveryboard
import invoice
import offeritem
import permanenceboard
import producer
import purchase
import repanier.apps
from repanier.picture.const import SIZE_L
from repanier.picture.fields import AjaxPictureField
from repanier.fields.RepanierMoneyField import ModelMoneyField
from repanier.const import *
from repanier.tools import cap


# def verbose_name():
#     if repanier.apps.DJANGO_IS_MIGRATION_RUNNING:
#         return EMPTY_STRING
#     return lambda: "%s" % repanier.apps.REPANIER_SETTINGS_PERMANENCE_NAME
#
#
# def verbose_name_plural():
#     if repanier.apps.DJANGO_IS_MIGRATION_RUNNING:
#         return EMPTY_STRING
#     return lambda: "%s" % repanier.apps.REPANIER_SETTINGS_PERMANENCES_NAME
#
#
# def verbose_name_in_preparation():
#     if repanier.apps.DJANGO_IS_MIGRATION_RUNNING:
#         return EMPTY_STRING
#     return lambda: _("%(name)s in preparation list") % {'name': repanier.apps.REPANIER_SETTINGS_PERMANENCES_NAME}
#
#
# def verbose_name_plural_in_preparation():
#     if repanier.apps.DJANGO_IS_MIGRATION_RUNNING:
#         return EMPTY_STRING
#     return lambda: _("%(name)s in preparation list") % {'name': repanier.apps.REPANIER_SETTINGS_PERMANENCES_NAME}
#
#
# def verbose_name_done():
#     if repanier.apps.DJANGO_IS_MIGRATION_RUNNING:
#         return EMPTY_STRING
#     return lambda: _("%(name)s done list") % {
#         'name': repanier.apps.REPANIER_SETTINGS_PERMANENCES_NAME} if repanier.apps.REPANIER_SETTINGS_INVOICE else "%s" % _(
#         "%(name)s archived list") % {'name': repanier.apps.REPANIER_SETTINGS_PERMANENCES_NAME}
#
#
# def verbose_name_plural_done():
#     if repanier.apps.DJANGO_IS_MIGRATION_RUNNING:
#         return EMPTY_STRING
#     return lambda: _("%(name)s done list") % {
#         'name': repanier.apps.REPANIER_SETTINGS_PERMANENCES_NAME} if repanier.apps.REPANIER_SETTINGS_INVOICE else "%s" % _(
#         "%(name)s archived list") % {'name': repanier.apps.REPANIER_SETTINGS_PERMANENCES_NAME}


@python_2_unicode_compatible
class Permanence(TranslatableModel):
    translations = TranslatedFields(
        short_name=models.CharField(_("offer name"), max_length=50, blank=True),
        offer_description=HTMLField(_("offer_description"),
                                    configuration='CKEDITOR_SETTINGS_MODEL2',
                                    help_text=_(
                                        "This message is send by mail to all customers when opening the order or on top "),
                                    blank=True, default=EMPTY_STRING),
        invoice_description=HTMLField(
            _("invoice_description"),
            configuration='CKEDITOR_SETTINGS_MODEL2',
            help_text=_(
                'This message is send by mail to all customers having bought something when closing the permanence.'),
            blank=True, default=EMPTY_STRING),
    )

    status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
        verbose_name=_("permanence_status"),
        help_text=_('status of the permanence from planned, orders opened, orders closed, send, done'))
    permanence_date = models.DateField(_("date"), db_index=True)
    payment_date = models.DateField(_("payment_date"), blank=True, null=True, db_index=True)
    producers = models.ManyToManyField(
        'Producer',
        verbose_name=_("producers"),
        blank=True
    )
    # Calculated with Purchase
    total_purchase_with_tax = ModelMoneyField(
        _("Total amount"),
        help_text=_('Total purchase amount vat included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    total_selling_with_tax = ModelMoneyField(
        _("Total amount"),
        help_text=_('Total purchase amount vat included'),
        default=DECIMAL_ZERO, max_digits=8, decimal_places=2)
    total_purchase_vat = ModelMoneyField(
        _("Total vat"),
        help_text=_('Vat part of the total purchased'),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    total_selling_vat = ModelMoneyField(
        _("Total vat"),
        help_text=_('Vat part of the total purchased'),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)

    with_delivery_point = models.BooleanField(
        _("with_delivery_point"), default=False)
    automatically_closed = models.BooleanField(
        _("automatically_closed"), default=False)
    is_updated_on = models.DateTimeField(
        _("is_updated_on"), auto_now=True)
    highest_status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
        verbose_name=_("highest permanence_status"),
        help_text=_('status of the permanence from planned, orders opened, orders closed, send, done'))
    master_permanence = models.ForeignKey(
        'Permanence', verbose_name=_("master permanence"),
        related_name='child_permanence',
        blank=True, null=True, default=None,
        on_delete=models.PROTECT, db_index=True)
    invoice_sort_order = models.IntegerField(
        _("invoice sort order"),
        default=None, blank=True, null=True)
    offer_description_on_home_page = models.BooleanField(
        _("Publish the offer description on the home page when the permanence is open"), default=True)
    picture = AjaxPictureField(
        verbose_name=_("picture"),
        null=True, blank=True,
        upload_to="permanence", size=SIZE_L)
    gauge = models.IntegerField(
        default=0, editable=False
    )

    def get_producers(self):
        if self.status == PERMANENCE_PLANNED:
            if len(self.producers.all()) > 0:
                changelist_url = urlresolvers.reverse(
                    'admin:repanier_product_changelist',
                )
                link = []
                for p in self.producers.all():
                    link.append(
                        '<a href="%s?producer=%d">&nbsp;%s</a>' % (
                            changelist_url, p.id, p.short_profile_name))
                return '<div class="wrap-text">%s</div>' % ", ".join(link)
            else:
                return '<div class="wrap-text">%s</div>' % _("No offer")
        elif self.status == PERMANENCE_PRE_OPEN:
            return '<div class="wrap-text">%s</div>' % ", ".join([p.short_profile_name + " (" + p.phone1 + ")" for p in self.producers.all()])
        elif self.status in [PERMANENCE_OPENED, PERMANENCE_CLOSED]:
            close_offeritem_changelist_url = urlresolvers.reverse(
                'admin:repanier_offeritemclosed_changelist',
            )

            link = []
            for p in self.producers.all().only("id"):
                pi = invoice.ProducerInvoice.objects.filter(
                    producer_id=p.id, permanence_id=self.id
                ).order_by('?').first()
                if pi is not None:
                    if pi.status == PERMANENCE_OPENED:
                        label = ('%s (%s) ' % (p.short_profile_name, pi.get_total_price_with_tax())).replace(
                            ' ', '&nbsp;')
                        offeritem_changelist_url = close_offeritem_changelist_url
                    else:
                        label = ('%s (%s) %s' % (
                        p.short_profile_name, pi.get_total_price_with_tax(), LOCK_UNICODE)).replace(' ',
                                                                                                    '&nbsp;')
                        offeritem_changelist_url = close_offeritem_changelist_url
                else:
                    label = ('%s ' % (p.short_profile_name,)).replace(' ', '&nbsp;')
                    offeritem_changelist_url = close_offeritem_changelist_url
                link.append(
                    '<a href="%s?permanence=%s&producer=%d">%s</a>' % (
                        offeritem_changelist_url, self.id, p.id, label))
            return '<div class="wrap-text">%s</div>' % ", ".join(link)

        elif self.status in [PERMANENCE_SEND, PERMANENCE_INVOICED, PERMANENCE_ARCHIVED]:
            send_offeritem_changelist_url = urlresolvers.reverse(
                'admin:repanier_offeritemsend_changelist',
            )
            send_customer_changelist_url = urlresolvers.reverse(
                'admin:repanier_customersend_changelist',
            )
            link = []
            at_least_one_permanence_send = False
            for pi in invoice.ProducerInvoice.objects.filter(permanence_id=self.id).select_related(
                    "producer").order_by('producer'):
                if pi.status == PERMANENCE_SEND:
                    at_least_one_permanence_send = True
                    if pi.producer.invoice_by_basket:
                        changelist_url = send_customer_changelist_url
                    else:
                        changelist_url = send_offeritem_changelist_url
                    # Important : no target="_blank"
                    label = '%s (%s) %s' % (
                    pi.producer.short_profile_name, pi.get_total_price_with_tax(), LOCK_UNICODE)
                    link.append(
                        '<a href="%s?permanence=%d&producer=%d">&nbsp;%s</a>' % (
                            changelist_url, self.id, pi.producer_id, label.replace(' ', '&nbsp;')
                        ))
                else:
                    if pi.invoice_reference:
                        if pi.to_be_invoiced_balance != DECIMAL_ZERO or pi.total_price_with_tax != DECIMAL_ZERO:
                            label = "%s (%s - %s)" % (
                                pi.producer.short_profile_name,
                                pi.to_be_invoiced_balance,
                                cap(pi.invoice_reference, 15)
                            )
                        else:
                            label = "%s (%s)" % (
                                pi.producer.short_profile_name,
                                cap(pi.invoice_reference, 15)
                            )
                    else:
                        if pi.to_be_invoiced_balance != DECIMAL_ZERO or pi.total_price_with_tax != DECIMAL_ZERO:
                            label = "%s (%s)" % (
                                pi.producer.short_profile_name,
                                pi.to_be_invoiced_balance
                            )
                        else:
                            # label = "%s" % (
                            #     pi.producer.short_profile_name
                            # )
                            continue
                    # Important : target="_blank" because the invoices must be displayed without the cms_toolbar
                    # Such that they can be accessed by the producer and by the staff
                    link.append(
                        '<a href="%s?producer=%d" target="_blank">%s</a>'
                        % (
                            urlresolvers.reverse('producer_invoice_view', args=(pi.id,)),
                            pi.producer_id,
                            label.replace(' ', '&nbsp;')))

            producers = ", ".join(link)
            if at_least_one_permanence_send:
                msg_html = '<div class="wrap-text">%s</div>' % producers
            else:
                msg_html = """
                    <div class="wrap-text"><button
                    onclick="django.jQuery('#id_get_producers_%d').toggle();
                        if(django.jQuery(this).html()=='%s'){
                            django.jQuery(this).html('%s')
                        }else{
                            django.jQuery(this).html('%s')
                        };
                        return false;"
                    >%s</button>
                    <div id="id_get_producers_%d" style="display:none;">%s</div></div>
                """ % (
                    self.id, _("Show"), _("Hide"), _("Show"), _("Show"), self.id, producers
                )
            return msg_html
        else:
            return '<div class="wrap-text">%s</div>' % ", ".join([p.short_profile_name
                                   for p in
                                   producer.Producer.objects.filter(
                                       producerinvoice__permanence_id=self.id).only(
                                       'short_profile_name')])

    get_producers.short_description = (_("producers in this permanence"))
    get_producers.allow_tags = True

    def get_customers(self):
        if self.status in [
            PERMANENCE_OPENED, PERMANENCE_CLOSED, PERMANENCE_SEND
        ]:
            changelist_url = urlresolvers.reverse(
                'admin:repanier_purchase_changelist',
            )
            link = []
            delivery_save = None
            for ci in invoice.CustomerInvoice.objects.filter(permanence_id=self.id).select_related(
                "customer").order_by('delivery', 'customer'):
                if delivery_save != ci.delivery:
                    delivery_save = ci.delivery
                    if ci.delivery is not None:
                        link.append("<br/><b>%s</b>" % ci.delivery.get_delivery_display())
                    else:
                        link.append("<br/><br/>--")
                total_price_with_tax = ci.get_total_price_with_tax(customer_charged=True)
                # if ci.is_order_confirm_send:
                label = '%s%s (%s) %s%s' % (
                    "<b><i>" if ci.is_group else EMPTY_STRING,
                    ci.customer.short_basket_name,
                    "-" if ci.is_group or total_price_with_tax == DECIMAL_ZERO else total_price_with_tax,
                    ci.get_is_order_confirm_send_display(),
                    "</i></b>" if ci.is_group else EMPTY_STRING,
                )
                # else:
                #     label = '%s%s (%s) %s%s' % (
                #         "<b><i>" if ci.is_group else EMPTY_STRING,
                #         ci.customer.short_basket_name,
                #         "-" if ci.is_group or total_price_with_tax == DECIMAL_ZERO else total_price_with_tax,
                #         ci.get_is_order_confirm_send_display(),
                #         "</i></b>" if ci.is_group else EMPTY_STRING,
                #     )
                # Important : no target="_blank"
                link.append(
                    '<a href="%s?permanence=%d&customer=%d">%s</a>'
                    % (changelist_url, self.id, ci.customer_id, label.replace(' ', '&nbsp;')))
            customers = ", ".join(link)
        elif self.status in [PERMANENCE_INVOICED, PERMANENCE_ARCHIVED]:
            link = []
            delivery_save = None
            for ci in invoice.CustomerInvoice.objects.filter(permanence_id=self.id).select_related(
                "customer").order_by('delivery', 'customer'):
                if delivery_save != ci.delivery:
                    delivery_save = ci.delivery
                    if ci.delivery is not None:
                        link.append("<br/><b>%s</b>" % ci.delivery.get_delivery_display())
                    else:
                        link.append("<br/><br/>--")
                total_price_with_tax = ci.get_total_price_with_tax(customer_charged=True)
                label = "%s%s (%s) %s%s" % (
                    "<b><i>" if ci.is_group else EMPTY_STRING,
                    ci.customer.short_basket_name,
                    "-" if total_price_with_tax == DECIMAL_ZERO else total_price_with_tax,
                    ci.get_is_order_confirm_send_display(),
                    "</i></b>" if ci.is_group else EMPTY_STRING,
                )
                # Important : target="_blank" because the invoices must be displayed without the cms_toolbar
                # Such that they can be accessed by the customer and by the staff
                link.append(
                    '<a href="%s?customer=%d" target="_blank">%s</a>'
                    % (
                        urlresolvers.reverse('customer_invoice_view', args=(ci.id,)),
                        ci.customer_id,
                        label.replace(' ', '&nbsp;')
                    )
                )
            customers = ", ".join(link)
        else:
            customers = ", ".join([c.short_basket_name
                                   for c in
                                   customer.Customer.objects.filter(customerinvoice__permanence_id=self.id).only(
                                       'short_basket_name')])
        if len(customers) > 0:
            msg_html = """
                <div class="wrap-text"><button
                onclick="django.jQuery('#id_get_customers_%d').toggle();
                    if(django.jQuery(this).html()=='%s'){
                        django.jQuery(this).html('%s')
                    }else{
                        django.jQuery(this).html('%s')
                    };
                    return false;"
                >%s</button>
                <div id="id_get_customers_%d" style="display:none;">%s</div></div>
            """ % (
                self.id, _("Show"), _("Hide"), _("Show"), _("Show"), self.id, customers
            )
            return msg_html
        else:
            return '<div class="wrap-text">%s</div>' % _("No purchase")

    get_customers.short_description = (_("customers in this permanence"))
    get_customers.allow_tags = True

    def get_board(self):
        permanenceboard_set = permanenceboard.PermanenceBoard.objects.filter(
            permanence=self, permanence_role__rght=F('permanence_role__lft') + 1
        ).order_by("permanence_role__tree_id", "permanence_role__lft")
        first_board = True
        board = EMPTY_STRING
        if permanenceboard_set:
            for permanenceboard_row in permanenceboard_set:
                r_link = EMPTY_STRING
                r = permanenceboard_row.permanence_role
                if r:
                    r_url = urlresolvers.reverse(
                        'admin:repanier_lut_permanencerole_change',
                        args=(r.id,)
                    )
                    r_link = '<a href="' + r_url + \
                             '" target="_blank">' + r.short_name.replace(' ', '&nbsp;') + '</a>'
                c_link = EMPTY_STRING
                c = permanenceboard_row.customer
                if c:
                    c_url = urlresolvers.reverse(
                        'admin:repanier_customer_change',
                        args=(c.id,)
                    )
                    c_link = '&nbsp;->&nbsp;<a href="' + c_url + \
                             '" target="_blank">' + c.short_basket_name.replace(' ', '&nbsp;') + '</a>'
                if not first_board:
                    board += '<br/>'
                board += r_link + c_link
                first_board = False
        if not first_board:
            # At least one role is defined in the permanence board
            msg_html = """
                <div class="wrap-text"><button
                onclick="django.jQuery('#id_get_board_%d').toggle();
                    if(django.jQuery(this).html()=='%s'){
                        django.jQuery(this).html('%s')
                    }else{
                        django.jQuery(this).html('%s')
                    };
                    return false;"
                >%s</button>
                <div id="id_get_board_%d" style="display:none;">%s</div></div>
            """ % (
                self.id, _("Show"), _("Hide"), _("Show"), _("Show"), self.id, board
            )
            return msg_html
        else:
            return '<div class="wrap-text">%s</div>' % _("Empty board")

    get_board.short_description = (_("permanence board"))
    get_board.allow_tags = True

    def set_status(self, new_status, all_producers=True, producers_id=None, update_payment_date=False,
                   payment_date=None, allow_downgrade=True):
        if all_producers:
            now = timezone.now().date()
            self.is_updated_on = now
            self.status = new_status
            if self.highest_status < new_status:
                self.highest_status = new_status
            if update_payment_date:
                if payment_date is None:
                    self.payment_date = now
                else:
                    self.payment_date = payment_date
                self.save(
                    update_fields=['status', 'is_updated_on', 'highest_status', 'payment_date'])
            else:
                self.save(update_fields=['status', 'is_updated_on', 'highest_status'])
            if new_status == PERMANENCE_WAIT_FOR_OPEN:
                for a_producer in self.producers.all():
                    # Create ProducerInvoice to be able to close those producer on demand
                    if not invoice.ProducerInvoice.objects.filter(
                            permanence_id=self.id,
                            producer_id=a_producer.id
                    ).order_by('?').exists():
                        invoice.ProducerInvoice.objects.create(
                            permanence_id=self.id,
                            producer_id=a_producer.id
                        )

            self.with_delivery_point = deliveryboard.DeliveryBoard.objects.filter(
                permanence_id=self.id
            ).order_by('?').exists()
            if self.with_delivery_point:
                qs = deliveryboard.DeliveryBoard.objects.filter(
                    permanence_id=self.id
                ).exclude(status=new_status).order_by('?')
                for delivery_point in qs:
                    if allow_downgrade or delivery_point.status < new_status:
                        # --> or delivery_point.status < new_status -->
                        # Set new status except if PERMANENCE_SEND, PERMANENCE_WAIT_FOR_SEND
                        #  -> PERMANENCE_CLOSED, PERMANENCE_WAIT_FOR_CLOSED
                        # This occur if directly sending order of a opened delivery point
                        delivery_point.set_status(new_status)
            invoice.CustomerInvoice.objects.filter(
                permanence_id=self.id,
                delivery__isnull=True
            ).order_by('?').update(
                status=new_status
            )
            purchase.Purchase.objects.filter(
                permanence_id=self.id,
                customer_invoice__delivery__isnull=True
            ).order_by('?').update(
                status=new_status)
            invoice.ProducerInvoice.objects.filter(
                permanence_id=self.id
            ).order_by('?').update(
                status=new_status
            )
            if update_payment_date:
                if payment_date is None:
                    self.payment_date = now
                else:
                    self.payment_date = payment_date
                self.save(
                    update_fields=['status', 'is_updated_on', 'highest_status', 'with_delivery_point', 'payment_date'])
            else:
                self.save(update_fields=['status', 'is_updated_on', 'highest_status', 'with_delivery_point'])
            menu_pool.clear()
            cache.clear()
        else:
            # /!\ If one delivery point has been closed, I may not close anymore by producer
            purchase.Purchase.objects.filter(permanence_id=self.id, producer__in=producers_id).order_by('?').update(
                status=new_status)
            invoice.ProducerInvoice.objects.filter(permanence_id=self.id, producer__in=producers_id).order_by(
                '?').update(status=new_status)

    def duplicate(self, repeat_counter=0, repeat_step=1):
        creation_counter = 0
        if 1 <= repeat_counter * repeat_step <= 54:
            # 54 weeks in a year
            repeat_counter += 1
            starting_date = self.permanence_date
            short_name = self.safe_translation_getter(
                'short_name', any_language=True, default=EMPTY_STRING
            )
            cur_language = translation.get_language()
            every_x_days = 7 * int(repeat_step)
            for i in range(1, repeat_counter):
                new_date = starting_date + datetime.timedelta(days=every_x_days * i)
                # Mandatory because of Parler
                if short_name != EMPTY_STRING:
                    already_exists = Permanence.objects.filter(
                        permanence_date=new_date,
                        translations__language_code=cur_language,
                        translations__short_name=short_name
                    ).exists()
                else:
                    already_exists = False
                    for existing_permanence in Permanence.objects.filter(
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
                    new_permanence = Permanence.objects.create(
                        permanence_date=new_date
                    )
                    self.duplicate_short_name(
                        new_permanence,
                        cur_language=translation.get_language(),
                    )
                    for permanence_board in permanenceboard.PermanenceBoard.objects.filter(
                            permanence=self
                    ):
                        permanenceboard.PermanenceBoard.objects.create(
                            permanence=new_permanence,
                            permanence_role=permanence_board.permanence_role
                        )
                    for delivery_board in deliveryboard.DeliveryBoard.objects.filter(
                            permanence=self
                    ):
                        new_delivery_board = deliveryboard.DeliveryBoard.objects.create(
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
                    for a_producer in self.producers.all():
                        new_permanence.producers.add(a_producer)
        return creation_counter

    def duplicate_short_name(self, new_permanence, cur_language):
        for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
            language_code = language["code"]
            translation.activate(language_code)
            new_permanence.set_current_language(language_code)
            self.set_current_language(language_code)
            try:
                new_permanence.short_name = self.short_name
                new_permanence.save()
            except TranslationDoesNotExist:
                pass
        translation.activate(cur_language)
        return new_permanence

    def create_child(self, status):
        child_permanence = Permanence.objects.create(
            permanence_date=self.permanence_date,
            master_permanence_id=self.id,
            status=status
        )
        return self.duplicate_short_name(
            child_permanence,
            cur_language=translation.get_language(),
        )

    def recalculate_order_amount(self,
                                 offer_item_qs=None,
                                 re_init=False,
                                 send_to_producer=False):
        getcontext().rounding = ROUND_HALF_UP

        if send_to_producer or re_init:
            assert offer_item_qs is None, 'offer_item_qs must be set to None when send_to_producer or re_init'
            invoice.ProducerInvoice.objects.filter(
                permanence_id=self.id
            ).update(
                total_price_with_tax=DECIMAL_ZERO,
                total_vat=DECIMAL_ZERO,
                total_deposit=DECIMAL_ZERO,
            )
            invoice.CustomerInvoice.objects.filter(
                permanence_id=self.id
            ).update(
                total_price_with_tax=DECIMAL_ZERO,
                total_vat=DECIMAL_ZERO,
                total_deposit=DECIMAL_ZERO
            )
            invoice.CustomerProducerInvoice.objects.filter(
                permanence_id=self.id
            ).update(
                total_purchase_with_tax=DECIMAL_ZERO,
                total_selling_with_tax=DECIMAL_ZERO
            )
            offeritem.OfferItem.objects.filter(
                permanence_id=self.id
            ).update(
                quantity_invoiced=DECIMAL_ZERO,
                total_purchase_with_tax=DECIMAL_ZERO,
                total_selling_with_tax=DECIMAL_ZERO
            )
            self.total_purchase_with_tax=DECIMAL_ZERO
            self.total_selling_with_tax=DECIMAL_ZERO
            self.total_purchase_vat=DECIMAL_ZERO
            self.total_selling_vat=DECIMAL_ZERO
            for offer_item in offeritem.OfferItem.objects.filter(
                    permanence_id=self.id,
                    is_active=True,
                    manage_replenishment=True
            ).exclude(add_2_stock=DECIMAL_ZERO).order_by('?'):
                # Recalculate the total_price_with_tax of ProducerInvoice and
                # the total_purchase_with_tax of OfferItem
                # taking into account "add_2_stock"
                offer_item.previous_add_2_stock = DECIMAL_ZERO
                offer_item.save()

        if offer_item_qs is not None:
            purchase_set = purchase.Purchase.objects \
                .filter(permanence_id=self.id, offer_item__in=offer_item_qs) \
                .order_by('?')
        else:
            purchase_set = purchase.Purchase.objects \
                .filter(permanence_id=self.id) \
                .order_by('?')

        for a_purchase in purchase_set.select_related("offer_item"):
            # Recalculate the total_price_with_tax of ProducerInvoice,
            # the total_price_with_tax of CustomerInvoice,
            # the total_purchase_with_tax + total_selling_with_tax of CustomerProducerInvoice,
            # and quantity_invoiced + total_purchase_with_tax + total_selling_with_tax of OfferItem
            if send_to_producer or re_init:
                a_purchase.previous_quantity_ordered = DECIMAL_ZERO
                a_purchase.previous_quantity_invoiced = DECIMAL_ZERO
                a_purchase.previous_purchase_price = DECIMAL_ZERO
                a_purchase.previous_selling_price = DECIMAL_ZERO
                a_purchase.previous_producer_vat = DECIMAL_ZERO
                a_purchase.previous_customer_vat = DECIMAL_ZERO
                a_purchase.previous_deposit = DECIMAL_ZERO
                if send_to_producer:
                    offer_item = a_purchase.offer_item
                    if offer_item.order_unit == PRODUCT_ORDER_UNIT_PC_KG:
                        a_purchase.quantity_invoiced = (a_purchase.quantity_ordered * offer_item.order_average_weight) \
                            .quantize(FOUR_DECIMALS)
                    else:
                        a_purchase.quantity_invoiced = a_purchase.quantity_ordered
            a_purchase.save()
        self.save()

    def recalculate_profit(self):
        getcontext().rounding = ROUND_HALF_UP

        result_set = invoice.CustomerInvoice.objects.filter(
            permanence_id=self.id,
            is_group=True,
        ).order_by('?').aggregate(
            Sum('delta_price_with_tax'),
            Sum('delta_vat'),
            Sum('delta_transport')
        )
        if result_set["delta_price_with_tax__sum"] is not None:
            ci_sum_delta_price_with_tax = result_set["delta_price_with_tax__sum"]
        else:
            ci_sum_delta_price_with_tax = DECIMAL_ZERO
        if result_set["delta_vat__sum"] is not None:
            ci_sum_delta_vat = result_set["delta_vat__sum"]
        else:
            ci_sum_delta_vat = DECIMAL_ZERO
        if result_set["delta_transport__sum"] is not None:
            ci_sum_delta_transport = result_set["delta_transport__sum"]
        else:
            ci_sum_delta_transport = DECIMAL_ZERO

        result_set = purchase.Purchase.objects.filter(
            permanence_id=self.id,
            offer_item__price_list_multiplier__gte=DECIMAL_ONE
        ).order_by('?').aggregate(
            Sum('purchase_price'),
            Sum('selling_price'),
            Sum('producer_vat'),
            Sum('customer_vat'),
        )
        if result_set["purchase_price__sum"] is not None:
            purchase_price = result_set["purchase_price__sum"]
        else:
            purchase_price = DECIMAL_ZERO
        if result_set["selling_price__sum"] is not None:
            selling_price = result_set["selling_price__sum"]
        else:
            selling_price = DECIMAL_ZERO
        selling_price += ci_sum_delta_price_with_tax + ci_sum_delta_transport
        if result_set["producer_vat__sum"] is not None:
            producer_vat = result_set["producer_vat__sum"]
        else:
            producer_vat = DECIMAL_ZERO
        if result_set["customer_vat__sum"] is not None:
            customer_vat = result_set["customer_vat__sum"]
        else:
            customer_vat = DECIMAL_ZERO
        customer_vat += ci_sum_delta_vat
        self.total_purchase_with_tax = purchase_price
        self.total_selling_with_tax = selling_price
        self.total_purchase_vat = producer_vat
        self.total_selling_vat = customer_vat

        result_set = purchase.Purchase.objects.filter(
            permanence_id=self.id,
            offer_item__price_list_multiplier__lt=DECIMAL_ONE
        ).order_by('?').aggregate(
            Sum('selling_price'),
            Sum('customer_vat'),
        )
        if result_set["selling_price__sum"] is not None:
            selling_price = result_set["selling_price__sum"]
        else:
            selling_price = DECIMAL_ZERO
        if result_set["customer_vat__sum"] is not None:
            customer_vat = result_set["customer_vat__sum"]
        else:
            customer_vat = DECIMAL_ZERO
        self.total_purchase_with_tax += selling_price
        self.total_selling_with_tax += selling_price
        self.total_purchase_vat += customer_vat
        self.total_selling_vat += customer_vat

    @cached_property
    def get_new_products(self):
        assert self.status < PERMANENCE_SEND
        result = []
        for a_producer in self.producers.all():
            current_products = list(offeritem.OfferItem.objects.filter(
                is_active=True,
                may_order=True,
                order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,  # Don't display technical products.
                permanence_id=self.id,
                producer=a_producer
            ).values_list(
                'product', flat=True
            ).order_by('?'))
            six_months_ago = timezone.now().date() - datetime.timedelta(days=6*30)
            previous_permanence = Permanence.objects.filter(
                status__gte=PERMANENCE_SEND,
                producers=a_producer,
                permanence_date__gte=six_months_ago
            ).order_by(
                "-permanence_date",
                "status"
            ).first()
            if previous_permanence is not None:
                previous_products = list(offeritem.OfferItem.objects.filter(
                    is_active=True,
                    may_order=True,
                    order_unit__lt=PRODUCT_ORDER_UNIT_DEPOSIT,  # Don't display technical products.
                    permanence_id=previous_permanence.id,
                    producer=a_producer
                ).values_list(
                    'product', flat=True
                ).order_by('?'))
                new_products = [item for item in current_products if item not in previous_products]
            else:
                new_products = current_products

            qs = offeritem.OfferItem.objects.filter(
                permanence_id=self.id,
                product__in=new_products,
                translations__language_code=translation.get_language()
            ).order_by(
                "translations__order_sort_order"
            )
            for o in qs:
                result.append('<li>%s, %s, %s</li>' % (
                    o.get_long_name(box_unicode=EMPTY_STRING),
                    o.producer.short_profile_name,
                    o.email_offer_price_with_vat,
                ))
        if result:
            return '<ul>%s</ul>' % "".join(result)
        return EMPTY_STRING

    def get_full_status_display(self):
        need_to_refresh_status = self.status in [
            PERMANENCE_WAIT_FOR_PRE_OPEN,
            PERMANENCE_WAIT_FOR_OPEN,
            PERMANENCE_WAIT_FOR_CLOSED,
            PERMANENCE_WAIT_FOR_SEND,
            PERMANENCE_WAIT_FOR_INVOICED
        ]
        if self.with_delivery_point:
            status_list = []
            status = None
            status_counter = 0
            for delivery in deliveryboard.DeliveryBoard.objects.filter(permanence_id=self.id).order_by("status", "id"):
                need_to_refresh_status |= delivery.status in [
                    PERMANENCE_WAIT_FOR_PRE_OPEN,
                    PERMANENCE_WAIT_FOR_OPEN,
                    PERMANENCE_WAIT_FOR_CLOSED,
                    PERMANENCE_WAIT_FOR_SEND,
                    PERMANENCE_WAIT_FOR_INVOICED
                ]
                if status != delivery.status:
                    status = delivery.status
                    status_counter += 1
                    status_list.append("<b>%s</b>" % delivery.get_status_display())
                status_list.append("- %s" % delivery.get_delivery_display(admin=True))
            if status_counter > 1:
                message = "<br/>".join(status_list)
            else:
                message = self.get_status_display()
        else:
            message = self.get_status_display()
        if need_to_refresh_status:
            url = urlresolvers.reverse(
                'display_status',
                args=(self.id,)
            )
            progress = "◤◥◢◣"[self.gauge] # "◴◷◶◵" "▛▜▟▙"
            self.gauge = (self.gauge + 1) % 4
            self.save(update_fields=['gauge'])
            msg_html = """
                    <div class="wrap-text" id="id_get_status_%d">
                    <script type="text/javascript">
                        window.setTimeout(function(){
                            django.jQuery.ajax({
                                url: '%s',
                                cache: false,
                                async: false,
                                success: function (result) {
                                    django.jQuery("#id_get_status_%d").html(result);
                                }
                            });
                        }, 500);
                    </script>
                    %s %s</div>
                """ % (
                self.id, url, self.id, progress, message
            )
            return mark_safe(msg_html)
        else:
            return mark_safe('<div class="wrap-text">%s</div>' % message)

    get_full_status_display.short_description = (_("permanence_status"))
    get_full_status_display.allow_tags = True

    def get_permanence_display(self):
        short_name = self.safe_translation_getter(
            'short_name', any_language=True
        )
        if short_name:
            permanence_display = "%s" % short_name
        else:
            permanence_display = '%s%s' % (
                repanier.apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME,
                self.permanence_date.strftime(settings.DJANGO_SETTINGS_DATE)
            )
        return permanence_display

    def get_permanence_admin_display(self):
        if self.status == PERMANENCE_INVOICED and self.total_selling_with_tax.amount != DECIMAL_ZERO:
            profit = self.total_selling_with_tax.amount - self.total_purchase_with_tax.amount
            # profit = self.total_selling_with_tax.amount - self.total_selling_vat.amount - self.total_purchase_with_tax.amount + self.total_purchase_vat.amount
            if profit != DECIMAL_ZERO:
                return '%s<br/>%s<br/>💶&nbsp;%s' % (
                    self.get_permanence_display(), self.total_selling_with_tax, RepanierMoney(profit)
                )
            return '%s<br/>%s' % (
                self.get_permanence_display(), self.total_selling_with_tax)
        else:
            return self.get_permanence_display()

    get_permanence_admin_display.short_description = lambda: "%s" % repanier.apps.REPANIER_SETTINGS_PERMANENCES_NAME
    get_permanence_admin_display.allow_tags = True

    def get_permanence_customer_display(self, with_status=True):
        if with_status:
            if self.with_delivery_point:
                if self.status == PERMANENCE_OPENED:
                    deliveries_count = 0
                else:
                    deliveries_qs = deliveryboard.DeliveryBoard.objects.filter(
                        permanence_id=self.id,
                        status=PERMANENCE_OPENED
                    ).order_by('?')
                    deliveries_count = deliveries_qs.count()
            else:
                deliveries_count = 0
            if deliveries_count == 0:
                if self.status != PERMANENCE_SEND:
                    return "%s - %s" % (self.get_permanence_display(), self.get_status_display())
                else:
                    return "%s - %s" % (self.get_permanence_display(), _('orders closed'))
        return self.get_permanence_display()

    def __str__(self):
        return self.get_permanence_display()

    class Meta:
        verbose_name = _('order')
        verbose_name_plural = _('orders')

        # index_together = [
        #     ["permanence_date"],
        # ]


class PermanenceInPreparation(Permanence):
    class Meta:
        proxy = True
        verbose_name = _('In preparation')
        verbose_name_plural = _('In preparation')


class PermanenceDone(Permanence):
    class Meta:
        proxy = True
        verbose_name = _('In billing')
        verbose_name_plural = _('In billing')

