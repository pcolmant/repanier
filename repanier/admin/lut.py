# -*- coding: utf-8

from django import forms
from django.conf import settings
from django.contrib.admin import TabularInline
from django.utils.translation import ugettext_lazy as _, get_language_info
from django_mptt_admin.admin import DjangoMpttAdmin
from easy_select2 import apply_select2
from parler.admin import TranslatableAdmin
from parler.forms import TranslatableModelForm

from repanier.admin.inline_foreign_key_cache_mixin import InlineForeignKeyCacheMixin
from repanier.const import PERMANENCE_CLOSED, ONE_LEVEL_DEPTH, TWO_LEVEL_DEPTH
from repanier.models.customer import Customer
from repanier.models.permanence import Permanence
from repanier.models.permanenceboard import PermanenceBoard


class LUTDataForm(TranslatableModelForm):
    def __init__(self, *args, **kwargs):
        super(LUTDataForm, self).__init__(*args, **kwargs)

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return

        if self.instance.id is None:
            if self.language_code != settings.LANGUAGE_CODE:
                # Important to also prohibit untranslated instance in settings.LANGUAGE_CODE
                self.add_error(
                    'short_name',
                    _('Please define first a short_name in %(language)s') % {
                        'language': get_language_info(settings.LANGUAGE_CODE)['name_local']})


class LUTAdmin(TranslatableAdmin, DjangoMpttAdmin):
    form = LUTDataForm
    list_display = ('__str__', 'is_active')
    list_display_links = ('__str__',)
    mptt_level_indent = 20
    mptt_indent_field = "__str__"
    mptt_level_limit = None

    def has_delete_permission(self, request, obj=None):
        user = request.user
        if user.is_order_manager or user.is_invoice_manager or user.is_coordinator:
            return True
        return False

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def has_change_permission(self, request, staff=None):
        return self.has_delete_permission(request)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Overrides parent class formfield_for_foreignkey method."""
        # If mptt_level_limit is set filter levels depending on the limit.
        if db_field.name == "parent" and self.mptt_level_limit is not None:
            kwargs["queryset"] = self.model.objects.filter(level__lt=self.mptt_level_limit)
        return super(LUTAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    def do_move(self, instance, position, target_instance):
        """
        Overwritting parent do_move method to disallow users to exceed the self.mptt_level_limit value when drag and
        dropping items.
        """
        if self.mptt_level_limit is not None:
            if position == "inside":
                if target_instance.level >= self.mptt_level_limit:
                    raise Exception(_("The maximum level for this model is {}".format(self.mptt_level_limit)))
            else:
                if target_instance.level > self.mptt_level_limit:
                    raise Exception(_("The maximum level for this model is {}".format(self.mptt_level_limit)))
        super(LUTAdmin, self).do_move(instance, position, target_instance)

    def get_queryset(self, request):
        qs = super(LUTAdmin, self).get_queryset(request)
        qs = qs.filter(
            # Important to also display untranslated produts : translations__language_code=settings.LANGUAGE_CODE
            translations__language_code=settings.LANGUAGE_CODE
        )
        return qs


class LUTProductionModeAdmin(LUTAdmin):
    mptt_level_limit = TWO_LEVEL_DEPTH

    def get_fields(self, request, obj=None):
        fields = [
            'parent',
            'short_name',
            'picture2',
            'is_active'
        ]
        return fields


class LUTDeliveryPointAdmin(LUTAdmin):
    mptt_level_limit = ONE_LEVEL_DEPTH

    def get_fields(self, request, obj=None):
        fields = [
            'parent',
            'short_name',
            'is_active',
            ('transport', 'min_transport')
        ]
        return fields

    def get_queryset(self, request):
        qs = super(LUTDeliveryPointAdmin, self).get_queryset(request)
        qs = qs.filter(
            customer_responsible__isnull=True,
        )
        return qs

    def filter_tree_queryset(self, qs, request):
        # https://github.com/mbraak/django-mptt-admin/issues/47
        return qs.filter(
            customer_responsible__isnull=True,
        )


class LUTDepartmentForCustomerAdmin(LUTAdmin):
    mptt_level_limit = TWO_LEVEL_DEPTH

    def get_fields(self, request, obj=None):
        fields = [
            'parent',
            'short_name',
            'is_active',
        ]
        return fields


class PermanenceBoardInlineForm(forms.ModelForm):
    class Meta:
        widgets = {
            'permanence': apply_select2(forms.Select),
            'customer': apply_select2(forms.Select),
        }


class PermanenceBoardInline(InlineForeignKeyCacheMixin, TabularInline):
    form = PermanenceBoardInlineForm

    model = PermanenceBoard
    extra = 1

    def get_fields(self, request, obj=None):
        fields = [
            'permanence',
            'customer'
        ]
        return fields

    def get_queryset(self, request):
        return super(PermanenceBoardInline, self).get_queryset(request).filter(
            permanence__status__lte=PERMANENCE_CLOSED)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "customer":
            kwargs["queryset"] = Customer.objects.filter(may_order=True)
        if db_field.name == "permanence":
            kwargs["queryset"] = Permanence.objects.filter(status__lte=PERMANENCE_CLOSED).order_by("permanence_date")
        return super(PermanenceBoardInline, self).formfield_for_foreignkey(db_field, request, **kwargs)


class LUTPermanenceRoleAdmin(LUTAdmin):
    mptt_level_limit = ONE_LEVEL_DEPTH
    inlines = [PermanenceBoardInline]

    def get_fields(self, request, obj=None):
        fields = [
            'parent',
            'short_name',
            'customers_may_register',
            'is_counted_as_participation',
            'description',
            'is_active',
        ]
        return fields
