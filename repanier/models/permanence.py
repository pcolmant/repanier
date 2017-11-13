# -*- coding: utf-8

import datetime

from django.conf import settings
from django.core import urlresolvers
from django.core.cache import cache
from django.db import models
from django.db.models import F, Sum
from django.utils import timezone, translation
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField
from menus.menu_pool import menu_pool
from parler.models import TranslatableModel, TranslatedFields, TranslationDoesNotExist

import repanier.apps
from repanier.const import *
from repanier.fields.RepanierMoneyField import ModelMoneyField
from repanier.models.customer import Customer
from repanier.models.deliveryboard import DeliveryBoard
from repanier.models.invoice import CustomerInvoice, CustomerProducerInvoice, ProducerInvoice
from repanier.models.offeritem import OfferItem, OfferItemWoReceiver
from repanier.models.permanenceboard import PermanenceBoard
from repanier.models.producer import Producer
from repanier.picture.const import SIZE_L
from repanier.picture.fields import AjaxPictureField
from repanier.tools import cap


class Permanence(TranslatableModel):
    translations = TranslatedFields(
        short_name=models.CharField(
            _("Offer name"),
            max_length=50, blank=True
        ),
        offer_description=HTMLField(
            _("Offer description"),
            configuration='CKEDITOR_SETTINGS_MODEL2',
            help_text=_(
                "This message is send by mail to all customers when opening the order or on top "),
            blank=True, default=EMPTY_STRING
        ),
        invoice_description=HTMLField(
            _("Invoice description"),
            configuration='CKEDITOR_SETTINGS_MODEL2',
            help_text=_(
                'This message is send by mail to all customers having bought something when closing the permanence.'),
            blank=True, default=EMPTY_STRING
        ),
    )

    status = models.CharField(
        _("Status"),
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
    )
    permanence_date = models.DateField(
        _("Date"), db_index=True
    )
    payment_date = models.DateField(
        _("Payment date"), blank=True, null=True, db_index=True
    )
    producers = models.ManyToManyField(
        'Producer',
        verbose_name=_("Producers"),
        blank=True
    )
    boxes = models.ManyToManyField(
        'Box',
        verbose_name=_('Boxes'),
        blank=True
    )
    contract = models.ForeignKey(
        'Contract',
        verbose_name=_("Commitment"),
        on_delete=models.PROTECT,
        null=True, blank=True, default=None
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
        _("VAT"),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)
    total_selling_vat = ModelMoneyField(
        _("VAT"),
        help_text=_('Vat'),
        default=DECIMAL_ZERO, max_digits=9, decimal_places=4)

    with_delivery_point = models.BooleanField(
        _("With delivery point"), default=False)
    automatically_closed = models.BooleanField(
        _("Automatically closed"), default=False)
    is_updated_on = models.DateTimeField(
        _("Updated on"), auto_now=True)
    highest_status = models.CharField(
        max_length=3,
        choices=LUT_PERMANENCE_STATUS,
        default=PERMANENCE_PLANNED,
        verbose_name=_("Highest status"),
    )
    master_permanence = models.ForeignKey(
        'Permanence',
        verbose_name=_("Master permanence"),
        related_name='child_permanence',
        blank=True, null=True, default=None,
        on_delete=models.PROTECT, db_index=True)
    invoice_sort_order = models.IntegerField(
        _("Invoice sort order"),
        default=None, blank=True, null=True)
    offer_description_on_home_page = models.BooleanField(
        _("Publish the offer description on the home page when the permanence is open"), default=True)
    picture = AjaxPictureField(
        verbose_name=_("Picture"),
        null=True, blank=True,
        upload_to="permanence", size=SIZE_L)
    gauge = models.IntegerField(
        default=0, editable=False
    )

    @cached_property
    def get_producers(self):
        if self.status == PERMANENCE_PLANNED:
            link = []
            if self.contract and len(self.contract.producers.all()) > 0:
                changelist_url = urlresolvers.reverse(
                    'admin:repanier_product_changelist',
                )
                for p in self.contract.producers.all():
                    link.append(
                        "<a href=\"{}?producer={}&commitment={}\">&nbsp;{}&nbsp;{}</a>".format(
                            changelist_url, p.id, self.contract.id, LINK_UNICODE, p.short_profile_name.replace(" ", "&nbsp;"))
                    )
            elif len(self.producers.all()) > 0:
                changelist_url = urlresolvers.reverse(
                    'admin:repanier_product_changelist',
                )
                for p in self.producers.all():
                    link.append(
                        "<a href=\"{}?producer={}\">&nbsp;{}</a>".format(
                            changelist_url, p.id, p.short_profile_name.replace(" ", "&nbsp;"))
                    )
            if len(link) > 0:
                msg_html = "<div class=\"wrap-text\">{}</div>".format(", ".join(link))
            else:
                msg_html = "<div class=\"wrap-text\">{}</div>".format(_("No offer"))
        elif self.status == PERMANENCE_PRE_OPEN:
            link = []
            for p in self.producers.all():
                if p.phone1 is not None:
                    link.append("{} ({})".format(p.short_profile_name, p.phone1).replace(" ", "&nbsp;"))
                else:
                    link.append(p.short_profile_name.replace(" ", "&nbsp;"))
            msg_html = "<div class=\"wrap-text\">{}</div>".format(", ".join(link))
        elif self.status in [PERMANENCE_OPENED, PERMANENCE_CLOSED]:
            close_offeritem_changelist_url = urlresolvers.reverse(
                'admin:repanier_offeritemclosed_changelist',
            )

            link = []
            if self.contract and len(self.contract.producers.all()) > 0:
                link_unicode = "{} ".format(LINK_UNICODE)
            else:
                link_unicode = EMPTY_STRING
            for p in self.producers.all().only("id"):
                pi = ProducerInvoice.objects.filter(
                    producer_id=p.id, permanence_id=self.id
                ).order_by('?').first()
                if pi is not None:
                    if pi.status == PERMANENCE_OPENED:
                        label = ("{}{} ({}) ".format(link_unicode, p.short_profile_name, pi.get_total_price_with_tax())).replace(
                            ' ', '&nbsp;')
                        offeritem_changelist_url = close_offeritem_changelist_url
                    else:
                        label = ("{}{} ({}) {}".format( link_unicode,
                        p.short_profile_name, pi.get_total_price_with_tax(), LOCK_UNICODE)).replace(' ',
                                                                                                    '&nbsp;')
                        offeritem_changelist_url = close_offeritem_changelist_url
                else:
                    label = ("{}{} ".format(link_unicode, p.short_profile_name,)).replace(' ', '&nbsp;')
                    offeritem_changelist_url = close_offeritem_changelist_url
                link.append(
                    "<a href=\"{}?permanence={}&producer={}\">{}</a>".format(
                        offeritem_changelist_url, self.id, p.id, label))
            msg_html = "<div class=\"wrap-text\">{}</div>".format(", ".join(link))

        elif self.status in [PERMANENCE_SEND, PERMANENCE_INVOICED, PERMANENCE_ARCHIVED]:
            if self.contract and len(self.contract.producers.all()) > 0:
                link_unicode = "{} ".format(LINK_UNICODE)
            else:
                link_unicode = EMPTY_STRING
            send_offeritem_changelist_url = urlresolvers.reverse(
                'admin:repanier_offeritemsend_changelist',
            )
            send_customer_changelist_url = urlresolvers.reverse(
                'admin:repanier_customersend_changelist',
            )
            link = []
            at_least_one_permanence_send = False
            for pi in ProducerInvoice.objects.filter(permanence_id=self.id).select_related(
                    "producer").order_by('producer'):
                if pi.status == PERMANENCE_SEND:
                    at_least_one_permanence_send = True
                    if pi.producer.invoice_by_basket:
                        changelist_url = send_customer_changelist_url
                    else:
                        changelist_url = send_offeritem_changelist_url
                    # Important : no target="_blank"
                    label = "{}{} ({}) {}".format( link_unicode,
                    pi.producer.short_profile_name, pi.get_total_price_with_tax(), LOCK_UNICODE)
                    link.append(
                        "<a href=\"{}?permanence={}&producer={}\">&nbsp;{}</a>".format(
                            changelist_url, self.id, pi.producer_id, label.replace(' ', '&nbsp;')
                        ))
                else:
                    if pi.invoice_reference:
                        if pi.to_be_invoiced_balance != DECIMAL_ZERO or pi.total_price_with_tax != DECIMAL_ZERO:
                            label = "{}{} ({} - {})".format(
                                link_unicode,
                                pi.producer.short_profile_name,
                                pi.to_be_invoiced_balance,
                                cap(pi.invoice_reference, 15)
                            )
                        else:
                            label = "{}{} ({})".format(
                                link_unicode,
                                pi.producer.short_profile_name,
                                cap(pi.invoice_reference, 15)
                            )
                    else:
                        if pi.to_be_invoiced_balance != DECIMAL_ZERO or pi.total_price_with_tax != DECIMAL_ZERO:
                            label = "{}{} ({})".format(
                                link_unicode,
                                pi.producer.short_profile_name,
                                pi.to_be_invoiced_balance
                            )
                        else:
                            continue
                    # Important : target="_blank" because the invoices must be displayed without the cms_toolbar
                    # Such that they can be accessed by the producer and by the staff
                    link.append(
                        "<a href=\"{}?producer={}\" target=\"_blank\">{}</a>".format(
                            urlresolvers.reverse('producer_invoice_view', args=(pi.id,)),
                            pi.producer_id,
                            label.replace(' ', '&nbsp;')))

            producers = ", ".join(link)
            if at_least_one_permanence_send:
                msg_html = "<div class=\"wrap-text\">{}</div>".format(producers)
            else:
                msg_html = """
                    <div class="wrap-text"><button
                    onclick="django.jQuery('#id_get_producers_{}').toggle();
                        if(django.jQuery(this).html()=='{}'){{
                            django.jQuery(this).html('{}')
                        }}else{{
                            django.jQuery(this).html('{}')
                        }};
                        return false;"
                    >{}</button>
                    <div id="id_get_producers_{}" style="display:none;">{}</div></div>
                """.format(
                    self.id, _("Show"), _("Hide"), _("Show"), _("Show"), self.id, producers
                )
        else:
            msg_html = "<div class=\"wrap-text\">{}</div>".format(", ".join([p.short_profile_name
                                   for p in
                                   Producer.objects.filter(
                                       producerinvoice__permanence_id=self.id).only(
                                       'short_profile_name')]))
        return mark_safe(msg_html)

    get_producers.short_description = (_("Offers from"))
    # get_producers.allow_tags = True

    @cached_property
    def get_customers(self):
        if self.status in [
            PERMANENCE_OPENED, PERMANENCE_CLOSED, PERMANENCE_SEND
        ]:
            changelist_url = urlresolvers.reverse(
                'admin:repanier_purchase_changelist',
            )
            link = []
            delivery_save = None
            for ci in CustomerInvoice.objects.filter(permanence_id=self.id).select_related(
                "customer").order_by('delivery', 'customer'):
                if delivery_save != ci.delivery:
                    delivery_save = ci.delivery
                    if ci.delivery is not None:
                        link.append("<br><b>{}</b>".format(ci.delivery.get_delivery_display()))
                    else:
                        link.append("<br><br>--")
                total_price_with_tax = ci.get_total_price_with_tax(customer_charged=True)
                # if ci.is_order_confirm_send:
                label = "{}{} ({}) {}{}".format(
                    "<b><i>" if ci.is_group else EMPTY_STRING,
                    ci.customer.short_basket_name,
                    "-" if ci.is_group or total_price_with_tax == DECIMAL_ZERO else total_price_with_tax,
                    ci.get_is_order_confirm_send_display(),
                    "</i></b>" if ci.is_group else EMPTY_STRING,
                )
                # Important : no target="_blank"
                link.append(
                    "<a href=\"{}?permanence={}&customer={}\">{}</a>".format(
                        changelist_url, self.id, ci.customer_id, label.replace(' ', '&nbsp;'))
                )
            customers = ", ".join(link)
        elif self.status in [PERMANENCE_INVOICED, PERMANENCE_ARCHIVED]:
            link = []
            delivery_save = None
            for ci in CustomerInvoice.objects.filter(permanence_id=self.id).select_related(
                "customer").order_by('delivery', 'customer'):
                if delivery_save != ci.delivery:
                    delivery_save = ci.delivery
                    if ci.delivery is not None:
                        link.append("<br><b>{}</b>".format(ci.delivery.get_delivery_display()))
                    else:
                        link.append("<br><br>--")
                total_price_with_tax = ci.get_total_price_with_tax(customer_charged=True)
                label = "{}{} ({}) {}{}".format(
                    "<b><i>" if ci.is_group else EMPTY_STRING,
                    ci.customer.short_basket_name,
                    "-" if total_price_with_tax == DECIMAL_ZERO else total_price_with_tax,
                    ci.get_is_order_confirm_send_display(),
                    "</i></b>" if ci.is_group else EMPTY_STRING,
                )
                # Important : target="_blank" because the invoices must be displayed without the cms_toolbar
                # Such that they can be accessed by the customer and by the staff
                link.append(
                    "<a href=\"{}?customer={}\" target=\"_blank\">{}</a>".format(
                        urlresolvers.reverse('customer_invoice_view', args=(ci.id,)),
                        ci.customer_id,
                        label.replace(' ', '&nbsp;')
                    )
                )
            customers = ", ".join(link)
        else:
            customers = ", ".join([c.short_basket_name
                                   for c in
                                   Customer.objects.filter(customerinvoice__permanence_id=self.id).only(
                                       'short_basket_name')])
        if len(customers) > 0:
            msg_html = """
                <div class="wrap-text"><button
                onclick="django.jQuery('#id_get_customers_{}').toggle();
                    if(django.jQuery(this).html()=='{}'){{
                        django.jQuery(this).html('{}')
                    }}else{{
                        django.jQuery(this).html('{}')
                    }};
                    return false;"
                >{}</button>
                <div id="id_get_customers_{}" style="display:none;">{}</div></div>
            """.format(
                self.id, _("Show"), _("Hide"), _("Show"), _("Show"), self.id, customers
            )
            return mark_safe(msg_html)
        else:
            return mark_safe("<div class=\"wrap-text\">{}</div>".format(_("No purchase")))

    get_customers.short_description = (_("Purchases by"))
    # get_customers.allow_tags = True

    @cached_property
    def get_board(self):
        permanenceboard_set = PermanenceBoard.objects.filter(
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
                    board += '<br>'
                board += r_link + c_link
                first_board = False
        if not first_board:
            # At least one role is defined in the permanence board
            msg_html = """
                <div class="wrap-text"><button
                onclick="django.jQuery('#id_get_board_{}').toggle();
                    if(django.jQuery(this).html()=='{}'){{
                        django.jQuery(this).html('{}')
                    }}else{{
                        django.jQuery(this).html('{}')
                    }};
                    return false;"
                >{}</button>
                <div id="id_get_board_{}" style="display:none;">{}</div></div>
            """.format(
                self.id, _("Show"), _("Hide"), _("Show"), _("Show"), self.id, board
            )
            return mark_safe(msg_html)
        else:
            return mark_safe("<div class=\"wrap-text\">{}</div>".format(_("No task")))

    get_board.short_description = (_("Tasks"))

    def set_status(self, new_status, all_producers=True, producers_id=None, update_payment_date=False,
                   payment_date=None, allow_downgrade=True):
        from repanier.models.purchase import Purchase

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
                all_producers = self.contract.producers.all() if self.contract else self.producers.all()
                for a_producer in all_producers:
                    # Create ProducerInvoice to be able to close those producer on demand
                    if not ProducerInvoice.objects.filter(
                            permanence_id=self.id,
                            producer_id=a_producer.id
                    ).order_by('?').exists():
                        ProducerInvoice.objects.create(
                            permanence_id=self.id,
                            producer_id=a_producer.id
                        )

            # self.with_delivery_point = DeliveryBoard.objects.filter(
            #     permanence_id=self.id
            # ).order_by('?').exists()
            if self.with_delivery_point:
                qs = DeliveryBoard.objects.filter(
                    permanence_id=self.id
                ).exclude(status=new_status).order_by('?')
                for delivery_point in qs:
                    if allow_downgrade or delivery_point.status < new_status:
                        # --> or delivery_point.status < new_status -->
                        # Set new status except if PERMANENCE_SEND, PERMANENCE_WAIT_FOR_SEND
                        #  -> PERMANENCE_CLOSED, PERMANENCE_WAIT_FOR_CLOSED
                        # This occur if directly sending order of a opened delivery point
                        delivery_point.set_status(new_status)
            CustomerInvoice.objects.filter(
                permanence_id=self.id,
                delivery__isnull=True
            ).order_by('?').update(
                status=new_status
            )
            Purchase.objects.filter(
                permanence_id=self.id,
                customer_invoice__delivery__isnull=True
            ).order_by('?').update(
                status=new_status)
            ProducerInvoice.objects.filter(
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
            Purchase.objects.filter(permanence_id=self.id, producer__in=producers_id).order_by('?').update(
                status=new_status)
            ProducerInvoice.objects.filter(permanence_id=self.id, producer__in=producers_id).order_by(
                '?').update(status=new_status)

    def duplicate(self, dates):
        creation_counter = 0
        short_name = self.safe_translation_getter(
            'short_name', any_language=True, default=EMPTY_STRING
        )
        cur_language = translation.get_language()
        for date in dates:
            delta_days = (date - self.permanence_date).days
            # Mandatory because of Parler
            if short_name != EMPTY_STRING:
                already_exists = Permanence.objects.filter(
                    permanence_date=date,
                    translations__language_code=cur_language,
                    translations__short_name=short_name
                ).exists()
            else:
                already_exists = False
                for existing_permanence in Permanence.objects.filter(
                        permanence_date=date
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
                    permanence_date=date
                )
                self.duplicate_short_name(
                    new_permanence,
                    cur_language=translation.get_language(),
                )
                for permanence_board in PermanenceBoard.objects.filter(
                        permanence=self
                ):
                    PermanenceBoard.objects.create(
                        permanence=new_permanence,
                        permanence_role=permanence_board.permanence_role
                    )
                for delivery_board in DeliveryBoard.objects.filter(
                        permanence=self
                ):
                    # if delivery_board.delivery_date is not None:
                    #     new_delivery_board = DeliveryBoard.objects.create(
                    #         permanence=new_permanence,
                    #         delivery_point=delivery_board.delivery_point,
                    #         delivery_date=delivery_board.delivery_date + datetime.timedelta(days=delta_days)
                    #     )
                    # else:
                    new_delivery_board = DeliveryBoard.objects.create(
                        permanence=new_permanence,
                        delivery_point=delivery_board.delivery_point,
                    )
                    for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
                        language_code = language["code"]
                        translation.activate(language_code)
                        new_delivery_board.set_current_language(language_code)
                        delivery_board.set_current_language(language_code)
                        try:
                            new_delivery_board.delivery_comment = delivery_board.delivery_comment
                            new_delivery_board.save_translation()
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
                new_permanence.short_name = self.safe_translation_getter('short_name', any_language=True)
                new_permanence.save_translation()
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
        from repanier.models.purchase import Purchase
        getcontext().rounding = ROUND_HALF_UP

        if send_to_producer or re_init:
            assert offer_item_qs is None, 'offer_item_qs must be set to None when send_to_producer or re_init'
            ProducerInvoice.objects.filter(
                permanence_id=self.id
            ).update(
                total_price_with_tax=DECIMAL_ZERO,
                total_vat=DECIMAL_ZERO,
                total_deposit=DECIMAL_ZERO,
            )
            CustomerInvoice.objects.filter(
                permanence_id=self.id
            ).update(
                total_price_with_tax=DECIMAL_ZERO,
                total_vat=DECIMAL_ZERO,
                total_deposit=DECIMAL_ZERO
            )
            CustomerProducerInvoice.objects.filter(
                permanence_id=self.id
            ).update(
                total_purchase_with_tax=DECIMAL_ZERO,
                total_selling_with_tax=DECIMAL_ZERO
            )
            OfferItemWoReceiver.objects.filter(
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
            for offer_item in OfferItem.objects.filter(
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
            purchase_set = Purchase.objects \
                .filter(permanence_id=self.id, offer_item__in=offer_item_qs) \
                .order_by('?')
        else:
            purchase_set = Purchase.objects \
                .filter(permanence_id=self.id) \
                .order_by('?')

        for a_purchase in purchase_set.select_related("offer_item", "customer_invoice"):
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
                if send_to_producer and a_purchase.status == PERMANENCE_WAIT_FOR_SEND:
                    offer_item = a_purchase.offer_item
                    if offer_item.order_unit == PRODUCT_ORDER_UNIT_PC_KG:
                        a_purchase.quantity_invoiced = (a_purchase.quantity_ordered * offer_item.order_average_weight) \
                            .quantize(FOUR_DECIMALS)
                    else:
                        a_purchase.quantity_invoiced = a_purchase.quantity_ordered
            a_purchase.save()

        if send_to_producer:
            OfferItemWoReceiver.objects.filter(
                permanence_id=self.id,
                order_unit=PRODUCT_ORDER_UNIT_PC_KG
            ).order_by('?').update(
                use_order_unit_converted=True
            )
        self.save()

    def recalculate_profit(self):
        from repanier.models.purchase import Purchase
        getcontext().rounding = ROUND_HALF_UP

        result_set = CustomerInvoice.objects.filter(
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

        result_set = Purchase.objects.filter(
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

        result_set = Purchase.objects.filter(
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
            current_products = list(OfferItemWoReceiver.objects.filter(
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
                previous_products = list(OfferItemWoReceiver.objects.filter(
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

            qs = OfferItemWoReceiver.objects.filter(
                permanence_id=self.id,
                product__in=new_products,
                translations__language_code=translation.get_language()
            ).order_by(
                "translations__order_sort_order"
            )
            department_for_customer_save = None
            for o in qs:
                if department_for_customer_save != o.department_for_customer:
                    if department_for_customer_save is not None:
                        result.append("</ul></li>")
                    department_for_customer_save = o.department_for_customer
                    result.append("<li>{}<ul>".format(department_for_customer_save))
                result.append("<li>{}</li>".format(
                    o.get_long_name_with_producer(is_html=True)
                ))
            if department_for_customer_save is not None:
                result.append("</ul>")
        if result:
            return mark_safe("<ul>{}</ul>".format(EMPTY_STRING.join(result)))
        return EMPTY_STRING

    def get_full_status_display(self):
        from repanier.apps import REPANIER_SETTINGS_CLOSE_WO_SENDING
        refresh_status = [
            PERMANENCE_WAIT_FOR_PRE_OPEN,
            PERMANENCE_WAIT_FOR_OPEN,
            PERMANENCE_WAIT_FOR_CLOSED,
            PERMANENCE_WAIT_FOR_SEND,
            PERMANENCE_WAIT_FOR_INVOICED
        ]
        if not REPANIER_SETTINGS_CLOSE_WO_SENDING:
            refresh_status += [
                PERMANENCE_CLOSED
            ]
        need_to_refresh_status = self.status in refresh_status
        if self.with_delivery_point:
            status_list = []
            status = None
            status_counter = 0
            for delivery in DeliveryBoard.objects.filter(permanence_id=self.id).order_by("status", "id"):
                need_to_refresh_status |= delivery.status in refresh_status
                if status != delivery.status:
                    status = delivery.status
                    status_counter += 1
                    status_list.append("<b>{}</b>".format(delivery.get_status_display()))
                status_list.append("- {}".format(delivery.get_delivery_display(color=True)))
            message = "<br>".join(status_list)
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
                    <div class="wrap-text" id="id_get_status_{}">
                    <script type="text/javascript">
                        window.setTimeout(function(){{
                            django.jQuery.ajax({{
                                url: '{}',
                                cache: false,
                                async: false,
                                success: function (result) {{
                                    django.jQuery("#id_get_status_{}").html(result);
                                }}
                            }});
                        }}, 500);
                    </script>
                    {} {}</div>
                """.format(
                self.id, url, self.id, progress, message
            )

        else:
            msg_html = "<div class=\"wrap-text\">{}</div>".format(message)
        return mark_safe(msg_html)

    get_full_status_display.short_description = (_("Status"))
    get_full_status_display.allow_tags = True

    def get_permanence_display(self):
        short_name = self.safe_translation_getter(
            'short_name', any_language=True
        )
        if short_name:
            permanence_display = "{}".format(short_name)
        else:
            from repanier.apps import REPANIER_SETTINGS_PERMANENCE_ON_NAME
            permanence_display = "{}{}".format(
                REPANIER_SETTINGS_PERMANENCE_ON_NAME,
                self.permanence_date.strftime(settings.DJANGO_SETTINGS_DATE)
            )
        return permanence_display

    def get_permanence_admin_display(self):
        if self.status == PERMANENCE_INVOICED and self.total_selling_with_tax.amount != DECIMAL_ZERO:
            profit = self.total_selling_with_tax.amount - self.total_purchase_with_tax.amount
            # profit = self.total_selling_with_tax.amount - self.total_selling_vat.amount - self.total_purchase_with_tax.amount + self.total_purchase_vat.amount
            if profit != DECIMAL_ZERO:
                return "{}<br>{}<br>💶&nbsp;{}".format(
                    self.get_permanence_display(), self.total_selling_with_tax, RepanierMoney(profit)
                )
            return "{}<br>{}".format(
                self.get_permanence_display(), self.total_selling_with_tax)
        else:
            return self.get_permanence_display()

    get_permanence_admin_display.short_description = _("Offers")
    get_permanence_admin_display.allow_tags = True

    def get_permanence_customer_display(self, with_status=True):
        if with_status:
            if self.with_delivery_point:
                if self.status == PERMANENCE_OPENED:
                    deliveries_count = 0
                else:
                    deliveries_qs = DeliveryBoard.objects.filter(
                        permanence_id=self.id,
                        status=PERMANENCE_OPENED
                    ).order_by('?')
                    deliveries_count = deliveries_qs.count()
            else:
                deliveries_count = 0
            if deliveries_count == 0:
                if self.status != PERMANENCE_SEND:
                    return "{} - {}".format(self.get_permanence_display(), self.get_status_display())
                else:
                    return "{} - {}".format(self.get_permanence_display(), _('Orders closed'))
        return self.get_permanence_display()

    def __str__(self):
        return self.get_permanence_display()

    class Meta:
        verbose_name = _('Order')
        verbose_name_plural = _('Orders')

        index_together = [
            ["permanence_date"],
        ]


class PermanenceInPreparation(Permanence):
    class Meta:
        proxy = True
        verbose_name = _('Offer in preparation')
        verbose_name_plural = _('Offers in preparation')


class PermanenceDone(Permanence):
    class Meta:
        proxy = True
        verbose_name = _('Billing offer')
        verbose_name_plural = _('Billing offers')

