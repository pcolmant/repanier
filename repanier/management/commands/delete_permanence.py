from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import translation

from repanier.models import (
    PurchaseWoReceiver,
    OfferItemWoReceiver,
    CustomerInvoice,
    ProducerInvoice,
    CustomerProducerInvoice,
    BankAccount,
    Customer,
)
from repanier.models.permanence import Permanence


class Command(BaseCommand):
    help = "Delete the specified permanence including all purchases"

    def add_arguments(self, parser):
        parser.add_argument("permanence_id", nargs="+", type=int)

    def handle(self, *args, **options):
        translation.activate(settings.LANGUAGE_CODE)
        for permanence_id in options["permanence_id"]:
            for permanence in Permanence.objects.filter(id=permanence_id).order_by(
                "permanence_date"
            ):
                print("{}".format(permanence))
                PurchaseWoReceiver.objects.filter(permanence_id=permanence_id).delete()
                OfferItemWoReceiver.objects.filter(permanence_id=permanence_id).delete()
                CustomerInvoice.objects.filter(permanence_id=permanence_id).delete()
                ProducerInvoice.objects.filter(permanence_id=permanence_id).delete()
                CustomerProducerInvoice.objects.filter(
                    permanence_id=permanence_id
                ).delete()
                BankAccount.objects.filter(permanence_id=permanence_id).delete()
                customer_buyinggroup = Customer.get_or_create_group()

                BankAccount.open_account(customer_buyinggroup=customer_buyinggroup)
                Permanence.objects.filter(id=permanence.id).delete()
                self.stdout.write(
                    self.style.SUCCESS(
                        "Successfully deleted permanence '{}'".format(permanence)
                    )
                )
