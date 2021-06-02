from django import template
from django.contrib.admin.views.main import (
    PAGE_VAR, )
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

DOT = '…'


@register.simple_tag
def repanier_admin_paginator_number(cl, i):
    """
    Generate an individual page index link in a paginated list.
    """
    if i == DOT:
        return '… '
    else:
        if i == cl.page_num:
            # return format_html('<span class="this-page">{}</span> ', i + 1)
            return format_html(
                '<a class="repanier-a-cancel-selected" href="{}"{}>{}</a> ',
                cl.get_query_string({PAGE_VAR: i}),
                mark_safe(' class="end"' if i == cl.paginator.num_pages - 1 else ''),
                i,
            )
        else:
            return format_html(
                # '<a href="{}"{}>{}</a> ',
                '<a class="repanier-a-cancel" href="{}"{}>{}</a> ',
                cl.get_query_string({PAGE_VAR: i}),
                mark_safe(' class="end"' if i == cl.paginator.num_pages - 1 else ''),
                i,
            )


@register.filter
def verbose_name(obj):
    return obj._meta.verbose_name


@register.filter
def verbose_name_plural(obj):
    return obj._meta.verbose_name_plural