from django.contrib import admin

from repanier.models import Producer
class ProducerAdmin(admin.ModelAdmin):
	fields = ['login_site', 'site', 'short_name', 'full_name', 'description', 'phone', 'fax', 'google_map_URL', 'address', 'bank_account']
#	exclude = ('site',)
admin.site.register(Producer, ProducerAdmin)
from repanier.models import Customer
admin.site.register(Customer)
from repanier.models import LUT_QuantityUnit
admin.site.register(LUT_QuantityUnit)
from repanier.models import LUT_CategoryForCustomer
admin.site.register(LUT_CategoryForCustomer)
from repanier.models import LUT_CategoryForProducer
admin.site.register(LUT_CategoryForProducer)
from repanier.models import LUT_CategoryForPreparator
admin.site.register(LUT_CategoryForPreparator)
from repanier.models import Product
admin.site.register(Product)
from repanier.models import LUT_PermanenceRole
admin.site.register(LUT_PermanenceRole)
from repanier.models import LUT_PermanenceLocation
admin.site.register(LUT_PermanenceLocation)
from repanier.models import Permanence
admin.site.register(Permanence)
from repanier.models import DutyRoster
admin.site.register(DutyRoster)
from repanier.models import Folder
admin.site.register(Folder)
from repanier.models import FolderItem
admin.site.register(FolderItem)
from repanier.models import Purchase
admin.site.register(Purchase)
from repanier.models import ProducerPayment
admin.site.register(ProducerPayment)
from repanier.models import CustomerPayment
admin.site.register(CustomerPayment)