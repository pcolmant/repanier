# -*- coding: utf-8
from __future__ import unicode_literals

import threading

from django.forms import widgets
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from djng.forms import fields, NgFormValidationMixin

from repanier.email.email import RepanierEmail
from repanier.models.customer import Customer
from repanier.views.forms import RepanierForm
from repanier.tools import check_if_is_coordinator


class MembersContactForm(RepanierForm):
    recipient = fields.CharField(label=_('Recipient(s)'))
    your_email = fields.EmailField(label=_('Your Email'))
    subject = fields.CharField(label=_('Subject'), max_length=100)
    message = fields.CharField(label=_('Message'), widget=widgets.Textarea)

    def __init__(self, *args, **kwargs):
        super(MembersContactForm, self).__init__(*args, **kwargs)


class MembersContactValidationForm(NgFormValidationMixin, MembersContactForm):
    pass


@login_required()
@csrf_protect
@never_cache
def send_mail_to_all_members_view(request):
    from repanier.apps import REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO
    if not REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO:
        raise Http404
    user = request.user
    customer_is_active = Customer.objects.filter(user_id=user.id, is_active=True).order_by('?').exists()
    if not customer_is_active:
        raise Http404
    is_coordinator = check_if_is_coordinator(request)
    if request.method == 'POST':
        form = MembersContactValidationForm(request.POST)  # A form bound to the POST data
        user_customer = Customer.objects.filter(
            id=request.user.customer.id,
            is_active=True
        ).order_by('?').first()
        if form.is_valid() and user_customer is not None:  # All validation rules pass
            to_email_customer = []
            qs = Customer.objects.filter(
                is_active=True,
                represent_this_buyinggroup=False,
                subscribe_to_email=True,
                user__last_login__isnull=False)
            if not is_coordinator:
                qs = qs.filter(accept_mails_from_members=True)
            for customer in qs:
                if customer.user_id != request.user.id:
                    to_email_customer.append(customer.user.email)
                    if customer.email2:
                        to_email_customer.append(customer.email2)
            to_email_customer.append(request.user.email)
            email = RepanierEmail(
                strip_tags(form.cleaned_data.get('subject')),
                html_content=strip_tags(form.cleaned_data.get('message')),
                from_email=request.user.email,
                cc=to_email_customer
            )
            # send_email(email=email, from_name=user_customer.long_basket_name)
            # thread.start_new_thread(send_email,(email, user_customer.long_basket_name, True))
            t = threading.Thread(target=email.send_email, args=(email, user_customer.long_basket_name))
            t.start()
            email = form.fields["your_email"]
            email.initial = request.user.email
            email.widget.attrs['readonly'] = True
            recipient = form.fields["recipient"]
            if is_coordinator:
                recipient.initial = _("All members as coordinator")
            else:
                recipient.initial = _("All members accepting to show they mail address")
            recipient.widget.attrs['readonly'] = True
            return render(request, "repanier/send_mail_to_all_members.html",
                          {'form': form, 'update': '2'})
    else:
        form = MembersContactValidationForm()  # An unbound form
        email = form.fields["your_email"]
        email.initial = request.user.email
        email.widget.attrs['readonly'] = True
        recipient = form.fields["recipient"]
        if is_coordinator:
            recipient.initial = _("All members as coordinator")
        else:
            recipient.initial = _("All members accepting to show they mail address")
        recipient.widget.attrs['readonly'] = True

    return render(request, "repanier/send_mail_to_all_members.html",
                  {'form': form, 'coordinator': is_coordinator})
