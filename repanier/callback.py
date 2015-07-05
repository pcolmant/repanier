# -*- coding: utf-8
from __future__ import unicode_literals
from const import DECIMAL_ZERO


def pasword_reset_callback(sender, user, request, **kwargs):
    if not user.is_superuser:
        from models import Staff, Customer

        staff = Staff.objects.filter(
            user=user, is_active=True
        ).order_by().first()
        if staff is not None:
            customer = staff.customer_responsible
        else:
            customer = Customer.objects.filter(
                user=user, is_active=True
            ).order_by().first()
        Customer.objects.filter(id=customer.id).update(
            login_attempt_counter=DECIMAL_ZERO
        )
