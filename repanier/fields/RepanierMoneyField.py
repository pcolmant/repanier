from decimal import Decimal, ROUND_HALF_UP

import repanier.apps
from django.conf import settings
from django.db import models
from django.db.models.expressions import BaseExpression, Expression
from django.forms import DecimalField
from repanier.widget.money import RepanierMoneyWidget

DECIMAL_ZERO = Decimal("0")


class RepanierMoney(object):
    def __init__(self, amount=DECIMAL_ZERO, decimal_places=2):
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        self.decimal_places = decimal_places
        self.rounding = Decimal("10") ** -self.decimal_places  # 2 places --> '0.01'
        self.amount = amount.quantize(self.rounding, ROUND_HALF_UP)

    def get_as_str(self, with_currency=True):
        negative, digits, e = self.amount.as_tuple()
        result = []
        digits = list(map(str, digits))
        build, next = result.append, digits.pop

        # Suffix currency
        if with_currency:
            if repanier.apps.REPANIER_SETTINGS_AFTER_AMOUNT:
                build(" {}".format(repanier.apps.REPANIER_SETTINGS_CURRENCY_DISPLAY))

        # Decimals
        for i in range(self.decimal_places):  # noqa
            build(next() if digits else "0")

        # Decimal points
        if self.decimal_places:
            build(settings.DECIMAL_SEPARATOR)

        # Grouped number
        if not digits:
            build("0")
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
        if with_currency:
            if not repanier.apps.REPANIER_SETTINGS_AFTER_AMOUNT:
                build("{}".format(repanier.apps.REPANIER_SETTINGS_CURRENCY_DISPLAY))

        return "".join(reversed(result))

    def __float__(self):
        return float(self.amount)

    def __repr__(self):
        return "{} {}".format(self.amount, self.decimal_places)

    def __pos__(self):
        return RepanierMoney(amount=self.amount, decimal_places=self.decimal_places)

    def __neg__(self):
        return RepanierMoney(amount=-self.amount, decimal_places=self.decimal_places)

    def __add__(self, other):
        if isinstance(other, RepanierMoney):
            return RepanierMoney(
                amount=self.amount + other.amount, decimal_places=self.decimal_places
            )
        else:
            return RepanierMoney(
                amount=self.amount + other, decimal_places=self.decimal_places
            )

    def __sub__(self, other):
        return self.__add__(-other)

    def __mul__(self, other):
        if isinstance(other, RepanierMoney):
            return RepanierMoney(
                amount=self.amount * other.amount, decimal_places=self.decimal_places
            )
        else:
            return RepanierMoney(
                amount=self.amount * other, decimal_places=self.decimal_places
            )

    def __truediv__(self, other):
        if isinstance(other, RepanierMoney):
            return RepanierMoney(
                amount=self.amount / other.amount, decimal_places=self.decimal_places
            )
        else:
            return RepanierMoney(
                amount=self.amount / other, decimal_places=self.decimal_places
            )

    def __abs__(self):
        return RepanierMoney(
            amount=abs(self.amount), decimal_places=self.decimal_places
        )

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
            raise TypeError("Invalid __rmod__ operation")
        else:
            return RepanierMoney(
                amount=Decimal(self.amount * (other / 100)),
                decimal_places=self.decimal_places,
            )

    __radd__ = __add__

    def __rsub__(self, other):
        if isinstance(other, RepanierMoney):
            return RepanierMoney(
                amount=other.amount - self.amount, decimal_places=self.decimal_places
            )
        else:
            return RepanierMoney(
                amount=other - self.amount, decimal_places=self.decimal_places
            )

    __rmul__ = __mul__
    __rtruediv__ = __truediv__

    # _______________________________________
    # Override comparison operators
    def __eq__(self, other):
        return (
                       isinstance(other, RepanierMoney) and (self.amount == other.amount)
               ) or self.amount == other

    def __ne__(self, other):
        result = self.__eq__(other)
        return not result

    def __lt__(self, other):
        return (
                       isinstance(other, RepanierMoney) and (self.amount < other.amount)
               ) or self.amount < other

    def __gt__(self, other):
        return (
                       isinstance(other, RepanierMoney) and (self.amount > other.amount)
               ) or self.amount > other

    def __le__(self, other):
        return self < other or self == other

    def __ge__(self, other):
        return self.amount > other or self == other

    def __str__(self):
        return self.get_as_str()

    def as_tuple(self):
        # Important : used by /django/core/validators.py
        return self.amount.as_tuple()

    def is_finite(self):
        # Important : used by /django/core/validators.py
        return self.amount.is_finite()


class ModelRepanierMoneyFieldProxy(object):
    def __init__(self, field):
        self.field = field

    def _money_from_obj(self, obj):
        amount = obj.__dict__[self.field.name]
        if amount is None:
            return
        return RepanierMoney(amount=amount, decimal_places=self.field.decimal_places)

    def __get__(self, obj, type=None):
        if obj is None:
            raise AttributeError("Can only be accessed via an instance.")
        if isinstance(obj.__dict__[self.field.name], BaseExpression):
            return obj.__dict__[self.field.name]
        if not isinstance(obj.__dict__[self.field.name], RepanierMoney):
            obj.__dict__[self.field.name] = self._money_from_obj(obj)
        return obj.__dict__[self.field.name]

    def __set__(self, obj, value):
        if isinstance(value, tuple):
            value = RepanierMoney(
                amount=value[0], decimal_places=self.field.decimal_places
            )
        if isinstance(value, RepanierMoney):
            obj.__dict__[self.field.name] = value.amount
        elif isinstance(value, BaseExpression):
            obj.__dict__[self.field.name] = value
        else:
            if value:
                value = str(value)
            obj.__dict__[self.field.name] = self.field.to_python(value)


class ModelMoneyField(models.DecimalField):
    # Replaced with ModelRepanierMoneyField
    pass


class ModelRepanierMoneyField(models.DecimalField):
    def formfield(self, **kwargs):
        kwargs.update({"form_class": FormRepanierMoneyField})
        return super().formfield(**kwargs)

    def to_python(self, value):
        if isinstance(value, Expression):
            return value
        if isinstance(value, RepanierMoney):
            value = value.amount
        if isinstance(value, tuple):
            value = value[0]
        return super().to_python(value)

    def get_db_prep_save(self, value, connection):
        if isinstance(value, Expression):
            return value
        if isinstance(value, RepanierMoney):
            value = value.amount
        return super().get_db_prep_save(value, connection)

    def contribute_to_class(self, cls, name, private_only=False):
        super().contribute_to_class(
            cls, name, private_only=private_only
        )
        setattr(cls, self.name, ModelRepanierMoneyFieldProxy(self))


class FormRepanierMoneyField(DecimalField):
    widget = RepanierMoneyWidget

    def __init__(self, *, max_value=None, min_value=None, max_digits=None, decimal_places=None, **kwargs):
        # Important : add "localize"
        super().__init__(max_value=max_value, min_value=min_value, max_digits=max_digits, decimal_places=decimal_places,
                         localize=True, **kwargs)

    def to_python(self, value):
        # Important : Do not validate if self.disabled
        value = (
                        not self.disabled and super().to_python(value)
                ) or DECIMAL_ZERO
        return RepanierMoney(value)

    def prepare_value(self, value):
        try:
            return value.amount
        except Exception:
            return value
