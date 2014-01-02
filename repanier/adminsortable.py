#-*- coding: utf-8 -*-
# Modified COPY OF django-admin-sortable2 / adminsortable / admin.py 
# Workaround following issues : 
# - Django CMS 3 compatibility, 
# - _reorder.admin_order_field is a class varialbe so it can't co-work with self.default_order_field
# - Removed "move to firs/last page" to limit the choices / the complexity to understand. 
# - Keep only "move to previous/next page" - only if those pages exists.
# - Renamed "move to previous/next page" by "move to top of previous/next page"
# - Adapted for multisite
# - Added : move for duplicate

import json
from django import VERSION
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.conf.urls import patterns, url
from django.core.exceptions import ImproperlyConfigured
from django.core.paginator import EmptyPage
from django.db import transaction
from django.db.models import Max, F
from django.forms.models import modelform_factory, inlineformset_factory, BaseInlineFormSet
from django.forms.widgets import HiddenInput
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib import admin


class SortableAdminBase(object):
    class Media:
        css = { 'all': ('adminsortable/css/sortable.css',) }
        js = (
            'adminsortable/js/plugins/admincompat.js',
            'adminsortable/js/libs/jquery.ui.core-1.10.3.js',
            'adminsortable/js/libs/jquery.ui.widget-1.10.3.js',
            'adminsortable/js/libs/jquery.ui.mouse-1.10.3.js',
            'adminsortable/js/libs/jquery.ui.sortable-1.10.3.js',
        )

class SortableAdminMixin(SortableAdminBase):
    PREV = 0
    NEXT = 1

    def __init__(self, model, admin_site):
        try:
            self.default_order_field = model._meta.ordering[0]
        except (AttributeError, IndexError):
            raise ImproperlyConfigured(u'Model %s.%s requires a list or tuple "ordering" in its Meta class'
                                       % (model.__module__, model.__name__))
        super(SortableAdminMixin, self).__init__(model, admin_site)
        if not isinstance(getattr(self, 'exclude', None), (list, tuple)):
            self.exclude = [self.default_order_field]
        elif not self.exclude or self.default_order_field != self.exclude[0]:
            self.exclude = [self.default_order_field] + self.exclude
        if not getattr(self, 'change_list_template', None):
            self.change_list_template = 'adminsortable/change_list.html'
        if not self.list_display_links:
            self.list_display_links = self.list_display[0]
        self.list_display = ['_reorder'] + list(self.list_display)
        self.Media.js += ('adminsortable/js/list-sortable.js',)

    def get_urls(self):
        my_urls = patterns('',
            url(r'^adminsortable_update/$', self.admin_site.admin_view(self.update), name='sortable_update'),
        )
        return my_urls + super(SortableAdminMixin, self).get_urls()

    def get_changelist(self, request, **kwargs):
        self.order_by = self.default_order_field
        if 'move_to_top_of_prev_page' in self.actions:
            self.actions.remove('move_to_top_of_prev_page')
        if 'move_to_top_of_next_page' in self.actions:
            self.actions.remove('move_to_top_of_next_page')
        objects = self.model.objects_without_filter.order_by(self.order_by)
        paginator = self.paginator(objects, self.list_per_page)
        page = paginator.page(int(request.REQUEST.get('p', 0)) + 1)
        if page.has_next():
            self.actions += ['move_to_top_of_next_page']
        if page.has_previous():
            self.actions += ['move_to_top_of_prev_page']
        return super(SortableAdminMixin, self).get_changelist(request, **kwargs)

    def _reorder(self, item):
        return '<div class="drag" order="{0}">&nbsp;</div>'.format(getattr(item, self.default_order_field))
    _reorder.short_description = _('Move')
    _reorder.allow_tags = True

    @csrf_exempt
    def update(self, request):
        if not request.is_ajax() or request.method != 'POST':
            return HttpResponseBadRequest('Not an XMLHttpRequest')
        if request.method != 'POST':
            return HttpResponseNotAllowed('Must be a POST request')
        if not self.has_change_permission(request):
            return HttpResponseForbidden('Missing permissions to perform this request')
        startorder = int(request.POST.get('startorder'))
        endorder = int(request.POST.get('endorder', 0))
        moved_items = list(self._move_item(request, startorder, endorder))
        return HttpResponse(json.dumps(moved_items, cls=DjangoJSONEncoder), content_type='application/json;charset=UTF-8')

    def save_model(self, request, obj, form, change):
        if not change:
            setattr(obj, self.default_order_field, self.get_max_order() + 1)
        obj.save()

    def move_to_top_of_prev_page(self, request, queryset):
        self._bulk_move(request, queryset, self.PREV)
    move_to_top_of_prev_page.short_description = _('Move selected to top of previous page')

    def move_to_top_of_next_page(self, request, queryset):
        self._bulk_move(request, queryset, self.NEXT)
    move_to_top_of_next_page.short_description = _('Move selected to top of next page')

    def move_for_duplicate(self, obj):
        startorder = getattr(obj, self.default_order_field)
        finalorder = self.get_max_order()
        print(startorder)
        print(finalorder)
        move_filter = {
            '%s__gte' % self.default_order_field: startorder,
            '%s__lte' % self.default_order_field: finalorder,
        }
        order_by = '-' + self.default_order_field
        move_update = { self.default_order_field: F(self.default_order_field) + 1 }
        with transaction.commit_on_success():
            self.model.objects_without_filter.filter(**move_filter).order_by(order_by).update(**move_update)
        return

    def _move_item(self, request, startorder, endorder):
        if startorder < endorder:
            finalorder = endorder
            move_filter = {
                '%s__gt' % self.default_order_field: startorder,
                '%s__lte' % self.default_order_field: finalorder,
            }
            order_by = self.default_order_field
            move_update = { self.default_order_field: F(self.default_order_field) - 1 }
        elif startorder > endorder + 1:
            finalorder = endorder + 1
            move_filter = {
                '%s__gte' % self.default_order_field: finalorder,
                '%s__lt' % self.default_order_field: startorder,
            }
            order_by = '-' + self.default_order_field
            move_update = { self.default_order_field: F(self.default_order_field) + 1 }
        else:
            return self.model.objects_without_filter.none()
        with transaction.commit_on_success():
            obj = self.model.objects_without_filter.get(**{ self.default_order_field: startorder })
            setattr(obj, self.default_order_field, 0)
            obj.save()
            self.model.objects_without_filter.filter(**move_filter).order_by(order_by).update(**move_update)
            setattr(obj, self.default_order_field, finalorder)
            obj.save()
        query_set = self.model.objects_without_filter.filter(**move_filter).order_by(self.default_order_field).values_list('pk', self.default_order_field)
        return [dict(pk=pk, order=order) for pk, order in query_set]

    def get_max_order(self):
        max_order = self.model.objects_without_filter.aggregate(max_order=Max(self.default_order_field))['max_order'] or 0
        return max_order

    def _bulk_move(self, request, queryset, method):
        objects = self.model.objects_without_filter.order_by(self.order_by)
        paginator = self.paginator(objects, self.list_per_page)
        page = paginator.page(int(request.REQUEST.get('p', 0)) + 1)
        try:
            if method == self.PREV:
                page = paginator.page(page.previous_page_number())
                endorder = getattr(objects[page.start_index() - 1], self.default_order_field)
                direction = +1
            elif method == self.NEXT:
                page = paginator.page(page.next_page_number())
                endorder = getattr(objects[page.start_index() - 1], self.default_order_field) + queryset.count()
                queryset = queryset.reverse()
                direction = -1
            else:
                raise Exception('Invalid method')
        except EmptyPage:
            return
        endorder -= 1
        for obj in queryset:
            startorder = getattr(obj, self.default_order_field)
            self._move_item(request, startorder, endorder)
            endorder += direction


class CustomInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        try:
            self.default_order_field = self.model._meta.ordering[0]
        except (AttributeError, IndexError):
            raise ImproperlyConfigured(u'Model %s.%s requires a list or tuple "ordering" in its Meta class'
                                       % (self.model.__module__, self.model.__name__))
        form = modelform_factory(self.model, widgets={ self.default_order_field: HiddenInput() })
        form.base_fields[self.default_order_field].is_hidden = True
        form.base_fields[self.default_order_field].required = False
        self.form = form
        super(CustomInlineFormSet, self).__init__(*args, **kwargs)

    def save_new(self, form, commit=True):
        """
        New objects do not have a valid value in their ordering field. On object save, add an order
        bigger than all other order fields for the current parent_model.
        """
        obj = super(CustomInlineFormSet, self).save_new(form, commit=False)
        if not isinstance(getattr(obj, self.default_order_field, None), int):
            query_set = self.model.objects_without_filter.filter(**{ self.fk.get_attname(): self.instance.pk })
            max_order = query_set.aggregate(max_order=Max(self.default_order_field))['max_order'] or 0
            setattr(obj, self.default_order_field, max_order + 1)
        if commit:
            obj.save()
        # form.save_m2m() can be called via the formset later on if commit=False
        if commit and hasattr(form, 'save_m2m'):
            form.save_m2m()
        return obj


class SortableInlineAdminMixin(SortableAdminBase):
    def __init__(self, parent_model, admin_site):
        version = (VERSION[0] == 1 and VERSION[1] <= 5) and '1.5' or '1.6'
        if isinstance(self, admin.StackedInline):
            self.template = 'adminsortable/stacked-%s.html' % version
            self.Media.js += ('adminsortable/js/inline-sortable.js',)
        elif isinstance(self, admin.TabularInline):
            self.template = 'adminsortable/tabular-%s.html' % version
            self.Media.js += ('adminsortable/js/inline-sortable.js',)
        else:
            raise ImproperlyConfigured(u'Class %s.%s must also derive from admin.TabularInline or admin.StackedInline'
                                       % (self.__module__, self.__class__))
        self.Media.css['all'] += ('adminsortable/css/sortable.css',)
        super(SortableInlineAdminMixin, self).__init__(parent_model, admin_site)
        self.formset = inlineformset_factory(parent_model, self.model, formset=CustomInlineFormSet)
