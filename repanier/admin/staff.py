# -*- coding: utf-8

import uuid

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _
from easy_select2 import apply_select2
from parler.forms import TranslatableModelForm

from repanier.const import EMPTY_STRING, \
    COORDINATION_GROUP, ONE_LEVEL_DEPTH
from repanier.models.customer import Customer
from repanier.models.staff import Staff
from repanier.views.logout_view import remove_staff_right
from .lut import LUTAdmin


class UserDataForm(TranslatableModelForm):
    email = forms.EmailField(label=_('Email'))
    user = None

    def __init__(self, *args, **kwargs):
        super(UserDataForm, self).__init__(*args, **kwargs)

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        # Check that the email is set
        if not "email" in self.cleaned_data:
            self.add_error('email', _('The given email must be set'))
        else:
            is_reply_to_order_email = self.cleaned_data["is_reply_to_order_email"]
            is_reply_to_invoice_email = self.cleaned_data["is_reply_to_invoice_email"]
            is_coordinator = self.cleaned_data["is_coordinator"]
            if is_reply_to_order_email:
                qs = Staff.objects.filter(is_reply_to_order_email=True).order_by('?')
                if self.instance.id is not None:
                    qs = qs.exclude(id=self.instance.id)
                if qs.exists():
                    self.add_error('is_reply_to_order_email', _('This flag is already set for another staff member'))
            if is_reply_to_invoice_email:
                qs = Staff.objects.filter(is_reply_to_invoice_email=True).order_by('?')
                if self.instance.id is not None:
                    qs = qs.exclude(id=self.instance.id)
                if qs.exists():
                    self.add_error('is_reply_to_invoice_email', _('This flag is already set for another staff member'))
            if not is_coordinator:
                qs = Staff.objects.filter(is_coordinator=True).order_by('?')
                if self.instance.id is not None:
                    qs = qs.exclude(id=self.instance.id)
                if not qs.exists():
                    self.add_error('is_coordinator', _('At least on coordinator must be set'))

    def save(self, *args, **kwargs):
        super(UserDataForm, self).save(*args, **kwargs)
        change = (self.instance.id is not None)
        email = self.data['email'].lower()
        user_model = get_user_model()
        if change:
            user = user_model.objects.get(id=self.instance.user_id)
            user.email = email
            user.save()
        else:
            # Important : The username who is never used is uuid1 to avoid clash with customer username
            # The staff member login with his customer mail address
            # Linked with AuthRepanierPasswordResetForm.get_users
            user = user_model.objects.create_user(
                username=uuid.uuid1().hex, email=email, password=None,
                first_name=EMPTY_STRING, last_name=EMPTY_STRING)
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
        if self._has_delete_permission is None:
            if request.user.groups.filter(name=COORDINATION_GROUP).exists() or request.user.is_superuser:
                # Only a coordinator can delete
                self._has_delete_permission = True
            else:
                self._has_delete_permission = False
        return self._has_delete_permission

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
            'is_reply_to_order_email',
            'is_reply_to_invoice_email',
            'is_contributor',
            'is_webmaster',
        ]
        if not settings.DJANGO_SETTINGS_IS_MINIMALIST:
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
            kwargs["queryset"] = Customer.objects.filter(is_active=True)
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
        if change_previous_customer_responsible:
            remove_staff_right(old_customer_responsible_field.user, is_customer=True)
