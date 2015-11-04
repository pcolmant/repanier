# -*- coding: utf-8
from __future__ import unicode_literals
from django.core.urlresolvers import reverse
from django.template import Template, Context as djangoContext
from django.utils.safestring import mark_safe
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _
from openpyxl.writer.excel import save_virtual_workbook
import repanier.apps
from repanier.models import Customer, CustomerInvoice
from repanier.models import Permanence
from repanier.models import PermanenceBoard
from repanier.models import Producer
from repanier.tools import *
from repanier.xlsx import xslx_order, xslx_stock


def email_order(permanence_id):
    translation.activate(settings.LANGUAGE_CODE)
    permanence = Permanence.objects.get(id=permanence_id)
    filename = ("%s - %s.xlsx" % (_("Order"), permanence)).encode('ascii', errors='replace').replace('?', '_')
    group_filename = ("%s - %s.xlsx" % (repanier.apps.REPANIER_SETTINGS_GROUP_NAME, filename)).encode('ascii', errors='replace').replace('?', '_')
    sender_email, sender_function, signature, cc_email_staff = get_signature(is_reply_to_order_email=True)

    board_composition = ''
    board_composition_and_description = ''
    for permanenceboard in PermanenceBoard.objects.filter(
            permanence=permanence_id).order_by(
            "permanence_role__tree_id",
            "permanence_role__lft"
    ):
        r = permanenceboard.permanence_role
        c = permanenceboard.customer
        if c is not None:
            if c.phone2 is not None:
                c_part = "%s, <b>%s</b>, <b>%s</b>" % (c.long_basket_name, c.phone1, c.phone2)
            else:
                c_part = "%s, <b>%s</b>" % (c.long_basket_name, c.phone1)
            member = "<b>%s</b> : %s, %s<br/>" % (r.short_name, c_part, c.user.email)
            board_composition += member
            board_composition_and_description += "%s%s<br/>" % (member, r.description)

    # Orders send to the preparation team
    group_wb = xslx_order.export_abstract(permanence=permanence, wb=None)
    if group_wb is not None:
        abstract_ws = group_wb.get_active_sheet()
    else:
        abstract_ws = None

    if group_wb is not None:
        # At least one order

        group_wb = xslx_order.export_customer_label(permanence, wb=group_wb)
        group_wb = xslx_order.export_preparation(permanence=permanence, wb=group_wb)
        group_wb = xslx_stock.export_stock(permanence=permanence, customer_price=True, wb=group_wb)
        group_wb = xslx_order.export_customer(permanence=permanence, wb=group_wb, deposit=True)
        group_wb = xslx_order.export_customer(permanence=permanence, wb=group_wb)

        to_email_board = []
        for permanenceboard in PermanenceBoard.objects.filter(
                permanence=permanence_id).order_by():
            if permanenceboard.customer:
                to_email_board.append(permanenceboard.customer.user.email)

        order_staff_mail = repanier.apps.REPANIER_SETTINGS_CONFIG.order_staff_mail
        template = Template(order_staff_mail)
        context = djangoContext({
            'permanence': mark_safe('<a href="http://%s%s">%s</a>' % (settings.ALLOWED_HOSTS[0], reverse('order_view', args=(permanence.id,)), permanence)),
            'board_composition': mark_safe(board_composition),
            'board_composition_and_description': mark_safe(board_composition_and_description),
            'signature': mark_safe('%s<br/>%s<br/>%s' % (signature, sender_function, repanier.apps.REPANIER_SETTINGS_GROUP_NAME))
        })
        html_content = template.render(context)
        email = EmailMultiAlternatives(
            "%s - %s - %s" % (_('Permanence preparation list'), permanence, repanier.apps.REPANIER_SETTINGS_GROUP_NAME),
            strip_tags(html_content),
            sender_email,
            to_email_board,
            cc=cc_email_staff
        )
        email.attach(group_filename,
                     save_virtual_workbook(group_wb),
                     'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        email.attach_alternative(html_content, "text/html")

        if not repanier.apps.REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_BOARD:
            email.to = cc_email_staff
            email.cc = []
            email.bcc = []
        send_email(email=email)


    # Orders send to our producers
    if repanier.apps.REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_PRODUCER:
        producer_set = Producer.objects.filter(
            permanence=permanence_id).order_by()
        for producer in producer_set:
            if producer.email.upper().find("NO-SPAM.WS") < 0:
                translation.activate(producer.language)
                long_profile_name = producer.long_profile_name if producer.long_profile_name is not None else producer.short_profile_name
                wb = xslx_order.export_producer_by_product(
                    permanence=permanence, producer=producer, wb=None)
                if wb is None:
                    order_empty = True
                    duplicate = False
                else:
                    order_empty = False
                    if not producer.manage_stock:
                        duplicate = True
                        wb = xslx_order.export_producer_by_customer(permanence=permanence, producer=producer, wb=wb)
                    else:
                        duplicate = False
                order_producer_mail = repanier.apps.REPANIER_SETTINGS_CONFIG.order_producer_mail
                template = Template(order_producer_mail)
                context = djangoContext({
                    'name': long_profile_name,
                    'long_profile_name': long_profile_name,
                    'order_empty': order_empty,
                    'duplicate': duplicate,
                    'permanence': mark_safe('<a href="http://%s%s">%s</a>' % (settings.ALLOWED_HOSTS[0], reverse('order_view', args=(permanence.id,)), permanence)),
                    'signature': mark_safe(
                        '%s<br/>%s<br/>%s' % (signature, sender_function, repanier.apps.REPANIER_SETTINGS_GROUP_NAME))
                })
                html_content = template.render(context)

                email = EmailMultiAlternatives(
                    "%s - %s - %s - %s" % (_('Order'), permanence, repanier.apps.REPANIER_SETTINGS_GROUP_NAME, long_profile_name),
                    strip_tags(html_content),
                    sender_email,
                    [producer.email],
                    cc=cc_email_staff
                )
                if repanier.apps.REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_PRODUCER and wb is not None:
                    if repanier.apps.REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_PRODUCER:
                        if abstract_ws is not None:
                            wb.add_sheet(abstract_ws, index=0)
                    email.attach(
                        filename,
                        save_virtual_workbook(wb),
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )

                email.attach_alternative(html_content, "text/html")
                send_email(email=email)

    # Orders send to our customers
    if repanier.apps.REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_CUSTOMER:
        customer_set = Customer.objects.filter(
            purchase__permanence=permanence_id, represent_this_buyinggroup=False).order_by().distinct()
        for customer in customer_set:
            wb = xslx_order.export_customer(permanence=permanence, customer=customer, wb=None)
            if wb is not None:
                translation.activate(customer.language)
                email_customer = [customer.user.email,]
                if customer.email2 is not None and len(customer.email2) > 0:
                    email_customer.append(customer.email2)
                order_amount = basket_amount(customer, permanence)
                customer_last_balance, customer_on_hold_movement, customer_payment_needed = payment_message(customer)
                long_basket_name = customer.long_basket_name if customer.long_basket_name is not None else customer.short_basket_name
                order_customer_mail = repanier.apps.REPANIER_SETTINGS_CONFIG.order_customer_mail
                template = Template(order_customer_mail)
                context = djangoContext({
                    'name': long_basket_name,
                    'long_basket_name': long_basket_name,
                    'basket_name': customer.short_basket_name,
                    'short_basket_name': customer.short_basket_name,
                    'permanence': mark_safe('<a href="http://%s%s">%s</a>' % (settings.ALLOWED_HOSTS[0], reverse('order_view', args=(permanence.id,)), permanence)),
                    'last_balance': mark_safe('<a href="http://%s%s">%s</a>' % (settings.ALLOWED_HOSTS[0], reverse('customer_invoice_view', args=(0,)), customer_last_balance)),
                    'order_amount': order_amount,
                    'on_hold_movement': mark_safe(customer_on_hold_movement),
                    'payment_needed': mark_safe(customer_payment_needed),
                    'delivery_point': customer.delivery_point,
                    'signature': mark_safe(
                        '%s<br/>%s<br/>%s' % (signature, sender_function, repanier.apps.REPANIER_SETTINGS_GROUP_NAME))
                })
                html_content = template.render(context)
                email = EmailMultiAlternatives(
                    "%s - %s - %s - %s" % (_('Order'), permanence, repanier.apps.REPANIER_SETTINGS_GROUP_NAME, long_basket_name),
                    strip_tags(html_content),
                    sender_email,
                    email_customer
                )
                if repanier.apps.REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_CUSTOMER:
                    if repanier.apps.REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_CUSTOMER:
                        if abstract_ws is not None:
                            wb.add_sheet(abstract_ws, index=0)
                    email.attach(filename,
                                 save_virtual_workbook(wb),
                                 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

                email.attach_alternative(html_content, "text/html")
                send_email(email=email)
