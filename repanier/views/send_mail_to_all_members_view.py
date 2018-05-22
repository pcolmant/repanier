# -*- coding: utf-8

import threading

from django.contrib.auth.decorators import login_required
from django.forms import widgets
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


class MembersContactForm(RepanierForm):
    recipient = fields.CharField(
        label=_('Recipient(s)'),
        initial=_("All members who agree to receive mails from this site")
    )
    your_email = fields.EmailField(label=_('My email address'))
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
    if request.method == 'POST' and user.customer_id is not None:
        form = MembersContactValidationForm(request.POST)  # A form bound to the POST data
        if form.is_valid():  # All validation rules pass
            user_customer = Customer.objects.filter(
                id=user.customer_id
            ).order_by('?').first()
            to_email_customer = []
            qs = Customer.objects.filter(
                is_active=True,
                represent_this_buyinggroup=False,
                subscribe_to_email=True,
                user__last_login__isnull=False,
                valid_email=True)
            for customer in qs:
                if customer.user_id != request.user.id:
                    to_email_customer.append(customer.user.email)
                    # if customer.email2:
                    #     to_email_customer.append(customer.email2)
            to_email_customer.append(request.user.email)
            email = RepanierEmail(
                strip_tags(form.cleaned_data.get('subject')),
                html_body=strip_tags(form.cleaned_data.get('message')),
                from_email=request.user.email,
                to=to_email_customer,
                show_customer_may_unsubscribe=True
            )
            t = threading.Thread(target=email.send_email, args=(email, user_customer.long_basket_name))
            t.start()
            email = form.fields["your_email"]
            email.initial = request.user.email
            email.widget.attrs['readonly'] = True
            recipient = form.fields["recipient"]
            recipient.widget.attrs['readonly'] = True
            return render(request, "repanier/send_mail_to_all_members.html",
                          {'form': form, 'coordinator': user.is_coordinator, 'send': True})
    else:
        form = MembersContactValidationForm()  # An unbound form
        email = form.fields["your_email"]
        email.initial = request.user.email
        email.widget.attrs['readonly'] = True
        recipient = form.fields["recipient"]
        recipient.widget.attrs['readonly'] = True

    return render(request, "repanier/send_mail_to_all_members.html",
                  {'form': form, 'coordinator': user.is_coordinator, 'send': None})
