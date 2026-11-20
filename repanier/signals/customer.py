from django.conf import settings
from django.db.models import Q
from django.db.models.signals import post_delete, post_save, pre_save
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
    update_fields = kwargs.get("update_fields")
    if customer.pk and update_fields is None and not customer.is_anonymized:
        # A customer instance loaded before an address change or webhook can be stale.
        stored = Customer.objects.using(kwargs["using"]).filter(pk=customer.pk).values(
            "user_id", "user__email", "valid_email"
        ).first()
        if stored:
            if stored["user_id"] != customer.user_id and (
                stored["user__email"] != customer.user.email
            ):
                customer.valid_email = None
            else:
                customer.valid_email = stored["valid_email"]


@receiver(pre_save, sender=settings.AUTH_USER_MODEL)
def detect_customer_email_change(sender, instance, using, update_fields, raw, **kwargs):
    instance._repanier_email_changed = False
    if raw or instance.pk is None or (update_fields is not None and "email" not in update_fields):
        return
    previous_email = sender.objects.using(using).filter(pk=instance.pk).values_list(
        "email", flat=True
    ).first()
    instance._repanier_email_changed = previous_email is not None and previous_email != instance.email


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def reset_customer_email_validity(sender, instance, using, **kwargs):
    if getattr(instance, "_repanier_email_changed", False):
        Customer.objects.using(using).filter(user_id=instance.pk).update(valid_email=None)


@receiver(post_delete, sender=Customer)
def customer_post_delete(sender, **kwargs):
    customer = kwargs["instance"]
    user = customer.user
    if user is not None and user.id is not None:
        user.delete()
