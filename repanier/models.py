from django.db import models
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.contrib.sites.managers import CurrentSiteManager

# Create your models here.



class UserProfile(models.Model):
	user = models.OneToOneField(User)
	# Nom, prenom, email, actif, equipe, surper-utilisateur, groupe, droits, 
	# date de derniere coonnnexion, date d'inscription.
	login_site = models.ForeignKey(Site)
	site = models.ManyToManyField(Site, related_name = 'userprofile__site')
	objects = models.Manager()
	on_site = CurrentSiteManager()
	
	short_name = models.CharField(max_length=25)
	full_name = models.CharField(max_length=100)
	phone = models.CharField(max_length=100)
	address = models.TextField()
#	picture = models.ImageField()
	
class Producer(UserProfile):
	description = models.TextField()
	google_map_URL = models.URLField()
	bank_account = models.CharField(max_length=100)
	fax = models.CharField(max_length=100)
	
	def __unicode__(self):
		return self.short_name

class Customer(UserProfile):

	def __unicode__(self):
		return self.short_name

class LUT_QuantityUnit(models.Model):
	site = models.ForeignKey(Site)
	objects = models.Manager()
	on_site = CurrentSiteManager()

	short_name = models.CharField(max_length=25)
	position = models.IntegerField(default=0)
	description = models.CharField(max_length=200)

	def __unicode__(self):
		return self.short_name

class LUT_Category(models.Model):
	site = models.ForeignKey(Site)
	objects = models.Manager()
	on_site = CurrentSiteManager()

	short_name = models.CharField(max_length=25)
	position = models.IntegerField(default=0)
	description = models.CharField(max_length=200)

	def __unicode__(self):
		return self.short_name

class LUT_CategoryForCustomer(LUT_Category):

	def __unicode__(self):
		return self.short_name

class LUT_CategoryForProducer(LUT_Category):

	def __unicode__(self):
		return self.short_name
			
class LUT_CategoryForPreparator(LUT_Category):

	def __unicode__(self):
		return self.short_name

class Product(models.Model):
	# Product portfolio
	site = models.ManyToManyField(Site)
	objects = models.Manager()
	on_site = CurrentSiteManager()

	producer = models.ForeignKey(Producer, on_delete=models.PROTECT)
	short_name = models.CharField(max_length=25)
#	picture = models.ImageField()
	description = models.TextField()
	more_info_URL = models.URLField()
	category_for_customer = models.ForeignKey(LUT_CategoryForCustomer, on_delete=models.PROTECT)
	position_into_category_for_customer = models.IntegerField(default=0)	
	# order into the categoryforcustomer
	category_for_producer = models.ForeignKey(LUT_CategoryForProducer, on_delete=models.PROTECT)
	position_into_category_for_producer = models.IntegerField(default=0)	
	# order into the categoryforproducer
	category_forpreparator = models.ForeignKey(LUT_CategoryForPreparator, on_delete=models.PROTECT)
	position_into_category_for_preparator = models.IntegerField(default=0)	
	# order into the categoryforpreparator

	# for the customer :
	customer_order_unit = models.ForeignKey(LUT_QuantityUnit, related_name = 'customer_order_unit+', on_delete=models.PROTECT)
	#       order unit (gr, bottle, Kg, pack of 500 grams, piece)
	customer_minimum_order_quantity = models.IntegerField(default=0)
	#       minimum order qty (eg : 100 gr, 1 bottle, 3 Kg, 1 pack of 500 grams)
	customer_increment_order_quantity = models.IntegerField(default=0)
	#       increment order qty (eg : 50 gr, 1 bottle, 3 Kg, 1 pack of 500 grams)
	customer_maximum_order_quantity = models.IntegerField(default=0)
	#       maximum order qty (eg : 1500 gr, 10 bottles, 9 Kg, 10 pack of 500 grams)
	# for the producer :
	best_producer_give_order_detail_per_customer = models.BooleanField()
	#       need order detail per customer (yes/no)
	producer_billing_unit = models.ForeignKey(LUT_QuantityUnit, related_name = 'producer_billing_unit+', on_delete=models.PROTECT)
	#       billing unit (if not the same as order unit)
	producer_unit_price = models.DecimalField(max_digits=8, decimal_places=2)
	#       last known price (into the billing unit)
	# for the buyer :
	#       must optimize the order (eg : 12 x 5 Kg => 2 x 25 Kg + 2 x 5 Kg)
	# for the preparator :
	best_preparator_record_the_quantity = models.BooleanField()
	#       must record the quantity (yes / no)
	best_preparator_record_the_weight = models.BooleanField()
	#       must record the weight (yes / no)
	best_preparator_record_the_price = models.BooleanField()
	#       must record the price (yes / no)

	def __unicode__(self):
		return self.short_name

