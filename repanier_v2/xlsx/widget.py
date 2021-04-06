import datetime

from django.utils.encoding import smart_str
from import_export.widgets import (
    CharWidget,
    ForeignKeyWidget,
    DecimalWidget,
    ManyToManyWidget,
    BooleanWidget,
    Widget,
)

from repanier_v2.const import *


class DecimalBooleanWidget(BooleanWidget):
    """
    Widget for converting boolean fields.
    """

    TRUE_VALUES = ["1", 1, DECIMAL_ONE, 1.0]
    FALSE_VALUE = "0"

    def clean(self, value, row=None, *args, **kwargs):
        if value == EMPTY_STRING:
            return
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
            return
        return Decimal(value).quantize(decimals)

    def render_quantize(self, value, decimals):
        return float(Decimal(value).quantize(decimals))


class IdWidget(DecimalsWidget):
    """
    Widget for converting id fields with 0 decimals or empty content.
    """

    def clean(self, value, row=None, *args, **kwargs):
        if self.is_empty(value):
            return None
        try:
            return Decimal(value).quantize(ZERO_DECIMAL)
        except InvalidOperation:
            # This occurs when text is present in a decimal field
            return None

    def render(self, value, obj=None):
        return super().render_quantize(value, ZERO_DECIMAL)


class ZeroDecimalsWidget(DecimalsWidget):
    """
    Widget for converting decimal price fields with 0 decimals.
    """

    def clean(self, value, row=None, *args, **kwargs):
        return super().clean_quantize(value, ZERO_DECIMAL)

    def render(self, value, obj=None):
        return super().render_quantize(value, ZERO_DECIMAL)


class TwoDecimalsWidget(DecimalsWidget):
    """
    Widget for converting decimal price fields with 2 decimals.
    """

    def clean(self, value, row=None, *args, **kwargs):
        return super().clean_quantize(value, TWO_DECIMALS)

    def render(self, value, obj=None):
        return super().render_quantize(value, TWO_DECIMALS)


class ThreeDecimalsWidget(DecimalsWidget):
    """
    Widget for converting decimal price fields with 3 decimals.
    """

    def clean(self, value, row=None, *args, **kwargs):
        return super().clean_quantize(value, THREE_DECIMALS)

    def render(self, value, obj=None):
        return super().render_quantize(value, THREE_DECIMALS)


class FourDecimalsWidget(DecimalsWidget):
    """
    Widget for converting decimal price fields with 4 decimals.
    """

    def clean(self, value, row=None, *args, **kwargs):
        return super().clean_quantize(value, FOUR_DECIMALS)

    def render(self, value, obj=None):
        return super().render_quantize(value, FOUR_DECIMALS)


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
        return super().clean_quantize(value, TWO_DECIMALS)

    def render(self, value, obj=None):
        return super().render_quantize(value, TWO_DECIMALS)


class TranslatedForeignKeyWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if value:
            target = (
                self.model.objects.filter(
                    **{"translations__{}".format(self.field): value}
                )
                .order_by("?")
                .first()
            )
            if target is not None:
                return target
            else:
                target = self.model.objects.create(**{"{}".format(self.field): value})
                return target
        else:
            return


class ProducerNameWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if value:
            value = ("{}".format(value)).strip()
            target = (
                self.model.objects.filter(**{"{}".format(self.field): value})
                .order_by("?")
                .first()
            )
            if target is None:
                target = (
                    self.model.objects.filter(**{"bank_account": value})
                    .order_by("?")
                    .first()
                )
            return target
        else:
            return


class CustomerNameWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if value:
            value = ("{}".format(value)).strip()
            target = (
                self.model.objects.filter(**{"{}".format(self.field): value})
                .order_by("?")
                .first()
            )
            if target is None:
                target = (
                    self.model.objects.filter(**{"bank_account1": value})
                    .order_by("?")
                    .first()
                )
                if target is None:
                    target = (
                        self.model.objects.filter(**{"bank_account2": value})
                        .order_by("?")
                        .first()
                    )
            return target
        else:
            return


class TranslatedManyToManyWidget(ManyToManyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return self.model.objects.none()
        result = []
        if value:
            array_values = value.split(self.separator)
            for v in array_values:
                add_this = (
                    self.model.objects.filter(
                        **{"translations__{}".format(self.field): v}
                    )
                    .order_by("?")
                    .first()
                )
                if add_this is None:
                    add_this = self.model.objects.create(**{"{}".format(self.field): v})
                result.append(add_this)
        return result

    def render(self, array_values, obj=None):
        ids = [smart_str(getattr(obj, self.field)) for obj in array_values.all()]
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
        super().__init__()

    def clean(self, value, row=None, *args, **kwargs):
        val = super().clean(value)
        return self.lut_reverse[val] if val else None

    def render(self, value, obj=None):
        if value is None:
            return EMPTY_STRING
        return "{}".format(self.lut_dict[value] if value else None)


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
            self.model.objects.filter(**{self.field: value})
            .order_by("?")
            .only(self.field)
            .first()
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
        for fmt in settings.DJANGO_SETTINGS_DATETIME:
            try:
                return datetime.datetime.strptime(value, fmt).date()
            except (ValueError, TypeError):
                continue
        raise ValueError("Enter a valid date.")

    def render(self, value, obj=None):
        if not value:
            return EMPTY_STRING
        return value


class HTMLWidget(CharWidget):
    """
    Widget for converting HTML Field.
    """

    def clean(self, value, row=None, *args, **kwargs):
        if value:
            return ("{}".format(value)).strip()
        else:
            return EMPTY_STRING

    def render(self, value, obj=None):
        if value is None:
            return EMPTY_STRING
        return value.encode("utf-8").decode("utf-8")
