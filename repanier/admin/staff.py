# -*- coding: utf-8
import uuid

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _
from easy_select2 import apply_select2
from parler.forms import TranslatableModelForm

from repanier.auth_backend import RepanierAuthBackend
from repanier.const import EMPTY_STRING, \
    ONE_LEVEL_DEPTH
from repanier.models.customer import Customer
from repanier.models.staff import Staff
from .lut import LUTAdmin


class UserDataForm(TranslatableModelForm):
    email = forms.EmailField(label=_('Email'), required=False)
    user = None

    def __init__(self, *args, **kwargs):
        super(UserDataForm, self).__init__(*args, **kwargs)

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        is_active = self.cleaned_data["is_active"]
        is_coordinator = is_active and self.cleaned_data["is_coordinator"]
        # print("------- self.cleaned_data[\"is_active\"] : {}".format(self.cleaned_data["is_active"]))
        # print("------- is_active : {}".format(is_active))
        # print("------- is_coordinator : {}".format(is_coordinator))
        is_order_manager = is_active and self.cleaned_data["is_order_manager"]
        is_order_referent = is_active and self.cleaned_data["is_order_referent"]
        is_invoice_manager = is_active and self.cleaned_data["is_invoice_manager"]
        is_invoice_referent = is_active and self.cleaned_data["is_invoice_referent"]
        is_webmaster = is_active and self.cleaned_data["is_webmaster"]
        if settings.REPANIER_SETTINGS_TEST_MODE:
            is_tester = is_active and self.cleaned_data["is_tester"]
        else:
            is_tester = False
        if is_active and not (is_coordinator or
                is_order_manager or is_order_referent or
                is_invoice_manager or is_invoice_referent or
                is_webmaster or
                is_tester):
            self.add_error(
                None,
                _('Members of the management team must assure at least one function')
            )
        if is_order_manager:
            qs = Staff.objects.filter(is_order_manager=True, is_active=True).order_by('?')
            if self.instance.id is not None:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                self.add_error(
                    'is_order_manager',
                    _('One and only one member of the management team can assure this function')
                )
        if is_invoice_manager:
            qs = Staff.objects.filter(is_invoice_manager=True, is_active=True).order_by('?')
            if self.instance.id is not None:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                self.add_error(
                    'is_invoice_manager',
                    _('One and only one member of the management team can assure this function')
                )
        # Check that the email is not already used
        email = self.cleaned_data["email"].lower()
        if email:
            # self.add_error('email', _('This field is required.'))
            user_model = get_user_model()
            qs = user_model.objects.filter(email=email).order_by('?')
            if self.instance.id is not None:
                qs = qs.exclude(id=self.instance.user_id)
            if qs.exists():
                self.add_error(
                    'email',
                    _('The email {} is already used by another user.').format(email)
                )
        else:
            if not self.cleaned_data["customer_responsible"]:
                self.add_error(
                    'email',
                    _('At least one email address or one responsible customer must be set.')
                )
                self.add_error(
                    'customer_responsible',
                    _('At least one email address or one responsible customer must be set.')
                )

        if not is_coordinator:
            qs = Staff.objects.filter(is_coordinator=True, is_active=True).order_by('?')
            if self.instance.id is not None:
                qs = qs.exclude(id=self.instance.id)
            if not qs.exists():
                self.add_error(
                    'is_coordinator',
                    _('At least one coordinator must be set within the management team')
                )
                if not is_active:
                    self.add_error(
                        'is_active',
                        _('At least one coordinator must be set within the management team')
                    )

    def save(self, *args, **kwargs):
        super(UserDataForm, self).save(*args, **kwargs)
        change = (self.instance.id is not None)
        email = self.data['email'].lower()
        user_model = get_user_model()
        if change:
            user = user_model.objects.get(id=self.instance.user_id)
            user.email = email
            user.username = email or uuid.uuid1()
            user.last_name = self.data['long_name']
            user.first_name = EMPTY_STRING
            user.save()
        else:
            # Important : The username who is never used is uuid1 to avoid clash with customer username
            # The staff member login with his customer mail address
            # Linked with AuthRepanierPasswordResetForm.get_users
            user = user_model.objects.create_user(
                username=email or "{}@repanier.be".format(uuid.uuid1()),
                email=email, password=None,
                first_name=EMPTY_STRING, last_name=email)
        self.user = user
        return self.instance


