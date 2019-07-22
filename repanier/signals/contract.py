from django.conf import settings
from django.db.models.signals import pre_save
from django.dispatch import receiver

from repanier.models import Contract, ContractContent
from repanier.tools import get_recurrence_dates


@receiver(pre_save, sender=Contract)
def contract_pre_save(sender, **kwargs):
    contract = kwargs["instance"]

    # Save old permanences date for futher adjustement of contract content dates
    old_permanences_dates = contract.permanences_dates

    # Calculate new contract dates
    new_dates = get_recurrence_dates(
        contract.first_permanence_date, contract.recurrences
    )
    if len(new_dates) > 0:
        contract.permanences_dates = settings.DJANGO_SETTINGS_DATES_SEPARATOR.join(
            # Important : linked to django.utils.dateparse.parse_date format
            one_date.strftime("%Y-%m-%d")
            for one_date in new_dates
        )
        contract.last_permanence_date = new_dates[-1]
    else:
        contract.permanences_dates = None
        contract.last_permanence_date = None

    # Adjust contract content dates if an occurence has been removed
    if old_permanences_dates:
        old_dates_str = old_permanences_dates.split(
            settings.DJANGO_SETTINGS_DATES_SEPARATOR
        )
    else:
        old_dates_str = []
    if contract.permanences_dates:
        new_dates_str = contract.permanences_dates.split(
            settings.DJANGO_SETTINGS_DATES_SEPARATOR
        )
    else:
        new_dates_str = []

    dates_to_remove_str = []
    for one_date_str in old_dates_str:
        if one_date_str not in new_dates_str:
            dates_to_remove_str.append(one_date_str)

    dates_to_add_str = []
    for one_date_str in new_dates_str:
        if one_date_str not in old_dates_str:
            dates_to_add_str.append(one_date_str)

    if len(dates_to_remove_str) > 0 or len(dates_to_add_str) > 0:
        for contract_content in ContractContent.objects.filter(contract=contract):
            if contract_content.permanences_dates:
                all_dates_str = list(
                    filter(
                        None,
                        contract_content.permanences_dates.split(
                            settings.DJANGO_SETTINGS_DATES_SEPARATOR
                        ),
                    )
                )
            else:
                all_dates_str = []
            if contract_content.not_permanences_dates:
                all_not_dates_str = list(
                    filter(
                        None,
                        contract_content.not_permanences_dates.split(
                            settings.DJANGO_SETTINGS_DATES_SEPARATOR
                        ),
                    )
                )
            else:
                all_not_dates_str = []
            for one_dates_to_remove_str in dates_to_remove_str:
                if one_dates_to_remove_str in all_dates_str:
                    all_dates_str.remove(one_dates_to_remove_str)
                if one_dates_to_remove_str in all_not_dates_str:
                    all_not_dates_str.remove(one_dates_to_remove_str)
            for one_dates_to_add_str in dates_to_add_str:
                # if one_dates_to_add_str not in all_not_dates_str: --> should be always True
                all_not_dates_str.append(one_dates_to_add_str)
            if len(all_dates_str) > 0:
                contract_content.permanences_dates = settings.DJANGO_SETTINGS_DATES_SEPARATOR.join(
                    all_dates_str
                )
            else:
                contract_content.permanences_dates = None
            if len(all_not_dates_str) > 0:
                contract_content.not_permanences_dates = settings.DJANGO_SETTINGS_DATES_SEPARATOR.join(
                    all_not_dates_str
                )
            else:
                contract_content.not_permanences_dates = None
            contract_content.save()
