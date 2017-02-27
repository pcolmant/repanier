# -*- coding: utf-8
from __future__ import unicode_literals

from django.conf import settings
from django.core import urlresolvers
from django.core.cache import cache
from django.db import models
from django.db.models import F
from django.db.models.signals import post_init
from django.dispatch import receiver
from django.utils import timezone
from django.utils import translation
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from menus.menu_pool import menu_pool
from parler.models import TranslatableModel, TranslatedFields
from parler.models import TranslationDoesNotExist

import configuration
import customer
import deliveryboard
import invoice
import permanenceboard
import producer
import purchase
import repanier.apps
from repanier.const import *
from repanier.tools import get_full_status_display


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
        cache_part_d=HTMLField(configuration='CKEDITOR_SETTINGS_MODEL2', blank=True, default=EMPTY_STRING)
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

    def get_producers(self):
        if self.id is not None:
            if len(self.producers.all()) > 0:
                if self.status == PERMANENCE_PLANNED:
                    changelist_url = urlresolvers.reverse(
                        'admin:repanier_product_changelist',
                    )
                    link = []
                    for p in self.producers.all():
                        link.append(
                            '<a href=%s?producer=%d>&nbsp;%s</a>' % (
                                changelist_url, p.id, p.short_profile_name))
                    return '<div class="wrap-text">%s</div>' % ", ".join(link)
                elif self.status == PERMANENCE_PRE_OPEN:
                    return '<div class="wrap-text">%s</div>' % ", ".join([p.short_profile_name + " (" + p.phone1 + ")" for p in self.producers.all()])
                elif self.status in [PERMANENCE_OPENED, PERMANENCE_CLOSED]:
                    close_offeritem_changelist_url = urlresolvers.reverse(
                        'admin:repanier_offeritemclosed_changelist',
                    )
                    send_offeritem_changelist_url = urlresolvers.reverse(
                        'admin:repanier_offeritemsend_changelist',
                    )
                    send_customer_changelist_url = urlresolvers.reverse(
                        'admin:repanier_customersend_changelist',
                    )

                    link = []
                    for p in self.producers.all().only("id"):
                        pi = invoice.ProducerInvoice.objects.filter(producer_id=p.id, permanence_id=self.id) \
                            .order_by('?').first()
                        if pi is not None:
                            if pi.status > PERMANENCE_OPENED:
                                label = ('%s (%s) %s' % (p.short_profile_name, pi.get_total_price_with_tax(), LOCK_UNICODE)).replace(' ',
                                                                                                            '&nbsp;')
                                if pi.status == PERMANENCE_SEND:
                                    if p.invoice_by_basket:
                                        offeritem_changelist_url = send_customer_changelist_url
                                    else:
                                        offeritem_changelist_url = send_offeritem_changelist_url
                                else:
                                    offeritem_changelist_url = close_offeritem_changelist_url
                            else:
                                label = ('%s (%s) ' % (p.short_profile_name, pi.get_total_price_with_tax())).replace(' ', '&nbsp;')
                                offeritem_changelist_url = close_offeritem_changelist_url
                        else:
                            label = ('%s ' % (p.short_profile_name,)).replace(' ', '&nbsp;')
                            offeritem_changelist_url = close_offeritem_changelist_url
                        link.append(
                            '<a href="%s?permanence=%s&producer=%d">%s</a>' % (
                                offeritem_changelist_url, self.id, p.id, label))
                    return '<div class="wrap-text">%s</div>' % ", ".join(link)
                elif self.status == PERMANENCE_SEND:
                    send_offeritem_changelist_url = urlresolvers.reverse(
                        'admin:repanier_offeritemsend_changelist',
                    )
                    send_customer_changelist_url = urlresolvers.reverse(
                        'admin:repanier_customersend_changelist',
                    )
                    link = []
                    for p in self.producers.all().only("id", "short_profile_name", "invoice_by_basket"):
                        if p.invoice_by_basket:
                            changelist_url = send_customer_changelist_url
                        else:
                            changelist_url = send_offeritem_changelist_url
                        pi = invoice.ProducerInvoice.objects.filter(producer_id=p.id, permanence_id=self.id) \
                            .order_by('?').first()
                        if pi is not None:
                            label = '%s (%s) %s' % (p.short_profile_name, pi.get_total_price_with_tax(), LOCK_UNICODE)
                            link.append(
                                '<a href="%s?permanence=%d&producer=%d">&nbsp;%s</a>' % (
                                    changelist_url, self.id, p.id, label.replace(' ', '&nbsp;')
                                ))
                        else:
                            link.append(
                                '<a href="%s?permanence=%d&producer=%d">&nbsp;%s</a>' % (
                                    changelist_url, self.id, p.id, p.short_profile_name.replace(' ', '&nbsp;')
                                ))

                    return '<div class="wrap-text">%s</div>' % ", ".join(link)
                elif self.status in [PERMANENCE_DONE, PERMANENCE_ARCHIVED]:
                    link = []
                    for pi in invoice.ProducerInvoice.objects.filter(permanence_id=self.id).select_related(
                            "producer").order_by('producer'):
                        label = "%s (%s) %s" % (
                            pi.producer.short_profile_name,
                            pi.get_total_price_with_tax(),
                            pi.get_to_be_paid_display()
                        )
                        link.append(
                            '<a href="%s?producer=%d" target="_blank" %s>%s</a>'
                            % (
                                urlresolvers.reverse('producer_invoice_view', args=(pi.id,)),
                                pi.producer_id,
                                EMPTY_STRING if not pi.to_be_paid else '',
                                label.replace(' ', '&nbsp;')))
                    producers = ", ".join(link)
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
                    return ", ".join([p.short_profile_name
                                           for p in
                                           producer.Producer.objects.filter(
                                               producerinvoice__permanence_id=self.id).only(
                                               'short_profile_name')])
            else:
                return '<div class="wrap-text">%s</div>' % _("No offer")
        return "?"

    get_producers.short_description = (_("producers in this permanence"))
    get_producers.allow_tags = True

    def get_customers(self):
        if self.id is not None:
            if self.status in [
                PERMANENCE_OPENED, PERMANENCE_CLOSED, PERMANENCE_SEND
            ]:
                changelist_url = urlresolvers.reverse(
                    'admin:repanier_purchase_changelist',
                )
                link = []
                for ci in invoice.CustomerInvoice.objects.filter(permanence_id=self.id).select_related(
                    "customer").order_by('customer'):
                    if ci.is_order_confirm_send:
                        label = '%s (%s) %s' % (
                            ci.customer.short_basket_name, ci.get_total_price_with_tax(customer_who_pays=True),
                            ci.get_is_order_confirm_send_display())
                    else:
                        label = '%s (%s) %s' % (
                            ci.customer.short_basket_name, ci.total_price_with_tax,
                            ci.get_is_order_confirm_send_display())
                    link.append(
                        '<a href="%s?permanence=%d&customer=%d" target="_blank">%s</a>'
                        % (changelist_url, self.id, ci.customer_id, label.replace(' ', '&nbsp;')))
                customers = ", ".join(link)
            elif self.status == PERMANENCE_DONE:
                link = []
                for ci in invoice.CustomerInvoice.objects.filter(permanence_id=self.id).select_related(
                    "customer").order_by('customer'):
                    label = "%s (%s) %s" % (
                        ci.customer.short_basket_name,
                        ci.get_total_price_with_tax(customer_who_pays=True),
                        ci.get_is_order_confirm_send_display()
                    )
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
        return "?"

    get_customers.short_description = (_("customers in this permanence"))
    get_customers.allow_tags = True

    def get_board(self):
        if self.id is not None:
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
                                 '" > target="_blank"' + c.short_basket_name.replace(' ', '&nbsp;') + '</a>'
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
        return "?"

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
                    update_fields=['status', 'is_updated_on', 'highest_status', 'with_delivery_point', 'payment_date'])
            else:
                self.save(update_fields=['status', 'is_updated_on', 'with_delivery_point', 'highest_status'])
            menu_pool.clear()
            cache.clear()
            if new_status == PERMANENCE_WAIT_FOR_OPEN:
                self.with_delivery_point = deliveryboard.DeliveryBoard.objects.filter(
                    permanence_id=self.id
                ).order_by('?').exists()
                if self.with_delivery_point and not repanier.apps.REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
                    config = configuration.Configuration.objects.filter(id=DECIMAL_ONE).first()
                    # Important : Customer must confirm order if deliveries points are used
                    config.customers_must_confirm_orders = True
                    config.save()
                for a_producer in producer.Producer.objects.filter(
                        permanence=self.id
                ).only('id').order_by('?'):
                    # Create ProducerInvoice to be able to close those producer on demand
                    if not invoice.ProducerInvoice.objects.filter(
                            permanence_id=self.id,
                            producer_id=a_producer.id
                    ).order_by('?').exists():
                        invoice.ProducerInvoice.objects.create(
                            permanence_id=self.id,
                            producer_id=a_producer.id
                        )
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
                self.save(update_fields=['status', 'is_updated_on', 'with_delivery_point', 'highest_status'])
            menu_pool.clear()
            cache.clear()
        else:
            # /!\ If one delivery point has been closed, I may not close anymore by producer
            purchase.Purchase.objects.filter(permanence_id=self.id, producer__in=producers_id).order_by('?').update(
                status=new_status)
            invoice.ProducerInvoice.objects.filter(permanence_id=self.id, producer__in=producers_id).order_by(
                '?').update(status=new_status)

    def get_full_status_display(self):
        return get_full_status_display(self)

    get_full_status_display.short_description = (_("permanence_status"))
    get_full_status_display.allow_tags = True

    def get_permanence_display(self, with_status=True):
        permanence_display = '%s%s' % (
            repanier.apps.REPANIER_SETTINGS_PERMANENCE_ON_NAME,
            self.permanence_date.strftime(settings.DJANGO_SETTINGS_DATE)
        )
        try:
            if self.short_name:
                permanence_display = "%s" % self.short_name
        except TranslationDoesNotExist:
            pass

        if with_status:
            if self.with_delivery_point:
                if self.status == PERMANENCE_OPENED:
                    deliveries_count = 0
                else:
                    deliveries_qs = deliveryboard.DeliveryBoard.objects.filter(permanence_id=self.id,
                                                                               status=PERMANENCE_OPENED).order_by('?')
                    deliveries_count = deliveries_qs.count()
            else:
                deliveries_count = 0
            if deliveries_count == 0:
                return "%s - %s" % (permanence_display, self.get_status_display())
        return permanence_display

    def get_permanence_customer_display(self, with_status=True):
        permanence_display = self.get_permanence_display(with_status=False)
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
                    return "%s - %s" % (permanence_display, self.get_status_display())
                else:
                    return "%s - %s" % (permanence_display, _('orders closed'))
        return permanence_display

    def __str__(self):
        return self.get_permanence_display(with_status=False)

    class Meta:
        verbose_name = repanier.apps.REPANIER_SETTINGS_PERMANENCE_NAME or _("permanence")
        verbose_name_plural = repanier.apps.REPANIER_SETTINGS_PERMANENCES_NAME or _("permanences")

        index_together = [
            ["permanence_date"],
        ]


class PermanenceInPreparation(Permanence):
    class Meta:
        proxy = True
        verbose_name = _("X in preparation")
        verbose_name_plural = _("Xs in preparation")


class PermanenceDone(Permanence):
    class Meta:
        proxy = True
        verbose_name = _("X done")
        verbose_name_plural = _("Xs done")
