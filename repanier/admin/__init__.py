from django.contrib import admin
from repanier.admin.bankaccount import BankAccountAdmin
from repanier.admin.configuration import ConfigurationAdmin
from repanier.admin.notification import NotificationAdmin
from repanier.admin.customer import CustomerWithUserDataAdmin
from repanier.admin.group import GroupWithUserDataAdmin
from repanier.admin.purchase import PurchaseAdmin
from repanier.admin.lut import (
    LUTProductionModeAdmin,
    LUTPermanenceRoleAdmin,
    LUTDepartmentForCustomerAdmin,
    LUTDeliveryPointAdmin,
)
from repanier.admin.rule_of_3_per_product import OfferItemSendAdmin
from repanier.admin.rule_of_3_per_customer import CustomerSendAdmin
from repanier.admin.permanence_in_preparation import PermanenceInPreparationAdmin
from repanier.admin.permanence_done import PermanenceDoneAdmin
from repanier.admin.producer import ProducerAdmin
from repanier.admin.product import ProductAdmin
from repanier.admin.staff import StaffWithUserDataAdmin