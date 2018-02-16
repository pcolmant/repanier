# -*- coding: utf-8

from django.core.urlresolvers import reverse
from django.template import Template, Context as TemplateContext
from django.utils.translation import ugettext_lazy as _
from openpyxl.writer.excel import save_virtual_workbook

from repanier.models.customer import Customer
from repanier.models.deliveryboard import DeliveryBoard
from repanier.models.invoice import CustomerInvoice, ProducerInvoice
from repanier.models.permanence import Permanence
from repanier.models.permanenceboard import PermanenceBoard
from repanier.models.producer import Producer
from repanier.models.staff import Staff
from repanier.tools import *
from repanier.xlsx.xlsx_order import generate_customer_xlsx, generate_producer_xlsx


def email_order(permanence_id, everything=True, producers_id=(), deliveries_id=()):
    from repanier.apps import REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_BOARD, \
        REPANIER_SETTINGS_GROUP_NAME, \
        REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_PRODUCER, \
        REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS, \
        REPANIER_SETTINGS_CONFIG
    cur_language = translation.get_language()
    for language in settings.PARLER_LANGUAGES[settings.SITE_ID]:
        language_code = language["code"]
        translation.activate(language_code)
        permanence = Permanence.objects.get(id=permanence_id)
        config = REPANIER_SETTINGS_CONFIG
        filename = "{0}-{1}.xlsx".format(
            _("Order"),
            permanence
        )
        group_filename = "{0}-{1}.xlsx".format(
            REPANIER_SETTINGS_GROUP_NAME,
            filename
        )
        staff = Staff.get_or_create_order_responsible()

        if len(deliveries_id) > 0:
            # if closed deliveries_id is not empty list and not "None" then all_producers should be True
            everything = True
            for delivery_id in deliveries_id:
                # Send a recap of the orders to the responsible
                export_order_2_1_group(
                    config, delivery_id, filename,
                    permanence,
                    staff
                )

        if not everything:
            abstract_ws = None
        else:
            # Orders send to the preparation team
            wb, abstract_ws = generate_customer_xlsx(permanence, deliveries_id=deliveries_id)
            if wb is not None:
                # At least one order
                to_email_board = []
                for permanence_board in PermanenceBoard.objects.filter(
                        permanence_id=permanence.id).order_by('?'):
                    if permanence_board.customer:
                        to_email_board.append(permanence_board.customer.user.email)

                order_staff_mail = config.safe_translation_getter(
                    'order_staff_mail', any_language=True, default=EMPTY_STRING
                )
                order_staff_mail_subject = "{} - {}".format(REPANIER_SETTINGS_GROUP_NAME, permanence)

                board_composition, board_composition_and_description = get_board_composition(permanence.id)

                template = Template(order_staff_mail)
                context = TemplateContext({
                    'permanence_link': mark_safe("<a href=\"https://{}{}\">{}</a>".format(
                        settings.ALLOWED_HOSTS[0], reverse('order_view', args=(permanence.id,)), permanence)),
                    'board_composition': mark_safe(board_composition),
                    'board_composition_and_description': mark_safe(board_composition_and_description),
                    'signature': staff.get_html_signature
                })
                html_content = template.render(context)
                if REPANIER_SETTINGS_SEND_ORDER_MAIL_TO_BOARD:
                    email = RepanierEmail(
                        subject=order_staff_mail_subject,
                        html_content=html_content,
                        from_email=staff.get_from_email,
                        to=to_email_board,
                        cc=staff.get_to_email,
                        reply_to=staff.get_reply_to_email
                    )
                else:
                    email = RepanierEmail(
                        subject=order_staff_mail_subject,
                        html_content=html_content,
                        from_email=staff.get_from_email,
                        to=staff.get_to_email,
                        reply_to=staff.get_reply_to_email
                    )
                email.attach(group_filename,
                             save_virtual_workbook(wb),
                             'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                email.send_email()

        # Orders send to our producers
        producer_set = Producer.objects.filter(
            permanence=permanence,
            language=language_code,
        ).order_by('?')
        if len(producers_id) > 0:
            producer_set = producer_set.filter(id__in=producers_id)
        for producer in producer_set:
            long_profile_name = producer.long_profile_name if producer.long_profile_name is not None else producer.short_profile_name
            wb = generate_producer_xlsx(permanence=permanence, producer=producer, wb=None)

            order_producer_mail = config.safe_translation_getter(
                'order_producer_mail', any_language=True, default=EMPTY_STRING
            )
            order_producer_mail_subject = "{} - {}".format(REPANIER_SETTINGS_GROUP_NAME, permanence)

            template = Template(order_producer_mail)
            context = TemplateContext({
                'name': long_profile_name,
                'long_profile_name': long_profile_name,
                'order_empty': wb is None,
                'duplicate': not (wb is None or producer.manage_replenishment),
                'permanence_link': mark_safe("<a href=\"https://{}{}\">{}</a>".format(
                    settings.ALLOWED_HOSTS[0], reverse('order_view', args=(permanence.id,)), permanence)),
                'signature': staff.get_html_signature
            })
            html_content = template.render(context)

            producer_invoice = ProducerInvoice.objects.filter(
                producer_id=producer.id, permanence_id=permanence.id
            ).only("total_price_with_tax").order_by('?').first()
            if producer_invoice is not None \
                    and producer_invoice.total_price_with_tax < producer.minimum_order_value:
                to_email_producer = []
                html_content = "{}<br><br>{}".format(
                    order_producer_mail_subject, html_content
                )
                order_producer_mail_subject = _(
                    '⚠ Mail not send to our producer {} because the minimum order value has not been reached.').format(
                    long_profile_name)
            else:
                to_email_producer = []
                if producer.email:
                    to_email_producer.append(producer.email)
                if producer.email2:
                    to_email_producer.append(producer.email2)
                if producer.email3:
                    to_email_producer.append(producer.email3)
            email = RepanierEmail(
                subject=order_producer_mail_subject,
                html_content=html_content,
                from_email=staff.get_from_email,
                to=to_email_producer,
                cc=staff.get_to_email,
                reply_to=staff.get_reply_to_email
            )
            if wb is not None:
                if REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_PRODUCER:
                    if abstract_ws is not None:
                        wb.add_sheet(abstract_ws, index=0)
                email.attach(
                    filename,
                    save_virtual_workbook(wb),
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )

            email.send_email()

        if everything:
            # Orders send to our customers only if they don't have already received it
            # ==> customerinvoice__is_order_confirm_send=False
            #     customerinvoice__permanence_id=permanence.id
            if not REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
                # REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS -> Do not send cancelled orders
                customer_set = Customer.objects.filter(
                    represent_this_buyinggroup=False,
                    customerinvoice__is_order_confirm_send=False,
                    customerinvoice__permanence_id=permanence.id,
                    language=language_code
                ).order_by('?')
                if len(deliveries_id) > 0:
                    customer_set = customer_set.filter(
                        customerinvoice__delivery_id__in=deliveries_id,
                    )
                for customer in customer_set:
                    export_order_2_1_customer(
                        customer, filename, permanence,
                        staff,
                        abstract_ws
                    )
                    # confirm_customer_invoice(permanence_id, customer.id)
                    customer_invoice = CustomerInvoice.objects.filter(
                        customer_id=customer.id,
                        permanence_id=permanence_id
                    ).order_by('?').first()
                    customer_invoice.confirm_order()
                    customer_invoice.save()
    translation.activate(cur_language)


def export_order_2_1_group(config, delivery_id, filename, permanence, staff):
    delivery_board = DeliveryBoard.objects.filter(
        id=delivery_id
    ).exclude(
        delivery_point__customer_responsible=None
    ).order_by('?').first()
    if delivery_board is None:
        return

    from repanier.apps import REPANIER_SETTINGS_GROUP_NAME
    delivery_point = delivery_board.delivery_point
    customer_responsible = delivery_point.customer_responsible

    wb = generate_customer_xlsx(permanence=permanence, deliveries_id=[delivery_id], group=True)[0]
    if wb is not None:

        order_customer_mail = config.safe_translation_getter(
            'order_customer_mail', any_language=True, default=EMPTY_STRING
        )
        order_customer_mail_subject = "{} - {}".format(REPANIER_SETTINGS_GROUP_NAME, permanence)

        to_email_customer = [customer_responsible.user.email]
        if customer_responsible.email2:
            to_email_customer.append(customer_responsible.email2)

        long_basket_name = customer_responsible.long_basket_name or str(customer_responsible)

        template = Template(order_customer_mail)
        context = TemplateContext({
            'name': long_basket_name,
            'long_basket_name': long_basket_name,  # deprecated
            'basket_name': str(customer_responsible),
            'short_basket_name': str(customer_responsible),  # deprecated
            'permanence_link': mark_safe("<a href=\"https://{}{}\">{}</a>".format(
                settings.ALLOWED_HOSTS[0], reverse('order_view', args=(permanence.id,)), permanence)),
            'last_balance_link': mark_safe("<a href=\"https://{}{}\">{}</a>".format(
                settings.ALLOWED_HOSTS[0], reverse('customer_invoice_view', args=(0,)), _("Group invoices"))),
            'last_balance': EMPTY_STRING,
            'order_amount': EMPTY_STRING,
            'on_hold_movement': EMPTY_STRING,
            'payment_needed': EMPTY_STRING,
            'delivery_point': delivery_point,
            'signature': staff.get_html_signature
        })
        html_content = template.render(context)
        email = RepanierEmail(
            subject=order_customer_mail_subject,
            html_content=html_content,
            from_email=staff.get_from_email,
            to=to_email_customer,
            cc=staff.get_to_email,
            reply_to=staff.get_reply_to
        )
        email.attach(filename,
                     save_virtual_workbook(wb),
                     'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        email.send_email()


def export_order_2_1_customer(customer, filename, permanence, staff,
                              abstract_ws=None, cancel_order=False):
    from repanier.apps import \
        REPANIER_SETTINGS_GROUP_NAME, REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS, \
        REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_CUSTOMER, \
        REPANIER_SETTINGS_CONFIG

    config = REPANIER_SETTINGS_CONFIG
    customer_invoice = CustomerInvoice.objects.filter(
        permanence_id=permanence.id,
        customer_id=customer.id
    ).order_by('?').first()
    if customer_invoice is not None:
        wb = generate_customer_xlsx(permanence=permanence, customer=customer)[0]
        if wb is not None:
            if cancel_order or REPANIER_SETTINGS_CUSTOMERS_MUST_CONFIRM_ORDERS:
                cc = staff.get_to_email
            else:
                cc = []
            to_email_customer = [customer.user.email]
            if customer.email2:
                to_email_customer.append(customer.email2)
            if customer_invoice.delivery is not None:
                delivery_point = customer_invoice.delivery
                if delivery_point.delivery_point.inform_customer_responsible and delivery_point.delivery_point.customer_responsible is not None:
                    customer_responsible = delivery_point.delivery_point.customer_responsible
                    if customer_responsible.id != customer.id:
                        to_email_customer.append(customer_responsible.user.email)
                        if customer_responsible.email2:
                            to_email_customer.append(customer_responsible.email2)
            else:
                delivery_point = EMPTY_STRING
            customer_last_balance, customer_on_hold_movement, customer_payment_needed, customer_order_amount = payment_message(
                customer, permanence)
            long_basket_name = customer.long_basket_name if customer.long_basket_name is not None else customer.short_basket_name
            if cancel_order:
                order_customer_mail = config.safe_translation_getter(
                    'cancel_order_customer_mail', any_language=True, default=EMPTY_STRING
                )
                order_customer_mail_subject = "{} - {} - {}".format(
                    _('⚠ Order cancelled'), REPANIER_SETTINGS_GROUP_NAME, permanence)
            else:
                order_customer_mail = config.safe_translation_getter(
                    'order_customer_mail', any_language=True, default=EMPTY_STRING
                )
                order_customer_mail_subject = "{} - {}".format(REPANIER_SETTINGS_GROUP_NAME, permanence)

            template = Template(order_customer_mail)
            context = TemplateContext({
                'name': long_basket_name,
                'long_basket_name': long_basket_name,
                'basket_name': customer.short_basket_name,
                'short_basket_name': customer.short_basket_name,
                'permanence_link': mark_safe("<a href=\"https://{}{}\">{}</a>".format(
                    settings.ALLOWED_HOSTS[0], reverse('order_view', args=(permanence.id,)), permanence)),
                'last_balance_link': mark_safe("<a href=\"https://{}{}\">{}</a>".format(
                    settings.ALLOWED_HOSTS[0], reverse('customer_invoice_view', args=(0,)), customer_last_balance)),
                'last_balance': mark_safe(customer_last_balance),
                'order_amount': mark_safe(customer_order_amount),
                'on_hold_movement': customer_on_hold_movement,
                'payment_needed': mark_safe(customer_payment_needed),
                'delivery_point': delivery_point,
                'signature': staff.get_html_signature
            })
            html_content = template.render(context)
            email = RepanierEmail(
                subject=order_customer_mail_subject,
                html_content=html_content,
                from_email=staff.get_from_email,
                to=to_email_customer,
                cc=cc,
                reply_to=staff.get_reply_to_email,
                show_customer_may_unsubscribe=False,
                send_even_if_unsubscribed=True
            )
            if not cancel_order and REPANIER_SETTINGS_SEND_ABSTRACT_ORDER_MAIL_TO_CUSTOMER:
                if abstract_ws is not None:
                    wb.add_sheet(abstract_ws, index=0)
            email.attach(filename,
                         save_virtual_workbook(wb),
                         'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

            email.send_email()
