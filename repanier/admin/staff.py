# -*- coding: utf-8
from __future__ import unicode_literals

import uuid

from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from easy_select2 import apply_select2
from parler.admin import TranslatableAdmin
from parler.forms import TranslatableModelForm

from repanier.const import EMPTY_STRING, \
    COORDINATION_GROUP, ORDER_GROUP, INVOICE_GROUP
from repanier.models import Customer, Staff


class UserDataForm(TranslatableModelForm):
    username = forms.CharField(label=_('Username'), max_length=25, required=True)
    email = forms.EmailField(label=_('Email'))
    user = None

    def __init__(self, *args, **kwargs):
        super(UserDataForm, self).__init__(*args, **kwargs)

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        # The Staff has no first_name or last_name because it's a function with login/pwd.
        # A Customer with a first_name and last_name is responsible of this function.
        username_field_name = 'username'
        initial_username = None
        try:
            initial_username = self.instance.user.username
        except:
            pass
        username = self.cleaned_data.get(username_field_name)
        user_error2 = _('The given username is used by another user')
        # Check that the email is set
        if not "email" in self.cleaned_data:
            self.add_error('email', _('The given email must be set'))
        else:
            email = self.cleaned_data["email"]
            is_reply_to_order_email = self.cleaned_data["is_reply_to_order_email"]
            is_reply_to_invoice_email = self.cleaned_data["is_reply_to_invoice_email"]
            # if is_reply_to_order_email or is_reply_to_invoice_email:
            #     if not email.endswith(settings.DJANGO_SETTINGS_ALLOWED_MAIL_EXTENSION):
            #         self.add_error(
            #             'email',
            #             _('The given email must end with %(allowed_extension)s') %
            #             {'allowed_extension': settings.DJANGO_SETTINGS_ALLOWED_MAIL_EXTENSION}
            #         )
            if is_reply_to_order_email:
                if self.instance.id is None:
                    exists = Staff.objects.filter(is_reply_to_order_email=True)
                else:
                    exists = Staff.objects.filter(is_reply_to_order_email=True).exclude(id=self.instance.id)
                if exists:
                    self.add_error('is_reply_to_order_email', _('This flag is already set for another staff member'))
            if is_reply_to_invoice_email:
                if self.instance.id is None:
                    exists = Staff.objects.filter(is_reply_to_invoice_email=True)
                else:
                    exists = Staff.objects.filter(is_reply_to_invoice_email=True).exclude(id=self.instance.id)
                if exists:
                    self.add_error('is_reply_to_invoice_email', _('This flag is already set for another staff member'))
            user_model = get_user_model()
            user = user_model.objects.filter(email=email).order_by("?").first()
            # Check that the username is not already used
            if user is not None:
                if initial_username != user.username:
                    self.add_error('email', _('The given email is used by another user'))
            user = user_model.objects.filter(username=username).order_by("?").first()
            if user is not None:
                if initial_username != user.username:
                    self.add_error(username_field_name, user_error2)

    def save(self, *args, **kwargs):
        super(UserDataForm, self).save(*args, **kwargs)
        change = (self.instance.id is not None)
        username = self.data['username']
        email = self.data['email'].lower()
        user_model = get_user_model()
        if change:
            user = user_model.objects.get(id=self.instance.user_id)
            user.username = username
            user.first_name = EMPTY_STRING
            user.last_name = username
            user.email = email
            user.save()
        else:
            user = user_model.objects.create_user(
                username=username, email=email, password=uuid.uuid1().hex,
                first_name=EMPTY_STRING, last_name=username)
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


class StaffWithUserDataAdmin(TranslatableAdmin):
    form = StaffWithUserDataForm
    fields = ['username',
              'email', 'is_reply_to_order_email', 'is_reply_to_invoice_email',
              'is_coordinator', 'is_contributor', 'is_webmaster',
              'customer_responsible', 'long_name', 'function_description',
              'is_active']
    list_display = ('user', 'language_column', 'long_name', 'customer_responsible', 'get_customer_phone1')
    list_filter = ('is_active',)
    list_select_related = ('customer_responsible',)
    list_per_page = 16
    list_max_show_all = 16

    def has_delete_permission(self, request, obj=None):
        if request.user.groups.filter(name=COORDINATION_GROUP).exists() or request.user.is_superuser:
            # Only a coordinator can delete
            return True
        return False

    def has_add_permission(self, request):
        if request.user.groups.filter(
                name__in=[ORDER_GROUP, INVOICE_GROUP, COORDINATION_GROUP]).exists() or request.user.is_superuser:
            return True
        return False

    def has_change_permission(self, request, staff=None):
        return self.has_add_permission(request)

    def get_form(self, request, obj=None, **kwargs):
        form = super(StaffWithUserDataAdmin, self).get_form(request, obj, **kwargs)
        username_field = form.base_fields['username']
        email_field = form.base_fields['email']
        if "customer_responsible" in form.base_fields:
            customer_responsible_field = form.base_fields["customer_responsible"]
            customer_responsible_field.widget.can_add_related = False
            if obj:
                customer_responsible_field.empty_label = None
                customer_responsible_field.initial = obj.customer_responsible
            else:
                customer_responsible_field.queryset = Customer.objects.filter(is_active=True).order_by(
                    "short_basket_name")

        if obj:
            user_model = get_user_model()
            user = user_model.objects.get(id=obj.user_id)
            username_field.initial = getattr(user, user_model.USERNAME_FIELD)
            email_field.initial = user.email
        else:
            # Clean data displayed
            username_field.initial = EMPTY_STRING
            email_field.initial = EMPTY_STRING
        return form

    def save_model(self, request, staff, form, change):
        staff.user = form.user
        form.user.is_staff = True
        form.user.is_active = staff.is_active
        form.user.save()
        # pre save stuff here
        super(StaffWithUserDataAdmin, self).save_model(request, staff, form, change)
        # post save stuff here
