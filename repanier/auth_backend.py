# -*- coding: utf-8 -*-
from const import *
from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from repanier.models import SiteCustomer

class RepanierCustomBackend(ModelBackend):
	def authenticate(self, **credentials):
		user_or_none = None
		try:
			user_or_none = super(RepanierCustomBackend, self).authenticate(**credentials)
			if user_or_none:
				if user_or_none.is_superuser:
					if not (user_or_none.is_active):
						user_or_none = None
				else:
					is_customer = False
					is_staff = False
					is_producer = False
					try:
						a = user_or_none.customer
						is_customer = True
					except:
						try:
							a = user_or_none.sitestaff
							is_staff = True
						except:
							try:
								a = user_or_none.producer
								is_producer = True
							except:
								user_or_none = None
					if is_customer:
						site_customer = SiteCustomer.objects.filter(
							site_id = settings.SITE_ID,
							customer_id = user_or_none.customer)
						if not(site_customer.exists()):
							user_or_none = None
					elif is_staff:
						# A staff member may only access to one django admin site
						if user_or_none.sitestaff.site_id != settings.SITE_ID:
							user_or_none = None
					elif is_producer:
						# Only allowed to log into the site dedicated to producers
						if SITE_ID_PRODUCER != settings.SITE_ID:
							user_or_none = None
		except Exception as e:
			user_or_none = None
		# if user_or_none :
		# 	print ('Authenyticate user : %s' % getattr(user_or_none, get_user_model().USERNAME_FIELD))
		# else:
		# 	print ('Authenticate user : not defined')	
		return user_or_none

	def get_user(self, user_id):
		user_or_none = None
		try:
			user_or_none = User.objects.get(pk=user_id)
			if user_or_none:
				if user_or_none.is_superuser:
					if not (user_or_none.is_active):
						user_or_none = None
				else:
					is_customer = False
					is_staff = False
					is_producer = False
					try:
						a = user_or_none.customer
						is_customer = True
					except:
						try:
							a = user_or_none.sitestaff
							is_staff = True
						except:
							try:
								a = user_or_none.producer
								is_producer = True
							except:
								user_or_none = None
					if is_customer:
						site_customer = SiteCustomer.objects.filter(
							site_id = settings.SITE_ID,
							customer_id = user_or_none.customer)
						if not(site_customer.exists()):
							user_or_none = None
					elif is_staff:
						# A staff member may only access to one django admin site
						if user_or_none.sitestaff.site_id != settings.SITE_ID:
							user_or_none = None
					elif is_producer:
						# Only allowed to log into the site dedicated to producers
						if SITE_ID_PRODUCER != settings.SITE_ID:
							user_or_none = None
		except:
			user_or_none = None
		# if user_or_none :
		# 	print ('Get user : %s' % getattr(user_or_none, get_user_model().USERNAME_FIELD))
		# else:
		# 	print ('Get user : not defined')
		return user_or_none