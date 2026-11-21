"""Normalize the member usernames to their e-mail address.

The sign in reads the e-mail address only: a username inherited from
the CSV import (the short name of the member) does not open any door,
it only left the accounts in two shapes - the admin created them with
username == e-mail, the import with username == short name.

This command aligns every ordering member on the e-mail shape, which
is the shape the customer form already produces:

- without --apply, a dry run: the command reports what it would
  change and touches nothing;
- with --apply, the username of each ordering member whose usable
  e-mail differs from his username becomes that e-mail, lowercased
  and stripped;
- an account without usable e-mail is reported and skipped;
- a collision (another account already carrying that username) is
  reported and skipped - the collision never breaks the run;
- the site accounts, the staff and the inactive members stay out of
  the scope, exactly like in audit_emails.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q

from repanier.models.customer import Customer


class Command(BaseCommand):
    help = "Normalize the member usernames to their e-mail address"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Change the usernames. Without it, a dry run reports only.",
        )

    def handle(self, *args, **options):
        user_model = get_user_model()
        apply = options["apply"]

        customers = list(
            Customer.objects.filter(
                Q(user__is_active=True, is_active=True, may_order=True),
                represent_this_buyinggroup=False,
            )
            .select_related("user")
            .order_by("short_basket_name")
        )

        to_change = []
        already_email = 0
        without_email = []
        collisions = []

        for customer in customers:
            email = (customer.user.email or "").strip().lower()
            username = (customer.user.username or "").strip()
            if not email or "@" not in email:
                without_email.append(customer)
                continue
            if username.lower() == email:
                already_email += 1
                continue
            if (
                user_model.objects.filter(username__iexact=email)
                .exclude(id=customer.user_id)
                .exists()
            ):
                collisions.append(customer)
                continue
            to_change.append((customer, email))

        for customer, email in to_change:
            mode = "normalized"
            if apply:
                user_model.objects.filter(id=customer.user_id).update(
                    username=email
                )
                mode = "normalized (applied)"
            self.stdout.write(
                "{}: {} -> {}".format(
                    mode, customer.short_basket_name, email
                )
            )
        for customer in without_email:
            self.stderr.write(
                "skipped, no usable e-mail: {} (username {})".format(
                    customer.short_basket_name, customer.user.username
                )
            )
        for customer in collisions:
            self.stderr.write(
                "skipped, another account carries that username: {} ({})".format(
                    customer.short_basket_name, customer.user.email.strip().lower()
                )
            )

        self.stdout.write(
            "{} member accounts scanned, {} to normalize, {} already e-mail, "
            "{} skipped, {} collisions.{}".format(
                len(customers),
                len(to_change),
                already_email,
                len(without_email) + len(collisions),
                len(collisions),
                "" if apply else " Dry run - run again with --apply to change.",
            )
        )
        if not apply and (to_change or without_email or collisions):
            raise SystemExit(1)
