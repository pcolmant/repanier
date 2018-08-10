# -*- coding: utf-8

import threading

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.forms import widgets
from django.shortcuts import render
from django.utils import translation
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from djng.forms import fields, NgFormValidationMixin

from repanier.const import EMPTY_STRING
from repanier.email.email import RepanierEmail
from repanier.models.staff import Staff
from repanier.views.forms import RepanierForm
from repanier.widget.checkbox_select_multiple import CheckboxSelectMultipleWidget


class CoordinatorsContactForm(RepanierForm):
    staff = fields.MultipleChoiceField(
        label=EMPTY_STRING,
        choices=(),
        widget=CheckboxSelectMultipleWidget(
            label=_("This message will only be sent to the member(s) of the management team that you select below:")
        )
    )
    your_email = fields.EmailField(label=_('My email address'))
    subject = fields.CharField(label=_('Subject'), max_length=100)
    message = fields.CharField(label=_('Message'), widget=widgets.Textarea)

    def __init__(self, *args, **kwargs):
        super(CoordinatorsContactForm, self).__init__(*args, **kwargs)
        choices = []
        for staff in Staff.objects.filter(
                is_active=True,
                can_be_contacted=True,
                translations__language_code=translation.get_language()
        ):
            r = staff.customer_responsible
            if r is not None:
                sender_function = staff.safe_translation_getter(
                    'long_name', any_language=True, default=EMPTY_STRING
                )
                phone = " ({})".format(r.phone1 if r.phone1 else EMPTY_STRING)
                name = r.long_basket_name if r.long_basket_name else r.short_basket_name
                signature = "<b>{}</b> : {}{}".format(sender_function, name, phone)
                choices.append(("{}".format(staff.id), mark_safe(signature)))
        self.fields["staff"].choices = choices


class CoordinatorsContactValidationForm(NgFormValidationMixin, CoordinatorsContactForm):
    pass


@login_required()
@csrf_protect
@never_cache
def send_mail_to_coordinators_view(request):
    if request.method == 'POST':
        form = CoordinatorsContactValidationForm(request.POST)
        if form.is_valid():
            to_email = [request.user.email]
            selected_staff_members = form.cleaned_data.get('staff')
            for staff in Staff.objects.filter(
                    is_active=True,
                    can_be_contacted=True,
                    id__in=selected_staff_members
            ).order_by('?'):
                to_email = list(set(to_email + staff.get_to_email))

            email = RepanierEmail(
                strip_tags(form.cleaned_data.get('subject')),
                html_body=strip_tags(form.cleaned_data.get('message')),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=to_email,
                show_customer_may_unsubscribe=False,
                send_even_if_unsubscribed=True
            )
            t = threading.Thread(target=email.send_email)
            t.start()
            email = form.fields["your_email"]
            email.initial = request.user.email
            email.widget.attrs['readonly'] = True
            return render(request, "repanier/send_mail_to_coordinators.html",
                          {'form': form, 'send': True})
    else:
        form = CoordinatorsContactValidationForm()

        email = form.fields["your_email"]
        email.initial = request.user.email
        email.widget.attrs['readonly'] = True

    return render(request, "repanier/send_mail_to_coordinators.html", {'form': form, 'send': None})
