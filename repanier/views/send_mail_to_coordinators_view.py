# -*- coding: utf-8
from __future__ import unicode_literals

from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.http import Http404
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from djng.forms import NgFormValidationMixin
from djng.forms.field_mixins import EmailFieldMixin, CharFieldMixin, MultipleChoiceFieldMixin
from djng.styling.bootstrap3.field_mixins import BooleanFieldMixin
from djng.styling.bootstrap3.widgets import CheckboxSelectMultiple
from parler.models import TranslationDoesNotExist

from repanier.const import EMPTY_STRING
from repanier.models import Staff
from repanier.tools import send_email
from repanier.views.forms import RepanierForm
from repanier.widget.checkbox_select_multiple import CheckboxSelectMultipleWidget
from repanier.widget.checkbox import CheckboxWidget


class DjngBooleanField(BooleanFieldMixin, forms.BooleanField):
    pass


class DjngEmailField(EmailFieldMixin, forms.EmailField):
    pass


class DjngCharField(CharFieldMixin, forms.CharField):
    pass


class DjngMultipleChoiceField(MultipleChoiceFieldMixin, forms.MultipleChoiceField):
    pass


class CoordinatorsContactForm(RepanierForm):
    # team1 = forms.MultipleChoiceField(
    #     label=_("Management team"),
    #     choices=(('1', 'un'), ('2', 'deux'), ('3', 'trois')),
    #     widget=CheckboxSelectMultiple()
    # )

    def __init__(self, *args, **kwargs):
        super(CoordinatorsContactForm, self).__init__(*args, **kwargs)
        choices = []
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
                self.fields["staff_%d" % staff.id] = DjngBooleanField(label=EMPTY_STRING, required=False)
                self.fields["staff_%d" % staff.id].widget = CheckboxWidget(label=signature)
                # choices.append(("staff_%d" % staff.id, signature))
        # self.fields["staff"] = DjngMultipleChoiceField(
        #     label=_("This message will be send only to coordinators you have selected."),
        #     choices=choices,
        #     widget=CheckboxSelectMultipleWidget()
        # )
        self.fields["your_email"] = DjngEmailField(label=_('Your Email'))
        self.fields["subject"] = DjngCharField(label=_('Subject'), max_length=100)
        self.fields["message"] = DjngCharField(label=_('Message'), widget=forms.Textarea)


class CoordinatorsContactValidationForm(NgFormValidationMixin, CoordinatorsContactForm):
    pass


@login_required()
@csrf_protect
@never_cache
def send_mail_to_coordinators_view(request):
    if request.user.is_staff:
        raise Http404
    if request.method == 'POST':
        print('---------------')
        print(request.POST)
        form = CoordinatorsContactValidationForm(request.POST)
        if form.is_valid():
            print('valide')
            to_email_staff = []
            for staff in Staff.objects.filter(is_active=True, is_contributor=False).order_by('?'):
                if form.cleaned_data.get('staff_%d' % staff.id):
                    to_email_staff.append(staff.user.email)

            print(to_email_staff)
            if len(to_email_staff) > 0:
                to_email_customer = [request.user.email]
                email = EmailMessage(
                    strip_tags(form.cleaned_data.get('subject')),
                    strip_tags(form.cleaned_data.get('message')),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=to_email_customer,
                    cc=to_email_staff
                )
                # send_email(email=email)
                return HttpResponseRedirect('/')
            else:
                return render(request, "repanier/send_mail_to_coordinators.html",
                              {'form': form, 'update': '1'})
    else:
        form = CoordinatorsContactValidationForm()

        email = form.fields["your_email"]
        email.initial = request.user.email
        email.widget.attrs['readonly'] = True

    return render(request, "repanier/send_mail_to_coordinators.html", {'form': form})
