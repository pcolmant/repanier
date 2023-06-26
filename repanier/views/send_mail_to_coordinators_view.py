import threading

from django.contrib.auth.decorators import login_required
from django.forms import widgets, forms, fields
from django.shortcuts import render
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from repanier.email.email import RepanierEmail
from repanier.models.staff import Staff
from repanier.tools import get_repanier_template_name


class CoordinatorsContactForm(forms.Form):
    staff = fields.MultipleChoiceField(label=_("Send an email to"), choices=())
    your_email = fields.EmailField(label=_("My email address"))
    subject = fields.CharField(label=_("Subject"), max_length=100)
    message = fields.CharField(label=_("Message"), widget=widgets.Textarea)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = []
        for staff in Staff.objects.filter(
            is_active=True,
            can_be_contacted=True,
        ):
            choices.append((staff.id, staff.get_str_member))
        self.fields["staff"].choices = choices


@login_required()
@csrf_protect
@never_cache
def send_mail_to_coordinators_view(request):
    template_name = get_repanier_template_name("send_mail_to_coordinators.html")
    if request.method == "POST":
        form = CoordinatorsContactForm(request.POST)
        if form.is_valid():
            to_email = [request.user.email]
            selected_staff_members = form.cleaned_data.get("staff")
            for staff in Staff.objects.filter(
                is_active=True, can_be_contacted=True, id__in=selected_staff_members
            ):
                to_email = list(set(to_email + staff.get_to_email))

            email = RepanierEmail(
                strip_tags(form.cleaned_data.get("subject")),
                html_body=strip_tags(form.cleaned_data.get("message")),
                to=to_email,
            )
            t = threading.Thread(target=email.send_email)
            t.start()
            email = form.fields["your_email"]
            email.initial = request.user.email
            email.widget.attrs["readonly"] = True
            return render(request, template_name, {"form": form, "send": True})
    else:
        form = CoordinatorsContactForm()

        email = form.fields["your_email"]
        email.initial = request.user.email
        email.widget.attrs["readonly"] = True

    return render(request, template_name, {"form": form, "send": None})
