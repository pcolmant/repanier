# -*- coding: utf-8

from django import forms
from django.conf import settings
from django.contrib.admin import TabularInline
from django.utils.translation import ugettext_lazy as _
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

        # def clean(self):
        #     if any(self.errors):
        #         # Don't bother validating the formset unless each form is valid on its own
        #         return
        #
        #     parent = self.cleaned_data["parent"]
        #     if parent is not None:
        #         # Get model name
        #         # str(type(self.instance)) = "<class 'repanier.models.lut.LUT_DepartmentForCustomer'>"
        #         # .rsplit('.', 1)[1][:-2] --> "LUT_DepartmentForCustomer"
        #         admin_model_name = str(type(self.instance)).rsplit('.', 1)[1][:-2]
        #         admin_model = apps.get_model("repanier", admin_model_name)
        #         if admin_model.objects.filter(**{"translations__short_name": parent, "level__gt": 0}).order_by('?').exists():
        #             self.add_error(
        #                 'parent',
        #                 _('Only two levels are allowed.'))


class LUTAdmin(TranslatableAdmin, DjangoMpttAdmin):
    form = LUTDataForm
    list_display = ('short_name', 'is_active')
    list_display_links = ('short_name',)
    mptt_level_indent = 20
    mptt_indent_field = "short_name"
    mptt_level_limit = None

    def has_delete_permission(self, request, obj=None):
        user = request.user
        if user.is_order or user.is_invoice or user.is_coordinator:
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


class LUTProductionModeAdmin(LUTAdmin):
    exclude = ('picture', 'description')


class LUTDeliveryPointAdmin(LUTAdmin):
    mptt_level_limit = ONE_LEVEL_DEPTH

    def get_fields(self, request, obj=None):
        fields = [
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

    fields = [
        'parent',
        'short_name',
        'is_active',
    ]


class PermanenceBoardInlineForm(forms.ModelForm):
    class Meta:
        widgets = {
            'permanence': apply_select2(forms.Select),
            'customer': apply_select2(forms.Select),
        }


class PermanenceBoardInline(InlineForeignKeyCacheMixin, TabularInline):
    mptt_level_limit = ONE_LEVEL_DEPTH
    form = PermanenceBoardInlineForm

    model = PermanenceBoard
    fields = [
        'permanence',
        'customer'
    ]
    extra = 1

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
    mptt_level_limit = TWO_LEVEL_DEPTH

    fields = [
        'short_name',
        'customers_may_register',
        'is_counted_as_participation',
        'description',
        'is_active',
    ]

    if not settings.DJANGO_SETTINGS_IS_MINIMALIST:
        inlines = [PermanenceBoardInline]
