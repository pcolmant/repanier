# -*- coding: utf-8
from __future__ import unicode_literals

import thread
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.http import Http404
from django.shortcuts import render
from django.utils import translation
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from djng.forms import NgFormValidationMixin
from djng.forms.field_mixins import EmailFieldMixin, CharFieldMixin, MultipleChoiceFieldMixin
from djng.styling.bootstrap3.field_mixins import BooleanFieldMixin

from repanier.const import EMPTY_STRING
from repanier.models import Staff
from repanier.tools import send_email
from repanier.views.forms import RepanierForm
from repanier.widget.checkbox_select_multiple import CheckboxSelectMultipleWidget


class DjngBooleanField(BooleanFieldMixin, forms.BooleanField):
    pass


class DjngEmailField(EmailFieldMixin, forms.EmailField):
    pass


class DjngCharField(CharFieldMixin, forms.CharField):
    pass


class DjngMultipleChoiceField(MultipleChoiceFieldMixin, forms.MultipleChoiceField):
    pass


class CoordinatorsContactForm(RepanierForm):
    staff = DjngMultipleChoiceField(
        label=EMPTY_STRING,
        choices=[],
        widget=CheckboxSelectMultipleWidget()
    )
    your_email = DjngEmailField(label=_('Your Email'))
    subject = DjngCharField(label=_('Subject'), max_length=100)
    message = DjngCharField(label=_('Message'), widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super(CoordinatorsContactForm, self).__init__(*args, **kwargs)
        choices = []
        for staff in Staff.objects.filter(
            is_active=True, is_contributor=False,
            translations__language_code=translation.get_language()
        ):
            r = staff.customer_responsible
            if r is not None:
                sender_function = staff.safe_translation_getter(
                    'long_name', any_language=True, default=EMPTY_STRING
                )
                phone = " (%s)" % r.phone1 if r.phone1 else EMPTY_STRING
                name = r.long_basket_name if r.long_basket_name else r.short_basket_name
                signature = "<b>%s</b> : %s%s" % (sender_function, name, phone)
                choices.append(("%d" % staff.id, mark_safe(signature)))
        self.fields["staff"] = DjngMultipleChoiceField(
            label=EMPTY_STRING,
            choices=choices,
            widget=CheckboxSelectMultipleWidget()
        )


class CoordinatorsContactValidationForm(NgFormValidationMixin, CoordinatorsContactForm):
    pass


@login_required()
@csrf_protect
@never_cache
def send_mail_to_coordinators_view(request):
    if request.user.is_staff:
        raise Http404
    if request.method == 'POST':
        form = CoordinatorsContactValidationForm(request.POST)
        if form.is_valid():
            to_email_staff = []
            selected_staff_members = form.cleaned_data.get('staff')
            for staff in Staff.objects.filter(is_active=True, is_contributor=False, id__in=selected_staff_members).order_by('?'):
                to_email_staff.append(staff.user.email)

            if to_email_staff:
                to_email_customer = [request.user.email]
                email = EmailMessage(
                    strip_tags(form.cleaned_data.get('subject')),
                    strip_tags(form.cleaned_data.get('message')),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=to_email_customer,
                    cc=to_email_staff
                )
                # send_email(email=email)
                thread.start_new_thread(send_email, (email,))
                # return HttpResponseRedirect('/')
                email = form.fields["your_email"]
                email.initial = request.user.email
                email.widget.attrs['readonly'] = True
                return render(request, "repanier/send_mail_to_coordinators.html",
                              {'form': form, 'update': '2'})
            else:
                return render(request, "repanier/send_mail_to_coordinators.html",
                              {'form': form, 'update': '1'})
    else:
        form = CoordinatorsContactValidationForm()

        email = form.fields["your_email"]
        email.initial = request.user.email
        email.widget.attrs['readonly'] = True

    return render(request, "repanier/send_mail_to_coordinators.html", {'form': form})
