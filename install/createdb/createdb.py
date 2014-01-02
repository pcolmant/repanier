# -*- coding: ISO-8859-1 -*-
import sys
import csv
# Create Test DB
from django.conf import settings
from django.contrib.auth.models import User, Group, Permission, ContentType
from django.contrib.auth.hashers import make_password
from django.contrib.sites.models import Site
from repanier.models import Customer, SiteCustomer
from repanier.models import Producer, SiteProducer
from repanier.models import Staff
from repanier.models import Product
from repanier.models import LUT_ProductionMode
from repanier.models import LUT_DepartmentForCustomer
from repanier.models import LUT_DepartmentForProducer

from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

def add_all_sites():
  print("---------- Sites ----------")
  with open('sites.csv', 'r') as f:
    reader = csv.reader(f)
    firstrow = True
    for row in reader:
      if firstrow:
        # first line = header -> pass it.
        firstrow = False
      else:
        site = None
        print row
        site_set = Site.objects.filter(id = int(row[0]))[:1]
        if site_set:
          for site in site_set:
            site.domain = row[1]
            site.name = row[2]
            site.save()
        else:
          Site.objects.create(id = int(row[0]), domain = row[1], name = row[2])

def add_all_groups():
  print("---------- Create one group for each site, to allow web site content limited access ----------")
  with open('sites.csv', 'r') as f:
    reader = csv.reader(f)
    firstrow = True
    for row in reader:
      if firstrow:
        # first line = header -> pass it.
        firstrow = False
      else:
        site = None
        print row
        group_set = Group.objects.filter(name = row[1])[:1]
        if not(group_set):
          Group.objects.create(name = row[1])
  print("---------- Groups & their permissions ----------")
  with open('groups.csv', 'r') as f:
    reader = csv.reader(f)
    firstrow = True
    for row in reader:
      if firstrow:
        # first line = header.
        firstrow = False
        # récupérer les noms des groupes et créer les groupes si nécessaire
        group_name = row[4:]
        for name in group_name:
          print name
          group_set = Group.objects.filter(name=name)[:1]
          if not(group_set):
            Group.objects.create(name=name)
      else:
        site = None
        print row
        content_type = ContentType.objects.get(app_label=row[1], model=row[2])
        permission = Permission.objects.get(content_type=content_type, codename=row[3])
        # attribuer les permissions à chaque groupes
        for i, name in enumerate(group_name):
          group = Group.objects.get(name=name)
          if row[i+4]=='x':
            group.permissions.add(permission)
          else:
            group.permissions.remove(permission)

def add_all_customers():
  print("---------- Customers ----------")
  with open('customers.csv', 'r') as f:
    reader = csv.reader(f)
    firstrow = True
    for row in reader:
      if firstrow:
        # first line = header -> pass it.
        firstrow = False
      else:
        customer_id = None
        print row
        if(row[1]):
          # This is a User
          user = None
          user_set = User.objects.filter(username = row[1])[:1]
          if user_set:
            for user in user_set:
              user.password = make_password(row[2])
              user.is_superuser=False
              user.is_staff=False
              user.is_active=True
              user.email=row[3]
              user.first_name=row[4]
              user.last_name=row[5]
              user.save()
          else:
            user = User.objects.create(username = row[1], 
              password = make_password(row[2]),
              is_superuser=False, is_staff=False, is_active=True,
              email=row[3], first_name=row[4], last_name=row[5])
          site = Site.objects.get(id=int(row[0])) 
          group = Group.objects.get(name=site.domain) 
          group.user_set.add(user)
          customer = None
          customer_set = Customer.objects.filter(user_id = user.id)[:1]
          if customer_set:
            for customer in customer_set:
              customer.phone1 = row[6]
              customer.phone2 = row[7]
              customer.address = row[8]
              customer.is_active = True
              customer.save()
          else:
            customer = Customer.objects.create(user_id = user.id,
              phone1 = row[6], phone2 = row[7], address = row[8],
              is_active = True)
          if customer!= None:
            customer_id = customer.id
        # This is maybe a User
        # If this is the case : customer_id is set
        sitecustomer_set = SiteCustomer.objects_without_filter.filter(
          short_basket_name = row[9], site_id = int(row[0]))[:1]
        if sitecustomer_set:
          for sitecustomer in sitecustomer_set:
            sitecustomer.customer_id = customer_id
            sitecustomer.site_id = int(row[0])
            sitecustomer.long_basket_name = row[10]
            sitecustomer.date_previous_balance = row[11]
            sitecustomer.previous_balance = row[12]
            sitecustomer.amount_in = row[13]
            sitecustomer.amount_out = row[14]
            sitecustomer.represent_this_buyinggroup = ( row[15] == "True" )
            sitecustomer.is_active = True
            sitecustomer.save()
        else:
          sitecustomer = SiteCustomer.objects.create(customer_id = customer_id,
            site_id = int(row[0]), short_basket_name = row[9], 
            long_basket_name = row[10], date_previous_balance = row[11],
            previous_balance = row[12], 
            amount_in = row[13],
            amount_out = row[14], represent_this_buyinggroup = ( row[15] == "True" ),
            is_active = True)

