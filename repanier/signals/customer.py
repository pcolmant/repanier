from django.db.models import Q
from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver

from repanier.const import EMPTY_STRING, DECIMAL_ZERO, DECIMAL_ONE
from repanier.models import Customer


@receiver(pre_save, sender=Customer)
def customer_pre_save(sender, **kwargs):
    customer = kwargs["instance"]

    if customer.represent_this_buyinggroup:
        # The buying group may not be de activated
        customer.is_active = True
        customer.is_group = False
    if customer.bank_account1:
        # Prohibit to have two customers with same bank account
        other_bank_account1 = Customer.objects.filter(
            Q(bank_account1=customer.bank_account1)
            | Q(bank_account2=customer.bank_account1)
        )
        if customer.id is not None:
            other_bank_account1 = other_bank_account1.exclude(id=customer.id)
        if other_bank_account1.exists():
            customer.bank_account1 = EMPTY_STRING
    if customer.bank_account2:
        # Prohibit to have two customers with same bank account
        other_bank_account2 = Customer.objects.filter(
            Q(bank_account1=customer.bank_account2)
            | Q(bank_account2=customer.bank_account2)
        )
        if customer.id is not None:
            other_bank_account2 = other_bank_account2.exclude(id=customer.id)
        if other_bank_account2.exists():
            customer.bank_account2 = EMPTY_STRING
    if not customer.is_active:
        customer.may_order = False
    if customer.price_list_multiplier <= DECIMAL_ZERO:
        customer.price_list_multiplier = DECIMAL_ONE
    customer.city = "{}".format(customer.city).upper()
    customer.login_attempt_counter = DECIMAL_ZERO
    customer.valid_email = None


@receiver(post_delete, sender=Customer)
def customer_post_delete(sender, **kwargs):
    customer = kwargs["instance"]
    user = customer.user
    if user is not None and user.id is not None:
        user.delete()
