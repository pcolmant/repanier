# non proxies
from .bankaccount import BankAccount

# after Producer and Product
from .box import Box
from .box import BoxContent
from .configuration import Configuration
from .customer import Customer
from .saledelivery import SaleDelivery
from .invoice import CustomerInvoice, ProducerInvoice, CustomerProducerInvoice

# proxies
from .lut import (
    Label,
    DeliveryPoint,
    Department,
    Activity,
)

from .forsale import ForSale
from .forsale import ForSaleSend, ForSaleClosed, ForSaleWoReceiver
from .sale import Sale
from .sale import SaleInPreparation, SaleClosed

from .producer import Producer
from .product import Product, Product_Translation
from .purchase import Purchase
from .purchase import PurchaseWoReceiver
from .staff import Staff

###### TODO BEGIN OF OLD MODEL : TBD
from .invoice import CustomerSend
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

###### TODO END OF OLD MODEL : TBD