class LUT_PermanenceRole(models.Model):
	site = models.ManyToManyField(Site)
	objects = models.Manager()
	on_site = CurrentSiteManager()
	short_name = models.CharField(max_length=25)
	description = models.TextField()
	address = models.TextField()
	google_map_URL = models.URLField()

	def __unicode__(self):
		return self.short_name	

class LUT_PermanenceLocation(models.Model):
	site = models.ManyToManyField(Site)
	objects = models.Manager()
	on_site = CurrentSiteManager()
	short_name = models.CharField(max_length=25)
	description = models.TextField()
	address = models.TextField()
	google_map_URL = models.URLField()

	def __unicode__(self):
		return self.short_name

class Permanence(models.Model):
	site = models.ForeignKey(Site)
	objects = models.Manager()
	on_site = CurrentSiteManager()
	date = models.DateTimeField('prepared on')
	location = models.ForeignKey(LUT_PermanenceLocation, on_delete=models.PROTECT)
	preparator = models.ManyToManyField(UserProfile, through="DutyRoster", verbose_name="list of preparators")
	
	def __unicode__(self):
		return self.name

class DutyRoster(models.Model):
	user_pofile = models.ForeignKey(UserProfile)
	permanence = models.ForeignKey(Permanence)
	role = models.ForeignKey(LUT_PermanenceRole)

class Folder(models.Model):
	name = models.CharField(max_length=15)
	description = models.CharField(max_length=200)
	opening_date = models.DateTimeField('open from')
	closing_date = models.DateTimeField('open until')
	reception_date = models.DateTimeField('received on')
	permanence = models.ForeignKey(Permanence)
	
	def __unicode__(self):
		return self.name

class FolderItem(models.Model):
	# filter placed on product portfolio
	folder = models.ForeignKey(Folder, on_delete=models.PROTECT)
	product = models.ForeignKey(Product, on_delete=models.PROTECT)

#        def __unicode__(self):
#            return self.

class Purchase(models.Model):
	# site_id already present into folder_item->folder->permanace
	folder_item = models.ForeignKey(FolderItem, on_delete=models.PROTECT)
	customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
	# begin for optimisation purpose
	producer = models.ForeignKey(Producer, on_delete=models.PROTECT)
	product = models.ForeignKey(Product, on_delete=models.PROTECT)
	# end for optimisation purpose
	order_quantity = models.DecimalField(max_digits=9, decimal_places=3)
	shopping_date = models.DateField(auto_now_add=True)
	# price, quantity or weight
	preparator_recorded_value = models.DecimalField(max_digits=8, decimal_places=2)
	comment = models.CharField(max_length=200, default = '', null = True)
	balance = models.DecimalField(max_digits=8, decimal_places=2)
	payment_amount_from_customer_all_producer_account = models.DecimalField(max_digits=8, decimal_places=2)
	payment_amount_from_customer_dedicated_producer_account = models.DecimalField(max_digits=8, decimal_places=2)
	# for the customer :
	#       order qty (eg : 100 gr, 1 bottle, 3 Kg, 1 pack of 500 grams)
	#       order unit (gr, bottle, Kg, pack of 500 grams, piece)
	# for the preparator :
	#       delivered (yes / no / partially)
	#       weight if must record the weight (allways in Kg)
	#				 unit price
	#       total price if must record the total price
	#       quantity in other case
	#       comment
		
#        def __unicode__(self):
#            return self.

class ProducerPayment(models.Model):
	site = models.ForeignKey(Site)
	objects = models.Manager()
	on_site = CurrentSiteManager()

	payment_amount = models.DecimalField(max_digits=8, decimal_places=2)
	payment_description = models.CharField(max_length=200)
	payment_date = models.DateField(auto_now_add=True)
	# mouvement to provision a specific producer. NULL if none.
	payment_to_this_producer = models.ForeignKey(Producer, on_delete=models.PROTECT)
	
class CustomerPayment(models.Model):
	site = models.ForeignKey(Site)
	objects = models.Manager()
	on_site = CurrentSiteManager()
	
	payment_from_this_customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
	payment_amount = models.DecimalField(max_digits=8, decimal_places=2)
	payment_description = models.CharField(max_length=200)
	payment_date = models.DateField(auto_now_add=True)
	is_for_all_producer = models.BooleanField()
	# mouvement to provision a specific producer. NULL if not the case.
	is_dedicated_to_this_producer = models.ForeignKey(Producer, null = True, on_delete=models.PROTECT)
