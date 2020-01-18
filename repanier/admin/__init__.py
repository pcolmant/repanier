from django.contrib import admin

from repanier.models.bankaccount import BankAccount
from repanier.admin.bankaccount import BankAccountAdmin

admin.site.register(BankAccount, BankAccountAdmin)
from repanier.models.configuration import Configuration
from repanier.admin.configuration import ConfigurationAdmin

admin.site.register(Configuration, ConfigurationAdmin)
from repanier.models.notification import Notification
from repanier.admin.notification import NotificationAdmin

admin.site.register(Notification, NotificationAdmin)
from repanier.models.customer import Customer
from repanier.admin.customer import CustomerWithUserDataAdmin

admin.site.register(Customer, CustomerWithUserDataAdmin)
from repanier.models.group import Group
from repanier.admin.group import GroupWithUserDataAdmin

admin.site.register(Group, GroupWithUserDataAdmin)
from repanier.models.purchase import Purchase
from repanier.admin.purchase import PurchaseAdmin

admin.site.register(Purchase, PurchaseAdmin)
from repanier.models.lut import (
    LUT_ProductionMode,
    LUT_DeliveryPoint,
    LUT_DepartmentForCustomer,
    LUT_PermanenceRole,
)
from repanier.admin.lut import (
    LUTProductionModeAdmin,
    LUTPermanenceRoleAdmin,
    LUTDepartmentForCustomerAdmin,
    LUTDeliveryPointAdmin,
)

admin.site.register(LUT_ProductionMode, LUTProductionModeAdmin)
admin.site.register(LUT_PermanenceRole, LUTPermanenceRoleAdmin)
admin.site.register(LUT_DepartmentForCustomer, LUTDepartmentForCustomerAdmin)
admin.site.register(LUT_DeliveryPoint, LUTDeliveryPointAdmin)
from repanier.models.offeritem import OfferItemClosed
from repanier.admin.offeritem import OfferItemClosedAdmin

admin.site.register(OfferItemClosed, OfferItemClosedAdmin)
from repanier.models.offeritem import OfferItemSend
from repanier.admin.rule_of_3_per_product import OfferItemSendAdmin

admin.site.register(OfferItemSend, OfferItemSendAdmin)
from repanier.models.invoice import CustomerSend
from repanier.admin.rule_of_3_per_customer import CustomerSendAdmin

admin.site.register(CustomerSend, CustomerSendAdmin)
from repanier.models.permanence import PermanenceInPreparation
from repanier.admin.permanence_in_preparation import PermanenceInPreparationAdmin

admin.site.register(PermanenceInPreparation, PermanenceInPreparationAdmin)
from repanier.models.permanence import PermanenceDone
from repanier.admin.permanence_done import PermanenceDoneAdmin

admin.site.register(PermanenceDone, PermanenceDoneAdmin)
from repanier.models.producer import Producer
from repanier.admin.producer import ProducerAdmin

admin.site.register(Producer, ProducerAdmin)
from repanier.models.product import Product
from repanier.admin.product import ProductAdmin

admin.site.register(Product, ProductAdmin)
from repanier.models.box import Box
from repanier.admin.box import BoxAdmin

admin.site.register(Box, BoxAdmin)
from repanier.models.staff import Staff
from repanier.admin.staff import StaffWithUserDataAdmin

admin.site.register(Staff, StaffWithUserDataAdmin)
