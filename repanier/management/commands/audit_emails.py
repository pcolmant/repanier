"""Audit the emails of the member accounts before the email only login.

The site moves toward signing in with the email address alone, and
later toward matching social accounts (Google, Microsoft) on the
verified email. Both need every ordering member to carry one real,
unique email address. This command walks the member accounts and
reports what stands in the way - without changing anything:

- members sharing one email address with another member,
- members without a usable email address (missing or without "@"),
- members whose username is not their email - the accounts still
  opened by name instead of by email,
and exits with a non zero status as long as one finding remains.
"""
from collections import defaultdict

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q

from repanier.models.customer import Customer


class Command(BaseCommand):
    help = "Audit the emails of the member accounts (read only)"

    def handle(self, *args, **options):
        customers = list(
            Customer.objects.filter(
                Q(user__is_active=True, is_active=True, may_order=True),
                represent_this_buyinggroup=False,
            )
            .select_related("user")
            .order_by("short_basket_name")
        )

        problems = 0

        emails = defaultdict(list)
        for customer in customers:
            email = (customer.user.email or "").strip().lower()
            if email:
                emails[email].append(customer)
        for email, sharing in sorted(emails.items()):
            if len(sharing) > 1:
                problems += 1
                self.stderr.write(
                    "Shared email {}: {}".format(
                        email,
                        ", ".join(c.short_basket_name for c in sharing),
                    )
                )

        for customer in customers:
            email = (customer.user.email or "").strip()
            if "@" not in email:
                problems += 1
                self.stderr.write(
                    "No usable email for {} (username {})".format(
                        customer.short_basket_name, customer.user.username
                    )
                )

        for customer in customers:
            email = (customer.user.email or "").strip().lower()
            username = (customer.user.username or "").strip().lower()
            if email and username != email:
                problems += 1
                self.stderr.write(
                    "Signs in by name, not by email: {} (username {}, email {})".format(
                        customer.short_basket_name, customer.user.username, email
                    )
                )

        group_accounts = sum(1 for c in customers if c.is_group)
        self.stdout.write(
            "{} member accounts audited ({} group accounts), {} findings.".format(
                len(customers), group_accounts, problems
            )
        )
        if customers and not problems:
            self.stdout.write("Every member account carries a unique email address.")
        if problems:
            raise SystemExit(1)
