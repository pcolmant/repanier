from django.contrib import admin

from repanier_v2.admin.bank_account import BankAccountAdmin
from repanier_v2.models.bank_account import BankAccount

admin.site.register(BankAccount, BankAccountAdmin)

from repanier_v2.models.configuration import Configuration
from repanier_v2.admin.configuration import ConfigurationAdmin

admin.site.register(Configuration, ConfigurationAdmin)

from repanier_v2.models.notification import Notification
from repanier_v2.admin.notification import NotificationAdmin

admin.site.register(Notification, NotificationAdmin)

from repanier_v2.models.customer import Customer
from repanier_v2.admin.customer import CustomerWithUserDataAdmin

admin.site.register(Customer, CustomerWithUserDataAdmin)

from repanier_v2.models.group import Group
from repanier_v2.admin.group import GroupWithUserDataAdmin

admin.site.register(Group, GroupWithUserDataAdmin)

from repanier_v2.models.purchase import Purchase
from repanier_v2.admin.purchase import PurchaseAdmin

admin.site.register(Purchase, PurchaseAdmin)

from repanier_v2.models.lut import (
    Label,
    DispensingPoint,
    Department,
    Task,
)
from repanier_v2.admin.lut import (
    LabelAdmin,
    TaskAdmin,
    DepartmentAdmin,
    DistributionPointAdmin,
)

from django.contrib import admin


admin.site.register(Label, LabelAdmin)
admin.site.register(Task, TaskAdmin)
# admin.site.register(LUT_DepartmentForCustomer, LUTDepartmentForCustomerAdmin)
admin.site.register(Department, DepartmentAdmin)
admin.site.register(DispensingPoint, DistributionPointAdmin)


from repanier_v2.models.frozen_item import FrozenItemClosed
from repanier_v2.admin.frozen_item import FrozenItemClosedAdmin

admin.site.register(FrozenItemClosed, FrozenItemClosedAdmin)

from repanier_v2.models.frozen_item import FrozenItemSend
from repanier_v2.admin.rule_of_3_per_product import FrozenItemSendAdmin

admin.site.register(FrozenItemSend, FrozenItemSendAdmin)

from repanier_v2.models.invoice import CustomerSend
from repanier_v2.admin.rule_of_3_per_customer import CustomerSendAdmin

admin.site.register(CustomerSend, CustomerSendAdmin)

from repanier_v2.models.order import OrderInPreparation
from repanier_v2.admin.order_in_preparation import OrderInPreparationAdmin

admin.site.register(OrderInPreparation, OrderInPreparationAdmin)

from repanier_v2.models.order import OrderClosed
from repanier_v2.admin.order_closed import OrderClosedAdmin

admin.site.register(OrderClosed, OrderClosedAdmin)

from repanier_v2.models.producer import Producer
from repanier_v2.admin.producer import ProducerAdmin

admin.site.register(Producer, ProducerAdmin)

from repanier_v2.models.live_item import LiveItem
from repanier_v2.admin.live_item import LiveItemAdmin

admin.site.register(LiveItem, LiveItemAdmin)

from repanier_v2.models.box import Box
from repanier_v2.admin.box import BoxAdmin

admin.site.register(Box, BoxAdmin)

from repanier_v2.models.staff import Staff
from repanier_v2.admin.staff import StaffWithUserDataAdmin

admin.site.register(Staff, StaffWithUserDataAdmin)

########################
# TODO : TBD PCO BEGIN
from repanier_v2.models.lut import (
    LUT_ProductionMode,
    LUT_DeliveryPoint,
    LUT_DepartmentForCustomer,
    LUT_PermanenceRole,
)
from repanier_v2.admin.old_lut import (
    LUTProductionModeAdmin,
    LUTPermanenceRoleAdmin,
    LUTDepartmentForCustomerAdmin,
    LUTDeliveryPointAdmin,
)

admin.site.register(LUT_ProductionMode, LUTProductionModeAdmin)
admin.site.register(LUT_PermanenceRole, LUTPermanenceRoleAdmin)
admin.site.register(LUT_DepartmentForCustomer, LUTDepartmentForCustomerAdmin)
admin.site.register(LUT_DeliveryPoint, LUTDeliveryPointAdmin)

from repanier_v2.models.product import Product
from repanier_v2.admin.product import ProductAdmin
admin.site.register(Product, ProductAdmin)

from repanier_v2.models.permanence import PermanenceInPreparation
from repanier_v2.admin.permanence_in_preparation import PermanenceInPreparationAdmin
admin.site.register(PermanenceInPreparation, PermanenceInPreparationAdmin)

from repanier_v2.models.permanence import PermanenceDone
from repanier_v2.admin.permanence_done import PermanenceDoneAdmin
admin.site.register(PermanenceDone, PermanenceDoneAdmin)

from repanier_v2.models.offeritem import OfferItemClosed
from repanier_v2.admin.offeritem import OfferItemClosedAdmin
admin.site.register(OfferItemClosed, OfferItemClosedAdmin)

from repanier_v2.models.offeritem import OfferItemSend
from repanier_v2.admin.old_rule_of_3_per_product import OfferItemSendAdmin
admin.site.register(OfferItemSend, OfferItemSendAdmin)

# from repanier_v2.models.invoice import CustomerSend
# from repanier_v2.admin.rule_of_3_per_customer import CustomerSendAdmin
# admin.site.register(CustomerSend, CustomerSendAdmin)
# TODO : TBD PCO END
