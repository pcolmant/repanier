# -*- coding: utf-8
from __future__ import unicode_literals
from django.utils.encoding import smart_bytes
from import_export.widgets import CharWidget, ForeignKeyWidget, DecimalWidget, ManyToManyWidget, \
    BooleanWidget
from repanier.const import *


class DecimalBooleanWidget(BooleanWidget):
    """
    Widget for converting boolean fields.
    """
    TRUE_VALUES = ["1", 1, DECIMAL_ONE, 1.0]


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

    def clean(self, value):
        if self.is_empty(value):
            return DECIMAL_ZERO
        return Decimal(value).quantize(ZERO_DECIMAL)

    def render(self, value):
        return super(IdWidget, self).render_quantize(value, ZERO_DECIMAL)


class ZeroDecimalsWidget(DecimalsWidget):
    """
    Widget for converting decimal price fields with 0 decimals.
    """

    def clean(self, value):
        return super(ZeroDecimalsWidget, self).clean_quantize(value, ZERO_DECIMAL)

    def render(self, value):
        return super(ZeroDecimalsWidget, self).render_quantize(value, ZERO_DECIMAL)


class TwoDecimalsWidget(DecimalsWidget):
    """
    Widget for converting decimal price fields with 2 decimals.
    """

    def clean(self, value):
        return super(TwoDecimalsWidget, self).clean_quantize(value, TWO_DECIMALS)

    def render(self, value):
        return super(TwoDecimalsWidget, self).render_quantize(value, TWO_DECIMALS)


class ThreeDecimalsWidget(DecimalsWidget):
    """
    Widget for converting decimal price fields with 3 decimals.
    """

    def clean(self, value):
        return super(ThreeDecimalsWidget, self).clean_quantize(value, THREE_DECIMALS)

    def render(self, value):
        return super(ThreeDecimalsWidget, self).render_quantize(value, THREE_DECIMALS)


class FourDecimalsWidget(DecimalsWidget):
    """
    Widget for converting decimal price fields with 4 decimals.
    """

    def clean(self, value):
        return super(FourDecimalsWidget, self).clean_quantize(value, FOUR_DECIMALS)

    def render(self, value):
        return super(FourDecimalsWidget, self).render_quantize(value, FOUR_DECIMALS)


class TranslatedForeignKeyWidget(ForeignKeyWidget):

    def clean(self, value):
        if value:
            target = self.model.objects.filter(**{"translations__%s" % self.field: value}).order_by().first()
            if target is not None:
                return target
            else:
                target = self.model.objects.create(**{"%s" % self.field: value})
                return target
        else:
            return None


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
        super(ChoiceWidget, self).__init__(*args, **kwargs)

    def clean(self, value):
        val = super(ChoiceWidget, self).clean(value)
        # print smart_bytes(val, encoding='utf-8', strings_only=False, errors='strict')
        return self.lut_reverse[val] if val else None

    def render(self, value):
        if value is None:
            return ""
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

    def clean(self, value):
        r = self.model.objects.filter(**{self.field: value}).order_by().only(self.field).first() if value else None
        if r is None and value is not None:
            r = self.model(**{self.field: value})
        return r

    def render(self, value):
        if value is None:
            return ""
        return getattr(value, self.field)
