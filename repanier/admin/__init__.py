# -*- coding: utf-8
from django.contrib import admin

from repanier.models import BankAccount
from .bankaccount import BankAccountAdmin
admin.site.register(BankAccount, BankAccountAdmin)
from repanier.models import Configuration
from .configuration import ConfigurationAdmin
admin.site.register(Configuration, ConfigurationAdmin)
from repanier.models import Customer
from .customer import CustomerWithUserDataAdmin
admin.site.register(Customer, CustomerWithUserDataAdmin)
from repanier.models import Purchase
from .purchase import PurchaseAdmin
admin.site.register(Purchase, PurchaseAdmin)
from repanier.models import LUT_ProductionMode, LUT_DeliveryPoint, LUT_DepartmentForCustomer, LUT_PermanenceRole
from .lut import LUTProductionModeAdmin, LUTPermanenceRoleAdmin, LUTDepartmentForCustomerAdmin, LUTDeliveryPointAdmin
admin.site.register(LUT_ProductionMode, LUTProductionModeAdmin)
admin.site.register(LUT_PermanenceRole, LUTPermanenceRoleAdmin)
admin.site.register(LUT_DepartmentForCustomer, LUTDepartmentForCustomerAdmin)
admin.site.register(LUT_DeliveryPoint, LUTDeliveryPointAdmin)
from repanier.models import OfferItemClosed
from .offeritem import OfferItemClosedAdmin
admin.site.register(OfferItemClosed, OfferItemClosedAdmin)
from repanier.models import OfferItemSend
from .rule_of_3_per_product import OfferItemSendAdmin
admin.site.register(OfferItemSend, OfferItemSendAdmin)
from repanier.models import CustomerSend
from .rule_of_3_per_customer import CustomerSendAdmin
admin.site.register(CustomerSend, CustomerSendAdmin)
from repanier.models import PermanenceInPreparation
from .permanence_in_preparation import PermanenceInPreparationAdmin
admin.site.register(PermanenceInPreparation, PermanenceInPreparationAdmin)
from repanier.models import PermanenceDone
from .permanence_done import PermanenceDoneAdmin
admin.site.register(PermanenceDone, PermanenceDoneAdmin)
from repanier.models import Producer
from .producer import ProducerAdmin
admin.site.register(Producer, ProducerAdmin)
from repanier.models import Product
from .product import ProductAdmin
admin.site.register(Product, ProductAdmin)
from repanier.models.box import Box
from .box import BoxAdmin
admin.site.register(Box, BoxAdmin)
from repanier.models import Staff
from .staff import StaffWithUserDataAdmin
admin.site.register(Staff, StaffWithUserDataAdmin)