# Staff
class StaffWithUserDataForm(UserDataForm):
    class Meta:
        model = Staff
        fields = "__all__"
        widgets = {
            'customer_responsible': apply_select2(forms.Select),
        }


class StaffWithUserDataAdmin(LUTAdmin):
    mptt_level_limit = ONE_LEVEL_DEPTH
    item_label_field_name = 'title_for_admin'
    form = StaffWithUserDataForm
    list_display = ('long_name',)
    list_display_links = ('long_name',)
    list_select_related = ('customer_responsible',)
    list_per_page = 16
    list_max_show_all = 16
    _has_delete_permission = None

    def has_delete_permission(self, request, obj=None):
        user = request.user
        if user.is_coordinator:
            return True
        return False

    def has_add_permission(self, request):
        return self.has_delete_permission(request)

    def has_change_permission(self, request, staff=None):
        return self.has_delete_permission(request)

    def get_list_display(self, request):
        list_display = [
            'long_name'
        ]
        if settings.DJANGO_SETTINGS_MULTIPLE_LANGUAGE:
            list_display += [
                'language_column',
            ]
        list_display += [
            'customer_responsible',
            'get_customer_phone1'
        ]
        return list_display

    def get_fields(self, request, obj=None):
        fields = [
            'long_name',
            'email',
            'customer_responsible',
            'is_coordinator',
            'is_order_manager',
            'is_order_referent',
            'is_invoice_manager',
            'is_invoice_referent',
            'is_webmaster',
        ]
        if settings.REPANIER_SETTINGS_TEST_MODE:
            fields += [
                'is_tester',
            ]
        fields += [
            'is_active'
        ]
        return fields

    def get_form(self, request, obj=None, **kwargs):
        form = super(StaffWithUserDataAdmin, self).get_form(request, obj, **kwargs)
        email_field = form.base_fields['email']
        # if "customer_responsible" in form.base_fields:
        #     customer_responsible_field = form.base_fields["customer_responsible"]
        #     customer_responsible_field.widget.can_add_related = False
        #     if obj is not None:
        #         customer_responsible_field.empty_label = None
        #         customer_responsible_field.initial = obj.customer_responsible
        #     else:
        #         customer_responsible_field.queryset = Customer.objects.filter(is_active=True)

        if obj is not None:
            user_model = get_user_model()
            user = user_model.objects.get(id=obj.user_id)
            email_field.initial = user.email
        else:
            # Clean data displayed
            email_field.initial = EMPTY_STRING
        return form

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "customer_responsible":
            kwargs["queryset"] = Customer.objects.filter(is_active=True, represent_this_buyinggroup=False)
        return super(StaffWithUserDataAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, staff, form, change):
        staff.user = form.user
        form.user.is_staff = True
        form.user.is_active = staff.is_active
        form.user.save()
        old_customer_responsible_field = form.base_fields["customer_responsible"].initial
        new_customer_responsible_field = form.cleaned_data["customer_responsible"]
        change_previous_customer_responsible = (
                change and
                old_customer_responsible_field is not None and
                old_customer_responsible_field.id != new_customer_responsible_field.id
        )

        super(StaffWithUserDataAdmin, self).save_model(request, staff, form, change)
        if change_previous_customer_responsible and old_customer_responsible_field.user is not None:
            RepanierAuthBackend.remove_staff_right(
                user=old_customer_responsible_field.user
            )
