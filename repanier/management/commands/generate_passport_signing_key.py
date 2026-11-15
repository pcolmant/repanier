"""Generate a signing key for the Repanier passport.

The passport verifies its tokens with
REPANIER_SETTINGS_PASSPORT_SIGNING_KEY, the same value in the ini of
every site of the repanier.be family. The key must come from a
cryptographic generator - not from a human memory or a reused
password: whoever holds it opens the member sessions on the whole
family. This command prints one, ready to paste in the ini files:

    ./manage.py generate_passport_signing_key

The command touches nothing: it only prints. Paste the SAME value in
the [REPANIER_SETTINGS] section of every family site, leave it empty
on the sites living on their own domain (colibera.be,
commande.lebuisson.be, commande.coopeco-supermarche.be) - they carry
no passport anyway.
"""
import secrets

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Generate a Repanier passport signing key, ready to paste in the ini files."

    def handle(self, *args, **options):
        # token_urlsafe(48) -> 64 url-safe characters, 384 bits of
        # entropy: comfortable for a family wide signing key.
        key = secrets.token_urlsafe(48)
        self.stdout.write("REPANIER_SETTINGS_PASSPORT_SIGNING_KEY={}".format(key))
        self.stdout.write(
            "Paste the SAME value in the ini of every site of the repanier.be "
            "family ([REPANIER_SETTINGS] section)."
        )
