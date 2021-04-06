# non proxies
from .bank_account import BankAccount

# after Producer and Product
from .box import Box
from .box import BoxContent
from .configuration import Configuration
from .customer import Customer
from .order_dispensing_point import OrderDispensingPoint
from .receipt import CustomerReceipt, ProducerReceipt, CustomerProducerReceipt

# proxies
from .lut import (
    Label,
    DispensingPoint,
    Department,
    Task,
)

from .frozen_item import FrozenItem
from .frozen_item import FrozenItemSend, FrozenItemClosed, FrozenItemWoReceiver
from .order import Order
from .order import OrderInPreparation, OrderClosed
from .live_item import LiveItem
from .producer import Producer

from .purchase import Purchase
from .purchase import PurchaseWoReceiver
from .staff import Staff

###### TODO BEGIN OF OLD MODEL : TBD
from .invoice import CustomerSend
from .invoice import CustomerInvoice, ProducerInvoice, CustomerProducerInvoice
from .lut import (
    LUT_ProductionMode,
    LUT_DeliveryPoint,
    LUT_DepartmentForCustomer,
    LUT_PermanenceRole,
)

from .offeritem import OfferItem
from .offeritem import OfferItemSend, OfferItemClosed, OfferItemWoReceiver
from .permanence import Permanence
from .permanence import PermanenceInPreparation, PermanenceDone
from .permanenceboard import PermanenceBoard
from .deliveryboard import DeliveryBoard

# from .forsale import ForSale
# from .forsale import ForSaleSend, ForSaleClosed, ForSaleWoReceiver
from .product import Product, Product_Translation

###### TODO END OF OLD MODEL : TBD
