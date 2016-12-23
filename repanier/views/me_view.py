# -*- coding: utf-8
from __future__ import unicode_literals

from os import sep as os_sep

from django import forms
from django.contrib.auth import (get_user_model)
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from djangocms_text_ckeditor.widgets import TextEditorWidget
from djng.forms import NgFormValidationMixin

from repanier.const import DECIMAL_ZERO, EMPTY_STRING
from repanier.picture.const import SIZE_S
from repanier.picture.widgets import AjaxPictureWidget
from repanier.views.forms import RepanierForm
from repanier.widget.checkbox import CheckboxWidget


class CustomerForm(RepanierForm):
    long_basket_name = forms.CharField(label=_("Your name"), max_length=100)

    email1 = forms.EmailField(label=_('Your main email, used for password recovery and login'))
    email2 = forms.EmailField(label=_('Your secondary email'), required=False)
    accept_mails_from_members = forms.BooleanField(
        label=EMPTY_STRING, required=False
    )

    phone1 = forms.CharField(label=_('Your main phone'), max_length=25)
    phone2 = forms.CharField(label=_('Your secondary phone'), max_length=25, required=False)

    accept_phone_call_from_members = forms.BooleanField(
        label=EMPTY_STRING, required=False
    )
    city = forms.CharField(label=_('Your city'), max_length=50, required=False)
    address = forms.CharField(label=_('address'), widget=forms.Textarea(attrs={'cols': '40', 'rows': '3'}),
                              required=False)
    picture = forms.CharField(
        label=_("picture"),
        widget=AjaxPictureWidget(upload_to="customer", size=SIZE_S, bootstrap=True),
        required=False)

    about_me = forms.CharField(label=_('About me'), widget=TextEditorWidget, required=False)

    def clean_email1(self):
        email1 = self.cleaned_data['email1']
        user_model = get_user_model()
        user = user_model.objects.filter(email=email1).order_by('?').first()
        if user is not None and user.id != self.request.user.id:
            self.add_error('email1', _('The given email is used by another user'))
        return email1

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(CustomerForm, self).__init__(*args, **kwargs)
        self.fields["accept_mails_from_members"].widget = CheckboxWidget(
            label=_('My emails are visible to all members'))
        self.fields["accept_phone_call_from_members"].widget = CheckboxWidget(
            label=_('My phones numbers are visible to all members'))


class CustomerValidationForm(NgFormValidationMixin, CustomerForm):
    pass


@login_required()
@csrf_protect
@never_cache
def me_view(request):
    if request.user.is_staff or request.user.is_superuser:
        raise Http404
    else:
        customer = request.user.customer
        from repanier.apps import REPANIER_SETTINGS_MEMBERSHIP_FEE
        if REPANIER_SETTINGS_MEMBERSHIP_FEE > DECIMAL_ZERO:
            membership_fee_valid_until = customer.membership_fee_valid_until
        else:
            membership_fee_valid_until = None
        if request.method == 'POST':  # If the form has been submitted...
            form = CustomerValidationForm(request.POST, request=request)  # A form bound to the POST data
            if form.is_valid():  # All validation rules pass
                # Process the data in form.cleaned_data
                # ...
                if customer is not None:
                    customer.long_basket_name = form.cleaned_data.get('long_basket_name')
                    customer.phone1 = form.cleaned_data.get('phone1')
                    customer.phone2 = form.cleaned_data.get('phone2')
                    customer.accept_phone_call_from_members = form.cleaned_data.get('accept_phone_call_from_members')
                    customer.email2 = form.cleaned_data.get('email2').lower()
                    customer.accept_mails_from_members = form.cleaned_data.get('accept_mails_from_members')
                    customer.city = form.cleaned_data.get('city')
                    customer.address = form.cleaned_data.get('address')
                    customer.picture = form.cleaned_data.get('picture')
                    customer.about_me = form.cleaned_data.get('about_me')
                    customer.save()
                    # Important : place this code after because form = CustomerForm(data, request=request) delete form.cleaned_data
                    email = form.cleaned_data.get('email1')
                    user_model = get_user_model()
                    user = user_model.objects.filter(email=email).order_by('?').first()
                    if user is None or user.email != email:
                        # user.email != email for case unsensitive SQL query
                        customer.user.email = email.lower()
                        customer.user.save()
                    # User feed back : Display email in lower case.
                    data = form.data.copy()
                    data["email1"] = customer.user.email
                    data["email2"] = customer.email2
                    form = CustomerValidationForm(data, request=request)
                return render(request, "repanier/me_form.html",
                              {'form': form, 'membership_fee_valid_until': membership_fee_valid_until, 'update': 'Ok'})
            return render(request, "repanier/me_form.html",
                          {'form': form, 'membership_fee_valid_until': membership_fee_valid_until, 'update': 'Nok'})
        else:
            form = CustomerValidationForm()  # An unbound form
            field = form.fields["long_basket_name"]
            field.initial = customer.long_basket_name
            field = form.fields["phone1"]
            field.initial = customer.phone1
            field = form.fields["phone2"]
            field.initial = customer.phone2
            field = form.fields["accept_phone_call_from_members"]
            field.initial = customer.accept_phone_call_from_members
            field = form.fields["email1"]
            field.initial = request.user.email
            field = form.fields["email2"]
            field.initial = customer.email2
            field = form.fields["accept_mails_from_members"]
            field.initial = customer.accept_mails_from_members
            field = form.fields["city"]
            field.initial = customer.city
            field = form.fields["address"]
            field.initial = customer.address
            field = form.fields["picture"]
            field.initial = customer.picture
            if hasattr(field.widget, 'upload_to'):
                field.widget.upload_to = "%s%s%d" % ("customer", os_sep, customer.id)
            field = form.fields["about_me"]
            field.initial = customer.about_me

        return render(request, "repanier/me_form.html",
                      {'form': form, 'membership_fee_valid_until': membership_fee_valid_until, 'update': None})
