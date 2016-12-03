# -*- coding: utf-8
from __future__ import unicode_literals

from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.http import Http404
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.html import strip_tags
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.conf import settings

from forms import CoordinatorsContactForm
from repanier.models import Staff
from repanier.tools import send_email


@login_required()
@csrf_protect
@never_cache
def send_mail_to_coordinators_view(request):
    if request.user.is_staff:
        raise Http404
    if request.method == 'POST':  # If the form has been submitted...
        form = CoordinatorsContactForm(request.POST)  # A form bound to the POST data
        if form.is_valid():  # All validation rules pass
            # Process the data in form.cleaned_data
            # ...
            to_email_staff = []
            for staff in Staff.objects.filter(is_active=True, is_contributor=False).order_by('?'):
                if form.cleaned_data.get('staff_%d' % staff.id):
                    to_email_staff.append(staff.user.email)
            if len(to_email_staff) > 0:
                to = (request.user.email,)
                email = EmailMessage(
                    strip_tags(form.cleaned_data.get('subject')),
                    strip_tags(form.cleaned_data.get('message')),
                    settings.DEFAULT_FROM_EMAIL,
                    to,
                    cc=to_email_staff
                )
                send_email(email=email)
                return HttpResponseRedirect('/')  # Redirect after POST
            else:
                return render(request, "repanier/send_mail_to_coordinators.html",
                                       {'form': form, 'update': '1'})
    else:
        form = CoordinatorsContactForm()  # An unbound form

        email = form.fields["your_email"]
        email.initial = request.user.email
        email.widget.attrs['readonly'] = True

    return render(request, "repanier/send_mail_to_coordinators.html", {'form': form})
