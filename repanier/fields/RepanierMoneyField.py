# -*- coding: utf-8
from __future__ import unicode_literals

import sys
from decimal import *

from django.conf import settings
from django.db import models
from django.db.models.expressions import BaseExpression, Expression
from django.forms import DecimalField, NumberInput
from django.forms.utils import flatatt
from django.utils.encoding import force_text, python_2_unicode_compatible
from django.utils.html import format_html

import repanier.apps

DECIMAL_ZERO = Decimal('0')

PYTHON2 = sys.version_info[0] == 2


# class RepanierMoneyComparisonError(TypeError):
#     # This exception was needed often enough to merit its own
#     # Exception class.
#
#     def __init__(self, other):
#         assert not isinstance(other, RepanierMoney)
#         self.other = other
#
#     def __str__(self):
#         # Note: at least w/ Python 2.x, use __str__, not __unicode__.
#         return "Cannot compare instances of RepanierMoney and %s" \
#                % self.other.__class__.__name__


@python_2_unicode_compatible
class RepanierMoney(object):
    def __init__(self, amount=DECIMAL_ZERO, decimal_places=2):
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        self.decimal_places = decimal_places
        self.rounding = Decimal('10') ** -self.decimal_places  # 2 places --> '0.01'
        self.amount = amount.quantize(self.rounding, ROUND_HALF_UP)

    def __float__(self):
        return float(self.amount)

    def __repr__(self):
        return "%s %d" % (self.amount, self.decimal_places)

    def __pos__(self):
        return RepanierMoney(amount=self.amount, decimal_places=self.decimal_places)

    def __neg__(self):
        return RepanierMoney(amount=-self.amount, decimal_places=self.decimal_places)

    def __add__(self, other):
        if isinstance(other, RepanierMoney):
            return RepanierMoney(amount=self.amount + other.amount, decimal_places=self.decimal_places)
        else:
            return RepanierMoney(amount=self.amount + other, decimal_places=self.decimal_places)

    def __sub__(self, other):
        return self.__add__(-other)

    def __mul__(self, other):
        if isinstance(other, RepanierMoney):
            return RepanierMoney(amount=self.amount * other.amount, decimal_places=self.decimal_places)
        else:
            return RepanierMoney(amount=self.amount * other, decimal_places=self.decimal_places)

    def __truediv__(self, other):
        if isinstance(other, RepanierMoney):
            return RepanierMoney(amount=self.amount / other.amount, decimal_places=self.decimal_places)
        else:
            return RepanierMoney(amount=self.amount / other, decimal_places=self.decimal_places)

    def __abs__(self):
        return RepanierMoney(amount=abs(self.amount), decimal_places=self.decimal_places)

    # def __bool__(self):
    #     return bool(self.amount)
    #
    # if PYTHON2:
    #     __nonzero__ = __bool__

    def __rmod__(self, other):
        """
        Calculate percentage of an amount.  The left-hand side of the
        operator must be a numeric value.

        Example:
        >>> money = RepanierMoney(200)
        >>> 5 % money
        USD 10.00
        """
        if isinstance(other, RepanierMoney):
            raise TypeError('Invalid __rmod__ operation')
        else:
            return RepanierMoney(amount=Decimal(self.amount * (other / 100)), decimal_places=self.decimal_places)

    __radd__ = __add__

    def __rsub__(self, other):
        if isinstance(other, RepanierMoney):
            return RepanierMoney(amount=other.amount - self.amount, decimal_places=self.decimal_places)
        else:
            return RepanierMoney(amount=other - self.amount, decimal_places=self.decimal_places)

    __rmul__ = __mul__
    __rtruediv__ = __truediv__

    # _______________________________________
    # Override comparison operators
    def __eq__(self, other):
        return (isinstance(other, RepanierMoney)
                and (self.amount == other.amount)) or self.amount == other

    def __ne__(self, other):
        result = self.__eq__(other)
        return not result

    def __lt__(self, other):
        return (isinstance(other, RepanierMoney)
                and (self.amount < other.amount)) or self.amount < other

    def __gt__(self, other):
        return (isinstance(other, RepanierMoney)
                and (self.amount > other.amount)) or self.amount > other

    def __le__(self, other):
        return self < other or self == other

    def __ge__(self, other):
        return self.amount > other or self == other

    def __str__(self):
        negative, digits, e = self.amount.as_tuple()
        result = []
        digits = list(map(str, digits))
        build, next = result.append, digits.pop

        # Suffix currency
        if repanier.apps.REPANIER_SETTINGS_AFTER_AMOUNT:
            build(" %s" % repanier.apps.REPANIER_SETTINGS_CURRENCY_DISPLAY)

        # Decimals
        for i in range(self.decimal_places):
            build(next() if digits else '0')

        # Decimal points
        if self.decimal_places:
            build(settings.DECIMAL_SEPARATOR)

        # Grouped number
        if not digits:
            build('0')
        else:
            i = 0
            while digits:
                build(next())
                i += 1
                if i == settings.NUMBER_GROUPING and digits:
                    i = 0
                    build(settings.THOUSAND_SEPARATOR)

        # Prefix sign
        if negative:
            build("- ")

        # Prefix currency
        if not repanier.apps.REPANIER_SETTINGS_AFTER_AMOUNT:
            build("%s " % repanier.apps.REPANIER_SETTINGS_CURRENCY_DISPLAY)
        return u''.join(reversed(result))

    def as_tuple(self):
        """Represents the number as a triple tuple.

        To show the internals exactly as they are.
        """
        return self.amount.as_tuple()