def add_all_staffs():
  print("---------- Staffs ----------")
  with open('staffs.csv', 'r') as f:
    reader = csv.reader(f)
    firstrow = True
    for row in reader:
      if firstrow:
        # first line = header -> pass it.
        firstrow = False
      else:
        staff_id = None
        print row
        if(row[1]):
          # This is a User
          user = None
          user_set = User.objects.filter(username = row[1])[:1]
          if user_set:
            for user in user_set:
              user.password = make_password(row[2])
              user.is_superuser=False
              user.is_staff=True
              user.is_active=True
              user.email=row[3]
              user.first_name=row[4]
              user.last_name=row[5]
              user.save()
          else:
            user = User.objects.create(username = row[1], 
              password = make_password(row[2]),
              is_superuser=False, is_staff=True, is_active=True,
              email=row[3], first_name=row[4], last_name=row[5])
          site = Site.objects.get(id=int(row[0])) 
          group = Group.objects.get(name=site.domain) 
          group.user_set.add(user)
          group = Group.objects.get(name=row[8]) 
          group.user_set.add(user)
          customer_responsible = SiteCustomer.objects_without_filter.get(
            customer__user__username = row[7], site_id = int(row[0]))
          staff_set = Staff.objects_without_filter.filter(user_id = user.id)[:1]
          if staff_set:
            for staff in staff_set:
              staff.login_site_id = int(row[0])
              staff.customer_responsible_id = customer_responsible.id
              staff.save()
          else:
            staff = Staff.objects.create(user_id = user.id,
              login_site_id = int(row[0]),
              customer_responsible_id = customer_responsible.id,
              long_name = row[6], memo = row[6],
              is_active = True)

def add_all_producers():
  print("---------- Producers ----------")
  with open('producers.csv', 'r') as f:
    reader = csv.reader(f)
    firstrow = True
    for row in reader:
      if firstrow:
        # first line = header -> pass it.
        firstrow = False
      else:
        producer_id = None
        print row
        if(row[1]):
          user = None
          user_set = User.objects.filter(username = row[1])[:1]
          if user_set:
            for user in user_set:
              user.password = make_password(row[2])
              user.is_superuser=False
              user.is_staff=False
              user.is_active=True
              user.email=row[3]
              user.first_name=row[4]
              user.last_name=row[5]
              user.save()
          else:
            user = User.objects.create(username = row[1], 
              password = make_password(row[2]),
              is_superuser=False, is_staff=False, is_active=True,
              email=row[3], first_name=row[4], last_name=row[5])
          site = Site.objects.get(id=2) 
          group = Group.objects.get(name=site.domain) 
          group.user_set.add(user)
          site = Site.objects.get(id=int(row[0])) 
          group = Group.objects.get(name=site.domain) 
          group.user_set.add(user)
          producer = None
          producer_set = Producer.objects.filter(user_id = user.id)[:1]
          if producer_set:
            for producer in producer_set:
              producer.phone1 = row[6]
              producer.phone2 = row[7]
              producer.fax = row[8]
              producer.bank_account = row[9]
              producer.address = row[10]
              producer.is_active = True
              producer.save()
          else:
            producer = Producer.objects.create(user_id = user.id,
              phone1 = row[6], phone2 = row[7], fax = row[8],
              bank_account = row[9], address = row[10], is_active = True)
          if producer!= None:
            producer_id = producer.id
        siteproducer_set = SiteProducer.objects_without_filter.filter(
          short_profile_name = row[11], site_id = int(row[0]))[:1]
        if siteproducer_set:
          for siteproducer in siteproducer_set:
            siteproducer.producer_id = producer_id
            siteproducer.site_id = int(row[0])
            siteproducer.long_profile_name = row[12]
            siteproducer.memo = row[13]
            siteproducer.date_previous_balance = row[14]
            siteproducer.previous_balance = row[15]
            siteproducer.amount_in = row[16]
            siteproducer.amount_out = row[17]
            siteproducer.represent_this_buyinggroup = ( row[18] == "True" )
            siteproducer.is_active = True
            siteproducer.save()
        else:
          siteproducer = SiteProducer.objects.create(producer_id = producer_id,
            site_id = int(row[0]), short_profile_name = row[11], 
            long_profile_name = row[12], memo = row[13],
            date_previous_balance = row[14],
            previous_balance = row[15], amount_in = row[16],
            amount_out = row[17], represent_this_buyinggroup = ( row[18] == "True" ),
            is_active = True)


