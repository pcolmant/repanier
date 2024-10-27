import datetime

from django.utils.html import strip_tags
from import_export.widgets import (
    CharWidget,
    ForeignKeyWidget,
    DecimalWidget,
    BooleanWidget,
    Widget,
    IntegerWidget,
)
from repanier.const import *


class DecimalBooleanWidget(BooleanWidget):
    """
    Widget for converting boolean fields.
    """

    TRUE_VALUES = ["1", 1, DECIMAL_ONE, 1.0, True]
    FALSE_VALUE = "0"

    def clean(self, value, row=None, *args, **kwargs):
        if value == EMPTY_STRING:
            return
        return True if value in self.TRUE_VALUES else False

    def render(self, value, obj=None):
        if value is None:
            return EMPTY_STRING
        return value


class DecimalsWidget(DecimalWidget):
    """
    Widget for converting decimal rounded.
    """

    def clean_quantize(self, value, decimals):
        if self.is_empty(value):
            return DECIMAL_ZERO
        try:
            return Decimal(value).quantize(decimals)
        except InvalidOperation:
            # This occurs when text is present in a decimal field
            return DECIMAL_ZERO

    def render_quantize(self, value, decimals):
        value = self.clean_quantize(value, decimals)
        return float(Decimal(value).quantize(decimals))



class ZeroDecimalsWidget(DecimalsWidget):
    """
    Widget for converting decimal price fields with 0 decimals.
    """

    def clean(self, value, row=None, *args, **kwargs):
        return super().clean_quantize(value, RoundUpTo.ZERO_DECIMAL)

    def render(self, value, obj=None):
        return super().render_quantize(value, RoundUpTo.ZERO_DECIMAL)


class TwoDecimalsWidget(DecimalsWidget):
    """
    Widget for converting decimal price fields with 2 decimals.
    """

    def clean(self, value, row=None, *args, **kwargs):
        return super().clean_quantize(value, RoundUpTo.TWO_DECIMALS)

    def render(self, value, obj=None):
        return super().render_quantize(value, RoundUpTo.TWO_DECIMALS)


class ThreeDecimalsWidget(DecimalsWidget):
    """
    Widget for converting decimal price fields with 3 decimals.
    """

    def clean(self, value, row=None, *args, **kwargs):
        return super().clean_quantize(value, RoundUpTo.THREE_DECIMALS)

    def render(self, value, obj=None):
        return super().render_quantize(value, RoundUpTo.THREE_DECIMALS)


class FourDecimalsWidget(DecimalsWidget):
    """
    Widget for converting decimal price fields with 4 decimals.
    """

    def clean(self, value, row=None, *args, **kwargs):
        return super().clean_quantize(value, RoundUpTo.FOUR_DECIMALS)

    def render(self, value, obj=None):
        return super().render_quantize(value, RoundUpTo.FOUR_DECIMALS)


class IdWidget(ZeroDecimalsWidget):
    """
    Widget for converting id fields with 0 decimals or empty content.
    """
    pass


class MoneysWidget(DecimalWidget):
    """
    Widget for converting decimal rounded.
    """

    def clean_quantize(self, value, decimals):
        if self.is_empty(value):
            return
        return Decimal(value).quantize(decimals)

    def render_quantize(self, value, decimals):
        return float(Decimal(value.amount).quantize(decimals))


class TwoMoneysWidget(MoneysWidget):
    """
    Widget for converting decimal price fields with 2 decimals.
    """

    def clean(self, value, row=None, *args, **kwargs):
        return super().clean_quantize(value, RoundUpTo.TWO_DECIMALS)

    def render(self, value, obj=None):
        return super().render_quantize(value, RoundUpTo.TWO_DECIMALS)


class ProducerNameWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if value:
            value = ("{}".format(value)).strip()
            target = self.model.objects.filter(
                **{"{}".format(self.field): value}
            ).first()
            if target is None:
                target = self.model.objects.filter(**{"bank_account": value}).first()
            return target
        else:
            return


class CustomerNameWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if value:
            value = ("{}".format(value)).strip()
            target = self.model.objects.filter(
                **{"{}".format(self.field): value}
            ).first()
            if target is None:
                target = self.model.objects.filter(**{"bank_account1": value}).first()
                if target is None:
                    target = self.model.objects.filter(
                        **{"bank_account2": value}
                    ).first()
            return target
        else:
            return


class TaxLevelWidget(DecimalWidget):
    """
    Widget for ``Choices`` which looks up related choices.

    Parameters:
        ``model`` should be the Model instance for this ForeignKey (required).
        ``field`` should be the lookup field on the related model.
    """

    def __init__(self, lut, lut_reverse, *args, **kwargs):
        self.lut_dict = dict(lut)
        self.lut_reverse = dict(lut_reverse)
        super().__init__()

    def clean(self, value, row=None, *args, **kwargs):
        val = super().clean(value)
        return self.lut_reverse[val] if val else self.lut_reverse[DECIMAL_ZERO]

    def render(self, value, obj=None):
        if value:
            return self.lut_dict[value]
        return DECIMAL_ZERO


class OrderUnitWidget(IntegerWidget):
    def __init__(self, lut, default_value, *args, **kwargs):
        self.lut_dict = dict(lut)
        self.default_value = default_value
        super().__init__()

    def clean(self, value, row=None, *args, **kwargs):
        val = str(super().clean(value))
        return val if val in self.lut_dict else self.default_value

    def render(self, value, obj=None):
        return int(value) or int(self.default_value)


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

    def __init__(self, model, field="pk", **kwargs):
        super().__init__(model, field, **kwargs)

    def clean(self, value, row=None, *args, **kwargs):
        r = (
            self.model.objects.filter(**{self.field: value}).only(self.field).first()
            if value
            else None
        )
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

    def __init__(self, date_format=None):
        if date_format is None:
            if not settings.DATE_INPUT_FORMATS:
                formats = ("%Y-%m-%d",)
            else:
                formats = settings.DATE_INPUT_FORMATS
        else:
            formats = (date_format,)
        self.formats = formats

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return
        if isinstance(value, datetime.datetime):
            # Data comes from Excel
            return value.date()
        if isinstance(value, float):
            # Data comes from Excel
            return (
                datetime.datetime(1899, 12, 30) + datetime.timedelta(days=value)
            ).date()
        for date_format in self.formats:
            try:
                return datetime.datetime.strptime(value, date_format).date()
            except (ValueError, TypeError):
                continue
        raise ValueError("Enter a valid date.")

    def render(self, value, obj=None):
        if not value:
            return EMPTY_STRING
        if isinstance(value, str):
            value_as_date = datetime.datetime.strptime(
                value[:10], self.formats[0]
            ).date()
            return value_as_date.strftime(self.formats[0])
        return value.strftime(self.formats[0])


class HTMLWidget(CharWidget):
    """
    Widget for converting HTML Field.
    """

    def clean(self, value, row=None, *args, **kwargs):
        if value:
            return str(value).strip()
        else:
            return EMPTY_STRING

    def render(self, value, obj=None):
        # generate exported value
        if value is None:
            return EMPTY_STRING
        return strip_tags(value.strip().replace("\n", EMPTY_STRING))
