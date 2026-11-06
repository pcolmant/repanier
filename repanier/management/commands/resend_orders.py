from django.core.management.base import BaseCommand

from repanier.task import task_order


class Command(BaseCommand):
    args = "<none>"
    help = "Resend last send order"

    def add_arguments(self, parser):
        # 1. Un argument positionnel (obligatoire par défaut)
        parser.add_argument("permanence_id", type=str, help="Id de la permanence")

        # 2. Une option / argument nommé (facultatif avec un préfixe --)
        # parser.add_argument(
        #     "--env",
        #     type=str,
        #     default="production",
        #     help="Environnement d'exécution",
        # )

        # 3. Un drapeau booléen (flag --, pas de valeur nécessaire)
        # parser.add_argument(
        #     "--send-email",
        #     action="store_true",
        #     help="Activer l'envoi d'e-mails",
        # )

    def handle(self, *args, **options):
        # Récupération des valeurs passées en paramètres
        permanence_id = options["permanence_id"]

        something_to_resend = task_order.resend(permanence_id=permanence_id)
        if something_to_resend:
            self.stdout.write("Latest order resend")
        else:
            self.stdout.write("Nothing to resend")
