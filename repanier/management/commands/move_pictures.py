# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from string import upper, rsplit
from PIL import Image

try:
    from StringIO import StringIO as IO
except ImportError:
    from io import BytesIO as IO
import os
from django.core.files.storage import default_storage
from django.utils.text import slugify
from django.core.management.base import BaseCommand
from django.conf import settings
from repanier.models import LUT_ProductionMode, LUT_DeliveryPoint, LUT_DepartmentForCustomer, LUT_PermanenceRole, \
    Product, OfferItem

# sudo rm -rf /var/tmp/django_cache/ptidej.repanier.be/
# cd /home/pi/v2/ptidej/ptidej/media/
# sudo chown pi:pi public
# cd /home/pi/v2/ptidej/
# python manage.py move_pictures
# cd /home/pi/v2/ptidej/ptidej/media/
# sudo chown -R www-data:www-data public
# sudo chown www-data:www-data /var/tmp/django_cache/ptidej.repanier.be/

# do not forget to rename picture 2 in picture, makemigrations and in admin picture_field.widget.upload_to += os_sep + producer.short_profile_name

class Command(BaseCommand):
    args = '<none>'
    help = 'Recalculate order amount'

    def handle(self, *args, **options):

        for obj in LUT_ProductionMode.objects.all():
            if obj.picture is not None:
                self.move(record=obj, to_subdir="label", size="XS")
        # for obj in LUT_DeliveryPoint.objects.all():
        #     if obj.picture is not None:
        #         self.move(record=obj, to_subdir="LUT_DeliveryPoint", size="S")
        # for obj in LUT_DepartmentForCustomer.objects.all():
        #     if obj.picture is not None:
        #         self.move(record=obj, to_subdir="LUT_DepartmentForCustomer", size="S")
        # for obj in LUT_PermanenceRole.objects.all():
        #     if obj.picture is not None:
        #         self.move(record=obj, to_subdir="LUT_PermanenceRole", size="S")
        for product in Product.objects.all():
            if product.picture is not None:
                self.move(record=product, to_subdir="product" + os.sep + str(product.producer.id), size="M")
            for obj in OfferItem.objects.filter(product_id=product.id).order_by():
                obj.picture2 = product.picture2
                obj.save()

    def move(self, record=None, to_subdir=None, size="M"):
        directory = "%s/%s" % (settings.MEDIA_ROOT, to_subdir)
        if not os.path.exists(directory):
            os.makedirs(directory, 0755)
        file_ = record.picture.file_ptr.file
        file_name, extension = os.path.splitext(rsplit(file_.name, os.sep, 1)[1])
        safe_name = '{0}{1}'.format(slugify(file_name), extension)
        name = os.path.join(to_subdir, safe_name)
        if default_storage.exists(name):
            default_storage.delete(name)
        image = Image.open(file_)
        if size == "XS":
            size = (48, 48)
            path = self.resize(image, name, size)
        else:
            # size = "M"
            size = (225, 225)
            path = self.resize(image, name, size)
        record.picture2 = path
        record.save()

    def resize(self, image, name, size):
        if image.size[0] > size[0] or image.size[1] > size[1]:
            new_mode = 'RGB'
            if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                # image is transparent
                if image.mode != 'RGBA':
                    image = image.convert('RGBA')
                base = Image.new('RGBA', image.size, '#fff')
                base.paste(image, mask=image)
                image = base
            if image.mode != new_mode:
                image = image.convert(new_mode)
            image.thumbnail(size, resample=Image.ANTIALIAS)
            image_resized = IO()
            image.save(image_resized, 'jpeg')
            path = default_storage.save(name, image_resized)
        else:
            path = default_storage.save(name, image.fp)
        return path
