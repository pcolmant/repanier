# -*- coding: utf-8


class InlineForeignKeyCacheMixin(object):
    """
    Cache foreignkey choices in the request object to prevent unnecessary queries.
    """

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super(InlineForeignKeyCacheMixin, self).formfield_for_foreignkey(db_field, request, **kwargs)
        # Optimize to not execute the query on each row
        choices = []
        for obj in kwargs["queryset"]:
            choices.append((obj.id, str(obj)))
        formfield.choices = choices
        return formfield
