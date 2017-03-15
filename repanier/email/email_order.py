# -*- coding: utf-8
from __future__ import unicode_literals

from django.core.mail import EmailMultiAlternatives
from django.core.urlresolvers import reverse
from django.template import Template, Context as TemplateContext
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _
from openpyxl.writer.excel import save_virtual_workbook

from repanier.models import Customer
from repanier.models import Permanence, Configuration, CustomerInvoice
from repanier.models import PermanenceBoard
from repanier.models import Producer, ProducerInvoice
from repanier.tools import *
from repanier.xlsx import xlsx_order, xlsx_stock


def email_order(permanence_id, all_producers=True, closed_deliveries_id=None, producers_id=None):
    from repanier.apps import REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_BOARD, \
        REPANIER_SETTINGS_GROUP_NAME, REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_PRODUCER, \
        REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_PRODUCER, \
        REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_CUSTOMER
    cur_language = translation.get_language()
    for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
        language_code = language["code"]
        translation.activate(language_code)
        permanence = Permanence.objects.get(id=permanence_id)
        config = Configuration.objects.get(id=DECIMAL_ONE)
        filename = "{0}-{1}.xlsx".format(
                        slugify(_("Order")),
                        slugify(permanence)
        )
        group_filename = "{0}-{1}.xlsx".format(
            slugify(REPANIER_SETTINGS_GROUP_NAME),
            slugify(filename)
        )
        sender_email, sender_function, signature, cc_email_staff = get_signature(is_reply_to_order_email=True)
        board_composition, board_composition_and_description = get_board_composition(permanence.id)

        # Orders send to the preparation team
        group_wb = xlsx_order.export_abstract(permanence=permanence, deliveries_id=closed_deliveries_id, wb=None)
        if group_wb is not None:
            abstract_ws = group_wb.get_active_sheet()
        else:
            abstract_ws = None

        if all_producers:
            if group_wb is not None:
                # At least one order

                group_wb = xlsx_order.export_customer_label(
                    permanence=permanence, deliveries_id=closed_deliveries_id, wb=group_wb
                )
                group_wb = xlsx_order.export_preparation(
                    permanence=permanence, deliveries_id=closed_deliveries_id, wb=group_wb
                )
                group_wb = xlsx_stock.export_permanence_stock(
                    permanence=permanence, customer_price=True, wb=group_wb
                )
                group_wb = xlsx_order.export_customer(
                    permanence=permanence, deliveries_id=closed_deliveries_id, deposit=True, wb=group_wb
                )
                group_wb = xlsx_order.export_customer(
                    permanence=permanence, deliveries_id=closed_deliveries_id, wb=group_wb
                )

                to_email_board = []
                for permanence_board in PermanenceBoard.objects.filter(
                        permanence=permanence.id).order_by('?'):
                    if permanence_board.customer:
                        to_email_board.append(permanence_board.customer.user.email)

                try:
                    order_staff_mail = config.order_staff_mail
                except TranslationDoesNotExist:
                    order_staff_mail = EMPTY_STRING
                # order_staff_mail_subject = "%s - %s - %s" % (
                #     _('Permanence preparation list'), permanence, REPANIER_SETTINGS_GROUP_NAME)
                order_staff_mail_subject = "%s - %s" % (REPANIER_SETTINGS_GROUP_NAME, permanence)

                template = Template(order_staff_mail)
                context = TemplateContext({
                    'permanence_link'                  : mark_safe('<a href="http://%s%s">%s</a>' % (
                        settings.ALLOWED_HOSTS[0], reverse('order_view', args=(permanence.id,)), permanence)),
                    'board_composition'                : mark_safe(board_composition),
                    'board_composition_and_description': mark_safe(board_composition_and_description),
                    'signature'                        : mark_safe(
                        '%s<br/>%s<br/>%s' % (signature, sender_function, REPANIER_SETTINGS_GROUP_NAME))
                })
                html_content = template.render(context)
                email = EmailMultiAlternatives(
                    order_staff_mail_subject,
                    strip_tags(html_content),
                    from_email=sender_email,
                    to=to_email_board,
                    cc=cc_email_staff
                )
                if group_wb is not None:
                    email.attach(group_filename,
                                 save_virtual_workbook(group_wb),
                                 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                email.attach_alternative(html_content, "text/html")

                if not REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_BOARD:
                    email.to = cc_email_staff
                    email.cc = []
                    email.bcc = []
                send_email(email=email)

        # Orders send to our producers
        if REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_PRODUCER:
            producer_set = Producer.objects.filter(
                permanence=permanence.id,
                language=language_code,
            ).order_by('?')
            if producers_id is not None:
                # Do not send order twice
                # all_producers is True if we are sending the order to the last group of selected producers
                producer_set = producer_set.filter(id__in=producers_id)
            for producer in producer_set:
                long_profile_name = producer.long_profile_name if producer.long_profile_name is not None else producer.short_profile_name
                wb = xlsx_order.export_producer_by_product(permanence=permanence, producer=producer, wb=None)
                if wb is None:
                    order_empty = True
                    duplicate = False
                else:
                    order_empty = False
                    if not producer.manage_replenishment:
                        duplicate = True
                        wb = xlsx_order.export_producer_by_customer(
                            permanence=permanence, producer=producer, wb=wb)
                    else:
                        duplicate = False
                try:
                    order_producer_mail = config.order_producer_mail
                except TranslationDoesNotExist:
                    order_producer_mail = EMPTY_STRING
                # order_producer_mail_subject = "%s - %s - %s" % (
                #     _('Permanence preparation list'), permanence, REPANIER_SETTINGS_GROUP_NAME)
                order_producer_mail_subject = "%s - %s" % (REPANIER_SETTINGS_GROUP_NAME, permanence)

                template = Template(order_producer_mail)
                context = TemplateContext({
                    'name'             : long_profile_name,
                    'long_profile_name': long_profile_name,
                    'order_empty'      : order_empty,
                    'duplicate'        : duplicate,
                    'permanence_link'  : mark_safe('<a href="http://%s%s">%s</a>' % (
                        settings.ALLOWED_HOSTS[0], reverse('order_view', args=(permanence.id,)), permanence)),
                    'signature'        : mark_safe(
                        '%s<br/>%s<br/>%s' % (signature, sender_function, REPANIER_SETTINGS_GROUP_NAME))
                })
                html_content = template.render(context)

                producer_invoice = models.ProducerInvoice.objects.filter(
                    producer_id=producer.id, permanence_id=permanence.id
                ).only("total_price_with_tax").order_by('?').first()
                if producer_invoice is not None \
                        and producer_invoice.total_price_with_tax < producer.minimum_order_value:
                    to = cc_email_staff
                    html_content = \
                        order_producer_mail_subject + '<br/><br/>' + html_content
                    cc = []
                    order_producer_mail_subject = _(
                        '/!\ Mail not send to our producer %s because the minimum order value has not been reached.') % long_profile_name
                else:
                    to_email_producer = []
                    if producer.email:
                        to_email_producer.append(producer.email)
                    if producer.email2:
                        to_email_producer.append(producer.email2)
                    if producer.email3:
                        to_email_producer.append(producer.email3)
                    cc = cc_email_staff
                email = EmailMultiAlternatives(
                    order_producer_mail_subject,
                    strip_tags(html_content),
                    from_email=sender_email,
                    to=to_email_producer,
                    cc=cc
                )
                if REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_PRODUCER and wb is not None:
                    if REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_PRODUCER:
                        if abstract_ws is not None:
                            wb.add_sheet(abstract_ws, index=0)
                    email.attach(
                        filename,
                        save_virtual_workbook(wb),
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )

                email.attach_alternative(html_content, "text/html")
                send_email(email=email)

        if all_producers:
            # Orders send to our customers only if they don't have already received it
            # ==> customerinvoice__is_order_confirm_send=False
            #     customerinvoice__permanence_id=permanence.id
            if REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_CUSTOMER:
                all_producers_closed = not (ProducerInvoice.objects.filter(
                    permanence_id=permanence_id,
                    status=PERMANENCE_OPENED
                ).order_by('?').exists())
                if all_producers_closed:
                    if closed_deliveries_id is None:
                        customer_set = Customer.objects.filter(
                            represent_this_buyinggroup=False,
                            customerinvoice__is_order_confirm_send=False,
                            customerinvoice__permanence_id=permanence.id,
                            language=language_code
                        ).order_by('?')
                    else:
                        customer_set = Customer.objects.filter(
                            represent_this_buyinggroup=False,
                            customerinvoice__is_order_confirm_send=False,
                            customerinvoice__permanence_id=permanence.id,
                            customerinvoice__delivery_id__in=closed_deliveries_id,
                            language=language_code
                        ).order_by('?')
                    for customer in customer_set:
                        export_order_2_1_customer(
                            customer, filename, permanence, sender_email,
                            sender_function, signature, abstract_ws)
                        # confirm_customer_invoice(permanence_id, customer.id)
                        customer_invoice = CustomerInvoice.objects.filter(
                            customer_id=customer.id,
                            permanence_id=permanence_id
                        ).order_by('?').first()
                        customer_invoice.confirm_order()
                        customer_invoice.save()
    translation.activate(cur_language)


def export_order_2_1_customer(customer, filename, permanence, sender_email, sender_function, signature,
                              abstract_ws=None, cancel_order=False):
    from repanier.apps import REPANIER_SETTINGS_SEND_CANCEL_ORDER_MAIL_TO_CUSTOMER, \
        REPANIER_SETTINGS_GROUP_NAME, REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS, \
        REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_CUSTOMER, \
        REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_CUSTOMER
    config = Configuration.objects.get(id=DECIMAL_ONE)
    if (cancel_order and REPANIER_SETTINGS_SEND_CANCEL_ORDER_MAIL_TO_CUSTOMER) \
            or REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_CUSTOMER:
        customer_invoice = CustomerInvoice.objects.filter(permanence_id=permanence.id,
                                                          customer_id=customer.id).order_by('?').first()
        if customer_invoice is not None:
            wb = xlsx_order.export_customer(permanence=permanence, customer=customer, xlsx_formula=False, wb=None)
            if wb is not None:

                to_email_customer = [customer.user.email]
                if cancel_order or REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
                    to_email_customer.append(sender_email)
                if customer.email2:
                    to_email_customer.append(customer.email2)
                if customer_invoice.delivery is not None:
                    delivery_point = customer_invoice.delivery
                    # if delivery_point.delivery_point.customer_responsible is not None:
                    #     customer_responsible = delivery_point.delivery_point.customer_responsible
                    #     if customer_responsible.id != customer.id:
                    #         to_email_customer.append(customer_responsible.user.email)
                    #         if customer_responsible.email2:
                    #             to_email_customer.append(customer_responsible.email2)
                else:
                    delivery_point = EMPTY_STRING
                customer_last_balance, customer_on_hold_movement, customer_payment_needed, customer_order_amount = payment_message(
                    customer, permanence)
                long_basket_name = customer.long_basket_name if customer.long_basket_name is not None else customer.short_basket_name
                if cancel_order:
                    try:
                        order_customer_mail = config.cancel_order_customer_mail
                    except TranslationDoesNotExist:
                        order_customer_mail = EMPTY_STRING
                    order_customer_mail_subject = "%s - %s - %s" % (
                        _('/!\ Order cancelled'), REPANIER_SETTINGS_GROUP_NAME, permanence)
                else:
                    try:
                        order_customer_mail = config.order_customer_mail
                    except TranslationDoesNotExist:
                        order_customer_mail = EMPTY_STRING
                    # order_customer_mail_subject = "%s - %s - %s" % (
                    #     _('Order'), REPANIER_SETTINGS_GROUP_NAME, permanence)
                    order_customer_mail_subject = "%s - %s" % (REPANIER_SETTINGS_GROUP_NAME, permanence)

                template = Template(order_customer_mail)
                context = TemplateContext({
                    'name'             : long_basket_name,
                    'long_basket_name' : long_basket_name,
                    'basket_name'      : customer.short_basket_name,
                    'short_basket_name': customer.short_basket_name,
                    'permanence_link'  : mark_safe('<a href="http://%s%s">%s</a>' % (
                        settings.ALLOWED_HOSTS[0], reverse('order_view', args=(permanence.id,)), permanence)),
                    'last_balance_link': mark_safe('<a href="http://%s%s">%s</a>' % (
                        settings.ALLOWED_HOSTS[0], reverse('customer_invoice_view', args=(0,)), customer_last_balance)),
                    'last_balance'     : mark_safe(customer_last_balance),
                    'order_amount'     : mark_safe(customer_order_amount),
                    'on_hold_movement' : mark_safe(customer_on_hold_movement),
                    'payment_needed'   : mark_safe(customer_payment_needed),
                    'delivery_point'   : delivery_point,
                    'signature'        : mark_safe(
                        '%s<br/>%s<br/>%s' % (signature, sender_function, REPANIER_SETTINGS_GROUP_NAME))
                })
                html_content = template.render(context)
                email = EmailMultiAlternatives(
                    order_customer_mail_subject,
                    strip_tags(html_content),
                    from_email=sender_email,
                    to=to_email_customer
                )
                if not cancel_order and REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_CUSTOMER:
                    if abstract_ws is not None:
                        wb.add_sheet(abstract_ws, index=0)
                email.attach(filename,
                             save_virtual_workbook(wb),
                             'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

                email.attach_alternative(html_content, "text/html")
                send_email(email=email)
