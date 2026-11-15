"""Audit the passport members of this site against their home site.

The members placed here by the Repanier passport - in a mirror group
which accepts the arrivals - keep their home site behind their group
name. This command asks every home site, server to server and signed
with the family key, whether each of those members still belongs to
it. A home site which answers no means the member left his home -
the passport never meant to keep the doors open forever - but the
audit NEVER acts on its own: read only, it reports to the
coordination by mail, and the coordination decides. A home site
which stays silent is never a departure: the network, a deployment
lag or a wrong key all look the same, and the report says so.

Run it from the crontab of the server, once a night:

    30 3 * * * cd ~/_X_prd_site/_X_prd_site && \\
        .venv/bin/python manage.py passport_audit >> ~/_passport_audit.log 2>&1

Nobody is modified. Only read.
"""
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from repanier.email.email import RepanierEmail
from repanier.models.customer import Customer
from repanier.passport_network import verify_passport_member

PASSPORT_AUDIT_PAUSE = 0.1  # seconds between two questions to a home site


class Command(BaseCommand):
    help = (
        "Ask the home sites whether the passport members placed here still "
        "belong to them. Read only: findings go to the coordination by mail."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            help="Audit a single member instead of every passport member.",
        )

    def handle(self, *args, **options):
        members = (
            Customer.objects.filter(
                is_group=False,
                is_active=True,
                user__email__isnull=False,
                group__is_group=True,
                group__is_active=True,
                group__accepts_passport_members=True,
            )
            .exclude(group__short_basket_name__isnull=True)
            .order_by("group__short_basket_name", "short_basket_name")
        )
        if options["email"]:
            members = members.filter(user__email__iexact=options["email"])
        self.stdout.write("repanier passport audit : {} members".format(members.count()))
        still_home = []
        gone_home = []
        silent = []
        for member in members:
            email = (member.user.email or "").strip().lower()
            home = (member.group.short_basket_name or "").strip().lower()
            if not email or not home or "|" in email:
                continue
            answer = verify_passport_member(home, email)
            if answer is True:
                still_home.append((home, member.short_basket_name, email))
            elif answer is False:
                gone_home.append((home, member.short_basket_name, email))
            else:
                silent.append((home, member.short_basket_name, email))
            time.sleep(PASSPORT_AUDIT_PAUSE)
        self.stdout.write(
            "repanier passport audit : {} still at home, {} gone, {} silent".format(
                len(still_home), len(gone_home), len(silent)
            )
        )
        for home, short_name, email in gone_home:
            self.stdout.write(
                "  gone  : [{}] {} ({})".format(home, short_name, email)
            )
        for home, short_name, email in silent:
            self.stdout.write(
                "  silent: [{}] {} ({})".format(home, short_name, email)
            )
        if gone_home or silent:
            self._report_by_mail(gone_home, silent)
        else:
            self.stdout.write(
                "repanier passport audit : nothing to report, no mail sent."
            )

    def _report_by_mail(self, gone_home, silent):
        # The coordination receives the findings once a night, never
        # more: the mail carries the decision, not the action.
        lines = []
        if gone_home:
            lines.append("Members their home site does not know anymore:")
            for home, short_name, email in gone_home:
                lines.append("  [{}] {} ({})".format(home, short_name, email))
            lines.append("")
        if silent:
            lines.append("Members their home site did not answer about:")
            for home, short_name, email in silent:
                lines.append("  [{}] {} ({})".format(home, short_name, email))
            lines.append("")
        lines.append(
            "This report is read only: the audit never touches an account. "
            "The coordination decides what to do."
        )
        body = "\n".join(lines)
        email = RepanierEmail(
            subject="[{}] Repanier passport audit".format(
                settings.REPANIER_SETTINGS_GROUP_NAME
            ),
            html_body="<pre>{}</pre>".format(body),
            to=[settings.ADMIN_EMAIL],
            show_customer_may_unsubscribe=False,
        )
        email.send_email()
        self.stdout.write(
            "repanier passport audit : report sent to {}".format(settings.ADMIN_EMAIL)
        )
