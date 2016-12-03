# -*- coding: utf-8
from __future__ import unicode_literals

import datetime

from django.conf import settings
from django.utils import datetime_safe
from django.utils.encoding import smart_text
from import_export.widgets import CharWidget, ForeignKeyWidget, DecimalWidget, ManyToManyWidget, \
    BooleanWidget, Widget

from repanier.const import *


class DecimalBooleanWidget(BooleanWidget):
    """
    Widget for converting boolean fields.
    """
    TRUE_VALUES = ["1", 1, DECIMAL_ONE, 1.0]
    FALSE_VALUE = "0"

    def clean(self, value, row=None, *args, **kwargs):
        if value == EMPTY_STRING:
            return None
        return True if value in self.TRUE_VALUES else False

    def render(self, value, obj=None):
        if value is None:
            return EMPTY_STRING
        return self.TRUE_VALUES[0] if value else self.FALSE_VALUE


class DecimalsWidget(DecimalWidget):
    """
    Widget for converting decimal rounded.
    """

    def clean_quantize(self, value, decimals):
        if self.is_empty(value):
            return None
        return Decimal(value).quantize(decimals)

    def render_quantize(self, value, decimals):
        return float(Decimal(value).quantize(decimals))


class IdWidget(DecimalsWidget):
    """
    Widget for converting id fields with 0 decimals or empty content.
    """

    def clean(self, value, row=None, *args, **kwargs):
        if self.is_empty(value):
            return DECIMAL_ZERO
        return Decimal(value).quantize(ZERO_DECIMAL)

    def render(self, value, obj=None):
        return super(IdWidget, self).render_quantize(value, ZERO_DECIMAL)


class ZeroDecimalsWidget(DecimalsWidget):
    """
    Widget for converting decimal price fields with 0 decimals.
    """

    def clean(self, value, row=None, *args, **kwargs):
        return super(ZeroDecimalsWidget, self).clean_quantize(value, ZERO_DECIMAL)

    def render(self, value, obj=None):
        return super(ZeroDecimalsWidget, self).render_quantize(value, ZERO_DECIMAL)


class TwoDecimalsWidget(DecimalsWidget):
    """
    Widget for converting decimal price fields with 2 decimals.
    """

    def clean(self, value, row=None, *args, **kwargs):
        return super(TwoDecimalsWidget, self).clean_quantize(value, TWO_DECIMALS)

    def render(self, value, obj=None):
        return super(TwoDecimalsWidget, self).render_quantize(value, TWO_DECIMALS)


class ThreeDecimalsWidget(DecimalsWidget):
    """
    Widget for converting decimal price fields with 3 decimals.
    """

    def clean(self, value, row=None, *args, **kwargs):
        return super(ThreeDecimalsWidget, self).clean_quantize(value, THREE_DECIMALS)

    def render(self, value, obj=None):
        return super(ThreeDecimalsWidget, self).render_quantize(value, THREE_DECIMALS)


class FourDecimalsWidget(DecimalsWidget):
    """
    Widget for converting decimal price fields with 4 decimals.
    """

    def clean(self, value, row=None, *args, **kwargs):
        return super(FourDecimalsWidget, self).clean_quantize(value, FOUR_DECIMALS)

    def render(self, value, obj=None):
        return super(FourDecimalsWidget, self).render_quantize(value, FOUR_DECIMALS)


class MoneysWidget(DecimalWidget):
    """
    Widget for converting decimal rounded.
    """

    def clean_quantize(self, value, decimals):
        if self.is_empty(value):
            return None
        return Decimal(value).quantize(decimals)

    def render_quantize(self, value, decimals):
        return float(Decimal(value.amount).quantize(decimals))


class TwoMoneysWidget(MoneysWidget):
    """
    Widget for converting decimal price fields with 2 decimals.
    """

    def clean(self, value, row=None, *args, **kwargs):
        return super(TwoMoneysWidget, self).clean_quantize(value, TWO_DECIMALS)

    def render(self, value, obj=None):
        return super(TwoMoneysWidget, self).render_quantize(value, TWO_DECIMALS)


class TranslatedForeignKeyWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if value:
            target = self.model.objects.filter(**{"translations__%s" % self.field: value}).order_by('?').first()
            if target is not None:
                return target
            else:
                target = self.model.objects.create(**{"%s" % self.field: value})
                return target
        else:
            return None


class ProducerNameWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if value:
            value = ("%s" % value).strip()
            target = self.model.objects.filter(**{"%s" % self.field: value}).order_by('?').first()
            if target is None:
                target = self.model.objects.filter(**{"bank_account": value}).order_by('?').first()
            return target
        else:
            return None


class CustomerNameWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if value:
            value = ("%s" % value).strip()
            target = self.model.objects.filter(**{"%s" % self.field: value}).order_by('?').first()
            if target is None:
                target = self.model.objects.filter(**{"bank_account1": value}).order_by('?').first()
                if target is None:
                    target = self.model.objects.filter(**{"bank_account2": value}).order_by('?').first()
            return target
        else:
            return None


class TranslatedManyToManyWidget(ManyToManyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            # File "/home/pi/d2/local/lib/python2.7/site-packages/django/db/models/fields/related_descriptors.py", line 887, in set
            #   objs = tuple(objs)
            #   TypeError: 'NoneType' object is not iterable
            # value = " "
            return self.model.objects.none()
        result = []
        if value:
            array_values = value.split(self.separator)
            for v in array_values:
                add_this = self.model.objects.filter(**{"translations__%s" % self.field: v}).order_by('?').first()
                if add_this is None:
                    add_this = self.model.objects.create(**{"%s" % self.field: v})
                result.append(add_this)
        return result

    def render(self, array_values, obj=None):
        ids = [smart_text(getattr(obj, self.field)) for obj in array_values.all()]
        return self.separator.join(ids)


class ChoiceWidget(CharWidget):
    """
    Widget for ``Choices`` which looks up related choices.

    Parameters:
        ``model`` should be the Model instance for this ForeignKey (required).
        ``field`` should be the lookup field on the related model.
    """

    def __init__(self, lut, lut_reverse, *args, **kwargs):
        self.lut_dict = dict(lut)
        self.lut_reverse = dict(lut_reverse)
        super(ChoiceWidget, self).__init__()

    def clean(self, value, row=None, *args, **kwargs):
        val = super(ChoiceWidget, self).clean(value)
        return self.lut_reverse[val] if val else None

    def render(self, value, obj=None):
        if value is None:
            return EMPTY_STRING
        return "%s" % self.lut_dict[value] if value else None


class OneToOneWidget(ForeignKeyWidget):
    """
    Widget for ``OneToOneKey`` which looks up a related model.

    The lookup field defaults to using the primary key (``pk``), but
    can be customised to use any field on the related model.

    e.g. To use a lookup field other than ``pk``, rather than specifying a
    field in your Resource as ``class Meta: fields = ('author__name', ...)``,
    you would specify it in your Resource like so:

        class BookResource(resources.ModelResource):
            email = fields.Field(attribute='user', \
                widget=OneToOneWidget(User, 'email'))
            class Meta: fields = ('email', ...)

    This will allow you to use "natural keys" for both import and export.

    Parameters:
        ``model`` should be the Model instance for this ForeignKey (required).
        ``field`` should be the lookup field on the related model.
    """

    def __init__(self, model, field='pk', **kwargs):
        super(OneToOneWidget, self).__init__(model, field, **kwargs)

    def clean(self, value, row=None, *args, **kwargs):
        r = self.model.objects.filter(**{self.field: value}).order_by('?').only(self.field).first() if value else None
        if r is None and value is not None:
            r = self.model(**{self.field: value})
        return r

    def render(self, value, obj=None):
        if value is None:
            return EMPTY_STRING
        return getattr(value, self.field)


class DateWidgetExcel(Widget):
    """
    Widget for converting date fields.

    Takes optional ``format`` parameter.
    """

    def __init__(self, format=None):
        if format is None:
            if not settings.DATE_INPUT_FORMATS:
                formats = ("%Y-%m-%d",)
            else:
                formats = settings.DATE_INPUT_FORMATS
        else:
            formats = (format,)
        self.formats = formats

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        if isinstance(value, datetime.datetime):
            # Data comes from Excel
            return value.date()
        if isinstance(value, float):
            # Data comes from Excel
            return (datetime.datetime(1899, 12, 30) + datetime.timedelta(days=value)).date()
        for format in self.formats:
            try:
                return datetime.datetime.strptime(value, format).date()
            except (ValueError, TypeError):
                continue
        raise ValueError("Enter a valid date.")

    def render(self, value, obj=None):
        if not value:
            return ""
        try:
            return value.strftime(self.formats[0])
        except:
            return datetime_safe.new_date(value).strftime(self.formats[0])
