# -*- coding: utf-8 -*-
from decimal import *
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

SITE_ID_REPANIER = 1
SITE_ID_PRODUCER = 2
SITE_ID_EPI_D_ICI = 6

DECIMAL_ZERO = Decimal('0')
DECIMAL_ONE = Decimal('1')
DECIMAL_0_01 = Decimal('.01')
DECIMAL_0_001 = Decimal('.001')

PERMANENCE_DISABLED = '050'
PERMANENCE_PLANIFIED = '100' 
PERMANENCE_WAIT_FOR_OPEN = '200' 
PERMANENCE_OPENED = '300'
PERMANENCE_WAIT_FOR_SEND = '400'
PERMANENCE_SEND = '500'
PERMANENCE_WAIT_FOR_DONE = '600'
PERMANENCE_INVOICES_VALIDATION_FAILED = '700'
PERMANENCE_DONE = '800'
PERMANENCE_CANCELED = '900'

LUT_PERMANENCE_STATUS = (
	(PERMANENCE_DISABLED, _('disabled')),
	(PERMANENCE_PLANIFIED, _('planified')),
	(PERMANENCE_WAIT_FOR_OPEN, _('wait for open')),
	(PERMANENCE_OPENED, _('orders opened')),
	(PERMANENCE_WAIT_FOR_SEND, _('wait for send')),
	(PERMANENCE_SEND, _('orders send to producers')),
	(PERMANENCE_WAIT_FOR_DONE, _('wait for done')),
	(PERMANENCE_INVOICES_VALIDATION_FAILED, _('invoices validation test failed')),
	(PERMANENCE_DONE, _('done'))
)

PRODUCT_PLACEMENT_FREEZER = '100'
PRODUCT_PLACEMENT_FRIDGE = '200'
PRODUCT_PLACEMENT_OUT_OF_BASKET = '300'
PRODUCT_PLACEMENT_BASKET_BOTTOM = '400'
PRODUCT_PLACEMENT_BASKET_MIDDLE = '500'
PRODUCT_PLACEMENT_BASKET_TOP = '600'

LUT_PRODUCT_PLACEMENT = (
	(PRODUCT_PLACEMENT_FREEZER, _('freezer')),
	(PRODUCT_PLACEMENT_FRIDGE, _('fridge')),
	(PRODUCT_PLACEMENT_OUT_OF_BASKET, _('loose, out of the basket')),
	(PRODUCT_PLACEMENT_BASKET_BOTTOM, _('bottom of basket')),
	(PRODUCT_PLACEMENT_BASKET_MIDDLE, _('middle of basket')),
	(PRODUCT_PLACEMENT_BASKET_TOP, _('top of basket')),
)

ADD_PORDUCT_MANUALY = '100'
ADD_PRODUCT_TO_CUSTOMER_BASKET_0 = '200'
ADD_PRODUCT_TO_CUSTOMER_BASKET = '300'
ADD_PRODUCT_TO_GROUP_BASKET = '400'
# ADD_PRODUCT_ADDED_WHEN_CREATING_A_PURCHASE_IN_ADMIN = "700"
# ADD_PRODUCT_DEACTIVATED_ADDED_WHEN_CREATING_A_PURCHASE_IN_ADMIN = "800"


LUT_ADD_PRODUCT = (
	(ADD_PORDUCT_MANUALY, _("As usual, let customers freely order it.")),
	(ADD_PRODUCT_TO_CUSTOMER_BASKET_0, _('As a deposit, a bag : always add this product to preparation list when the customer has purchased something.')),
	(ADD_PRODUCT_TO_CUSTOMER_BASKET, _('As a subscription, common expense : add the minimal order quantity of this product to each customer of the group')),
	(ADD_PRODUCT_TO_GROUP_BASKET, _('As a transportation cost : add the minimal order quantity of this product to the basket representing the group.')),
)

# LUT_ADD_PRODUCT_DISPLAY = (
# 	(ADD_PORDUCT_MANUALY, _("As usual, let customers freely order it.")),
# 	(ADD_PRODUCT_TO_CUSTOMER_BASKET_0, _('As a deposit, a bag : always add this product to preparation list when the customer has purchased something.')),
# 	(ADD_PRODUCT_TO_CUSTOMER_BASKET, _('As a subscription, common expense : add the minimal order quantity of this product to each customer of the group')),
# 	(ADD_PRODUCT_TO_GROUP_BASKET, _('As a transportation cost : add the minimal order quantity of this product to the basket representing the group.')),
# 	# (ADD_PRODUCT_TO_PERMANENCE_TEAM_MEMBER_BASKET, _('As a permanance team expense, motivation : add this product to permanence team members.')),
# 	# (ADD_PRODUCT_TO_STAFF_MEMBER_BASKET, _('As a staff expense : add this product to permanence staff member.')),
# 	(ADD_PRODUCT_ADDED_WHEN_CREATING_A_PURCHASE_IN_ADMIN, _('Product added when manually adding a purchase in the admin interface.')),
# 	(ADD_PRODUCT_DEACTIVATED_ADDED_WHEN_CREATING_A_PURCHASE_IN_ADMIN, _('Deactivated product added when manually adding a purchase in the admin interface.')),
# )

VAT_100 = '100'
VAT_200 = '200' 
VAT_300 = '300'
VAT_400 = '400'
VAT_500 = '500'
VAT_600 = '600'

LUT_VAT = (
	(VAT_100, _('none')),
	(VAT_200, _('compensation 2%')),
	(VAT_300, _('compensation 6%')),
	(VAT_400, _('vat 6%')),
	(VAT_500, _('vat 12%')),
	(VAT_600, _('vat 21%')),
)

LUT_VAT_REVERSE = (
	( unicode(_('none')), VAT_100),
	( unicode(_('compensation 2%')), VAT_200),
	( unicode(_('compensation 6%')), VAT_300),
	( unicode(_('vat 6%')), VAT_400),
	( unicode(_('vat 12%')), VAT_500),
	( unicode(_('vat 21%')), VAT_600),
)