def add_all_products():
  print("---------- Products ----------")
  with open('products.csv', 'r') as f:
    reader = csv.reader(f)
    firstrow = True
    for row in reader:
      if firstrow:
        # first line = header -> pass it.
        firstrow = False
      else:
        print row
        # Find site_producer_id from row[1]
        site_producer_id = None
        site_producer_set = SiteProducer.objects_without_filter.filter(
          site = int(row[0]), short_profile_name = row[1])[:1]
        if site_producer_set:
          for site_procuder in site_producer_set:
            break
          site_producer_id = site_procuder.id
        # Does the product already exists ?
        procduct_set = Product.objects_without_filter.filter(
          long_name = row[2], site_id = int(row[0]))[:1]
        if not procduct_set.exists():
          # Create the product beacause it doesn't exist
          # Find or create production_mode_id from row[3]
          production_mode_id = None
          production_mode_set = LUT_ProductionMode.objects_without_filter.filter(
            site = int(row[0]), short_name = row[3])[:1]
          if production_mode_set:
            for production_mode in production_mode_set:
              break
            production_mode_id = production_mode.id
          else:
            production_mode = LUT_ProductionMode.objects.create(
              site_id = int(row[0]),
              short_name = row[3], description = row[3],
              is_active = True)
            if production_mode!= None:
              production_mode_id = production_mode.id 
          # Find or create department_for_customer_id from row[4]
          department_for_customer_id = None
          department_for_customer_set = LUT_DepartmentForCustomer.objects_without_filter.filter(
            site = int(row[0]), short_name = row[4])[:1]
          if department_for_customer_set:
            for department_for_customer in department_for_customer_set:
              break
            department_for_customer_id = department_for_customer.id
          else:
            department_for_customer = LUT_DepartmentForCustomer.objects.create(
              site_id = int(row[0]),
              short_name = row[4], description = row[4],
              is_active = True)
            if department_for_customer!= None:
              department_for_customer_id = department_for_customer.id 
          # Find or create department_for_producer_id from row[6]
          department_for_producer_id = None
          department_for_producer_set = LUT_DepartmentForProducer.objects_without_filter.filter(
            site = int(row[0]), short_name = row[6])[:1]
          if department_for_producer_set:
            for department_for_producer in department_for_producer_set:
              break
            department_for_producer_id = department_for_producer.id
          else:
            department_for_producer = LUT_DepartmentForProducer.objects.create(
              site_id = int(row[0]),
              short_name = row[6], description = row[6],
              is_active = True)
            if department_for_producer!= None:
              department_for_producer_id = department_for_producer.id 
          # Create it         
          procduct = Product.objects.create(
            site_id = int(row[0]), site_producer_id = site_producer_id, 
            long_name = row[2], production_mode_id = production_mode_id,
            picture = None, order_description = "", usage_description = "", 
            department_for_customer_id = department_for_customer_id,
            department_for_producer_id = department_for_producer_id,
            order_by_kg_pay_by_kg = ( row[8] == "True" ),
            order_by_piece_pay_by_kg = ( row[9] == "True" ),
            order_by_piece_pay_by_piece = ( row[10] == "True" ),
            producer_must_give_order_detail_per_customer = ( row[11] == "True" ),
            producer_unit_price = row[12],
            customer_minimum_order_quantity = row[13],
            customer_increment_order_quantity = row[14],
            customer_alert_order_quantity = row[15],
            is_into_offer=False,
            is_active = ( row[16] == "True" ))
  order = 0
  for obj in Product.objects_without_filter.all().order_by(
      "site_producer__short_profile_name", "long_name"):
    order += 1
    obj.product_order = order
    obj.save()

#  producer.followed_by.add(1,3,4,5)

def main():
  add_all_sites()
  add_all_groups()
  add_all_customers()
  add_all_staffs()
  add_all_producers()
  add_all_products()

if __name__ == '__main__':
        if '--version' in sys.argv:
                print(__version__)
        else:
                main()