from django.core.cache import cache
from django.utils.translation import ugettext_lazy as _


class InlineForeignKeyCacheMixin(object):
    """
    Cache foreignkey choices in the request object to prevent unnecessary queries.
    """

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        cache_key = "repanier_field{}".format(db_field.name)
        cache_value = cache.get(cache_key)
        if cache_value is not None:
            formfield.choices = cache_value
        else:
            # Optimize to not execute the query on each row
            choices = [(None, _("---------"))]
            for obj in kwargs["queryset"]:
                choices.append((obj.id, str(obj)))
            formfield.choices = choices
            cache.set(cache_key, choices, 300)
        return formfield
