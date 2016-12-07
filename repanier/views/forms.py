from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q, F
from django.forms import Textarea
from django.template import loader
from django.utils import timezone
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.widgets import TextEditorWidget
from parler.models import TranslationDoesNotExist

import repanier.apps
from repanier.const import DECIMAL_ONE, DECIMAL_ZERO, LUT_PRODUCER_PRODUCT_ORDER_UNIT, EMPTY_STRING, DEMO_EMAIL
from repanier.models import LUT_ProductionMode, Staff, Customer, Configuration
from repanier.picture.const import SIZE_M, SIZE_S
from repanier.picture.widgets import AjaxPictureWidget
from repanier.widget.select_bootstrap import SelectBootstrapWidget
from repanier.widget.select_producer_order_unit import SelectProducerOrderUnitWidget


class AuthRepanierLoginForm(AuthenticationForm):
    confirm = forms.CharField(label=_("Validation code"), max_length=15, required=False)

    def clean(self):
        """We overwrite clean method of the original AuthenticationForm to include
        the third parameter, called otp_token

        """
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        confirm = self.cleaned_data.get('confirm')

        if username and password:
            self.user_cache = authenticate(username=username,
                                           password=password,
                                           confirm=confirm)
            if self.user_cache is None:
                raise forms.ValidationError(
                    self.error_messages['invalid_login'],
                    code='invalid_login',
                    params={'username': self.username_field.verbose_name},
                )
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class AuthRepanierPasswordResetForm(PasswordResetForm):
    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        """
        Sends a django.core.mail.EmailMultiAlternatives to `to_email`.
        """
        subject = loader.render_to_string(subject_template_name, context)
        # Email subject *must not* contain newlines
        subject = ''.join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)

        if settings.DJANGO_SETTINGS_DEMO:
            to_email = DEMO_EMAIL
        email_message = EmailMultiAlternatives(subject, body, from_email, [to_email])
        if html_email_template_name is not None:
            html_email = loader.render_to_string(html_email_template_name, context)
            email_message.attach_alternative(html_email, 'text/html')

        email_message.send()

    # From Django 1.8, this let the user enter name or email to recover
    def get_users(self, email):
        """Given an email, return matching user(s) who should receive a reset.

        This allows subclasses to more easily customize the default policies
        that prevent inactive users and users with unusable passwords from
        resetting their password.

        """
        active_users = User.objects.filter(
            Q(username__iexact=email[:30], is_active=True) | Q(email__iexact=email, is_active=True)).order_by('?')
        return (u for u in active_users if u.has_usable_password())


class AuthRepanierSetPasswordForm(SetPasswordForm):
    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        """
        Sends a django.core.mail.EmailMultiAlternatives to `to_email`.
        """
        subject = loader.render_to_string(subject_template_name, context)
        # Email subject *must not* contain newlines
        subject = EMPTY_STRING.join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)

        email_message = EmailMultiAlternatives(subject, body, from_email, [to_email])
        if html_email_template_name is not None:
            html_email = loader.render_to_string(html_email_template_name, context)
            email_message.attach_alternative(html_email, 'text/html')

        email_message.send()

    def save(self, commit=True, use_https=False, request=None,
             from_email=settings.DEFAULT_FROM_EMAIL):
        super(AuthRepanierSetPasswordForm, self).save(commit)
        if commit:
            now = timezone.now()
            if self.user.is_superuser:
                Configuration.objects.filter(id=DECIMAL_ONE).update(
                    login_attempt_counter=DECIMAL_ZERO,
                    password_reset_on=now
                )
            elif self.user.is_staff:
                staff = Staff.objects.filter(
                    user=self.user, is_active=True
                ).order_by('?').first()
                if staff is not None:
                    Staff.objects.filter(id=staff.id).update(
                        login_attempt_counter=DECIMAL_ZERO,
                        password_reset_on=now
                    )
            else:
                customer = Customer.objects.filter(
                    user=self.user, is_active=True
                ).order_by('?').first()
                if customer is not None:
                    Customer.objects.filter(id=customer.id).update(
                        login_attempt_counter=DECIMAL_ZERO,
                        password_reset_on=now
                    )
            current_site = get_current_site(request)
            site_name = current_site.name
            domain = current_site.domain
            context = {
                'email'    : self.user.email,
                'domain'   : domain,
                'site_name': site_name,
                'user'     : self.user,
                'protocol' : 'https' if use_https else 'http',
            }
            self.send_mail('repanier/registration/password_reset_done_subject.txt',
                           'repanier/registration/password_reset_done_email.html',
                           context, from_email, self.user.email,
                           html_email_template_name=None)
        return self.user


class CoordinatorsContactForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super(CoordinatorsContactForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'contact_form'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-2'
        self.helper.field_class = 'col-lg-10'
        for staff in Staff.objects.filter(is_active=True, is_contributor=False):
            r = staff.customer_responsible
            if r is not None:
                try:
                    sender_function = staff.long_name
                except TranslationDoesNotExist:
                    sender_function = EMPTY_STRING
                if r.long_basket_name is not None:
                    signature = "%s : %s" % (sender_function, r.long_basket_name)
                else:
                    signature = "%s :%s" % (sender_function, r.short_basket_name)
                self.fields["staff_%d" % staff.id] = forms.BooleanField(label=signature, required=False)
        self.fields["your_email"] = forms.EmailField(label=_('Your Email'))
        self.fields["subject"] = forms.CharField(label=_('Subject'))
        self.fields["message"] = forms.CharField(label=_('Message'), widget=Textarea)
        self.helper.add_input(Submit('submit', _('Send e-mail')))


class MembersContactForm(forms.Form):
    recipient = forms.CharField(label=_('Recipient(s)'))
    your_email = forms.EmailField(label=_('Your Email'))
    subject = forms.CharField(label=_('Subject'))
    message = forms.CharField(label=_('Message'), widget=Textarea)

    def __init__(self, *args, **kwargs):
        super(MembersContactForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'contact_form'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-2'
        self.helper.field_class = 'col-lg-10'
        self.helper.add_input(Submit('submit', _('Send e-mail')))


class CustomerForm(forms.Form):
    # error_css_class = 'has-warning'

    long_basket_name = forms.CharField(label=_("Your name"), max_length=100)
    accept_phone_call_from_members = forms.BooleanField(label=_('My phones numbers are visible to all members'),
                                                        required=False)
    phone1 = forms.CharField(label=_('Your main phone'), max_length=25)
    phone2 = forms.CharField(label=_('Your secondary phone'), max_length=25, required=False)
    accept_mails_from_members = forms.BooleanField(label=_('My emails are visible to all members'), required=False)
    email1 = forms.EmailField(label=_('Your main email, used for password recovery and login'))
    email2 = forms.EmailField(label=_('Your secondary email'), required=False)
    city = forms.CharField(label=_('Your city'), max_length=50, required=False)
    address = forms.CharField(label=_('address'), widget=Textarea(attrs={'cols': '40', 'rows': '3'}), required=False)
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
        self.helper = FormHelper()
        self.helper.form_id = 'customer_form'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-2'
        self.helper.field_class = 'col-lg-10'
        self.helper.add_input(Submit('submit', _('Update')))


class ProducerProductForm(forms.Form):
    long_name = forms.CharField(label=_('long_name'))
    order_unit = forms.ChoiceField(
        label=_("order unit"),
        choices=LUT_PRODUCER_PRODUCT_ORDER_UNIT,
        widget=SelectProducerOrderUnitWidget,
        required=True
    )
    production_mode = forms.ModelChoiceField(
        LUT_ProductionMode.objects.filter(
            rght=F('lft') + 1, is_active=True, translations__language_code=translation.get_language()).order_by(
            'translations__short_name'
        ),
        label=_("production mode"),
        widget=SelectBootstrapWidget,
        required=False
    )

    customer_increment_order_quantity = forms.DecimalField(
        max_digits=4, decimal_places=1)
    order_average_weight = forms.DecimalField(
        max_digits=4, decimal_places=1)
    producer_unit_price = forms.DecimalField(
        label=_("producer unit price"),
        max_digits=8, decimal_places=2)
    unit_deposit = forms.DecimalField(
        label=_("deposit to add"),
        max_digits=8, decimal_places=2)
    stock = forms.DecimalField(
        label=_("Stock"),
        max_digits=7, decimal_places=1)
    vat_level = forms.ChoiceField(
        label=_("tax"),
        choices=settings.LUT_VAT,
        widget=SelectBootstrapWidget,
        required=True
    )
    picture = forms.CharField(
        label=_("picture"),
        widget=AjaxPictureWidget(upload_to="product", size=SIZE_M, bootstrap=True),
        required=False)
    offer_description = forms.CharField(label=_('offer_description'), widget=TextEditorWidget, required=False)

    def __init__(self, *args, **kwargs):
        super(ProducerProductForm, self).__init__(*args, **kwargs)