class MoneyFieldProxy(object):
    def __init__(self, field):
        self.field = field

    def _money_from_obj(self, obj):
        amount = obj.__dict__[self.field.name]
        if amount is None:
            return
        return RepanierMoney(amount=amount, decimal_places=self.field.decimal_places)

    def __get__(self, obj, type=None):
        if obj is None:
            raise AttributeError('Can only be accessed via an instance.')
        if isinstance(obj.__dict__[self.field.name], BaseExpression):
            return obj.__dict__[self.field.name]
        if not isinstance(obj.__dict__[self.field.name], RepanierMoney):
            obj.__dict__[self.field.name] = self._money_from_obj(obj)
        return obj.__dict__[self.field.name]

    def __set__(self, obj, value):
        if isinstance(value, tuple):
            value = RepanierMoney(amount=value[0], decimal_places=self.field.decimal_places)
        if isinstance(value, RepanierMoney):
            obj.__dict__[self.field.name] = value.amount
        elif isinstance(value, BaseExpression):
            obj.__dict__[self.field.name] = value
        else:
            if value:
                value = str(value)
            obj.__dict__[self.field.name] = self.field.to_python(value)


class ModelMoneyField(models.DecimalField):
    def formfield(self, **kwargs):
        defaults = {'form_class': FormMoneyField}
        defaults.update(kwargs)
        return super(ModelMoneyField, self).formfield(**defaults)

    def to_python(self, value):
        if isinstance(value, Expression):
            return value
        if isinstance(value, RepanierMoney):
            value = value.amount
        if isinstance(value, tuple):
            value = value[0]
        return super(ModelMoneyField, self).to_python(value)

    def get_db_prep_save(self, value, connection):
        if isinstance(value, Expression):
            return value
        if isinstance(value, RepanierMoney):
            value = value.amount
        return super(ModelMoneyField, self).get_db_prep_save(value, connection)

    def contribute_to_class(self, cls, name):
        super(ModelMoneyField, self).contribute_to_class(cls, name)
        setattr(cls, self.name, MoneyFieldProxy(self))


class MoneyInput(NumberInput):

    def render(self, name, value, attrs=None):
        if value is None:
            value = ''
        final_attrs = self.build_attrs(attrs, type=self.input_type, name=name)
        if value != '':
            # Only add the 'value' attribute if a value is non-empty.
            final_attrs['value'] = force_text(self._format_value(value))
        if repanier.apps.REPANIER_SETTINGS_AFTER_AMOUNT:
            return format_html('<input{} />&nbsp;{}', flatatt(final_attrs), repanier.apps.REPANIER_SETTINGS_CURRENCY_DISPLAY)
        else:
            return format_html('{}&nbsp;<input{} />', repanier.apps.REPANIER_SETTINGS_CURRENCY_DISPLAY, flatatt(final_attrs))


class FormMoneyField(DecimalField):
    widget = MoneyInput

    def to_python(self, value):
        # Important : Do not validate if self.disabled
        value = (not self.disabled and super(FormMoneyField, self).to_python(value)) or DECIMAL_ZERO
        return RepanierMoney(value)

    def prepare_value(self, value):
        try:
            return value.amount
        except:
            return value

    # def validate(self, value):
    #     super(DecimalField, self).validate(value)
    #     if value in self.empty_values or not self.required:
    #         return
    #     # Check for NaN, Inf and -Inf values. We can't compare directly for NaN,
    #     # since it is never equal to itself. However, NaN is the only value that
    #     # isn't equal to itself, so we can use this to identify NaN
    #     if value != value or value == Decimal("Inf") or value == Decimal("-Inf"):
    #         raise ValidationError(self.error_messages['invalid'], code='invalid')
    #     sign, digittuple, exponent = value.amount.as_tuple()
    #     decimals = abs(exponent)
    #     # digittuple doesn't include any leading zeros.
    #     digits = len(digittuple)
    #     if decimals > digits:
    #         # We have leading zeros up to or past the decimal point.  Count
    #         # everything past the decimal point as a digit.  We do not count
    #         # 0 before the decimal point as a digit since that would mean
    #         # we would not allow max_digits = decimal_places.
    #         digits = decimals
    #     whole_digits = digits - decimals
    #
    #     if self.max_digits is not None and digits > self.max_digits:
    #         raise ValidationError(
    #             self.error_messages['max_digits'],
    #             code='max_digits',
    #             params={'max': self.max_digits},
    #         )
    #     if self.decimal_places is not None and decimals > self.decimal_places:
    #         raise ValidationError(
    #             self.error_messages['max_decimal_places'],
    #             code='max_decimal_places',
    #             params={'max': self.decimal_places},
    #         )
    #     if (self.max_digits is not None and self.decimal_places is not None
    #         and whole_digits > (self.max_digits - self.decimal_places)):
    #         raise ValidationError(
    #             self.error_messages['max_whole_digits'],
    #             code='max_whole_digits',
    #             params={'max': (self.max_digits - self.decimal_places)},
    #         )
    #     return value
