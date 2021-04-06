from os import sep as os_sep

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.forms import widgets, forms, fields
from django.http import Http404
from django.shortcuts import render
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from repanier_v2.const import DECIMAL_ZERO, EMPTY_STRING
from repanier_v2.models.customer import Customer
from repanier_v2.picture.const import SIZE_S
from repanier_v2.tools import get_repanier_template_name
from repanier_v2.widget.checkbox import RepanierCheckboxWidget
from repanier_v2.widget.picture import RepanierPictureWidget


class CustomerForm(forms.Form):
    long_name = fields.CharField(label=_("My name is"), max_length=100)
    zero_waste = fields.BooleanField(
        label=EMPTY_STRING,
        required=False,
        widget=RepanierCheckboxWidget(label=_("Family zero waste")),
    )
    subscribe_to_email = fields.BooleanField(
        label=EMPTY_STRING,
        required=False,
        widget=RepanierCheckboxWidget(
            label=_("I agree to receive mails from this site")
        ),
    )
    email1 = fields.EmailField(
        label=_(
            "My main email address, used to reset the password and connect to the site"
        )
    )
    email2 = fields.EmailField(
        label=_("My secondary email address (does not allow to connect to the site)"),
        required=False,
    )

    phone1 = fields.CharField(label=_("My main phone number"), max_length=25)
    phone2 = fields.CharField(
        label=_("My secondary phone number"), max_length=25, required=False
    )
    city = fields.CharField(label=_("My city"), max_length=50, required=False)
    address = fields.CharField(
        label=_("My address"),
        widget=widgets.Textarea(attrs={"cols": "40", "rows": "3"}),
        required=False,
    )
    picture = fields.CharField(
        label=_("My picture"),
        widget=RepanierPictureWidget(upload_to="customer", size=SIZE_S, bootstrap=True),
        required=False,
    )

    about_me = fields.CharField(
        label=_("About me"),
        widget=widgets.Textarea(attrs={"cols": "40", "rows": "3"}),
        required=False,
    )

    def clean_email1(self):
        email1 = self.cleaned_data["email1"]
        user_model = get_user_model()
        qs = (
            user_model.objects.filter(email=email1, is_staff=False)
            .exclude(id=self.request.customer_id)
            .order_by("?")
        )
        if qs.exists():
            self.add_error(
                "email1",
                _("The email {} is already used by another user.").format(email1),
            )
        return email1

    # def __init__(self, *args, **kwargs):
    #     self.request = kwargs.pop("request", None)
    #     super().__init__(*args, **kwargs)


@login_required()
@csrf_protect
@never_cache
def published_customer_view(request, customer_id=0):
    print("######### customer_id : {}".format(customer_id))
    user = request.user
    if user.is_repanier_staff:
        customer = Customer.objects.filter(id=customer_id, is_active=True).first()
    else:
        customer = (
            Customer.objects.filter(id=user.customer_id, is_active=True)
            .filter(id=customer_id)
            .first()
        )
    if not customer:
        raise Http404
    from repanier_v2.globals import (
        REPANIER_SETTINGS_MEMBERSHIP_FEE,
        REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO,
    )

    if REPANIER_SETTINGS_MEMBERSHIP_FEE > DECIMAL_ZERO:
        membership_fee_valid_until = customer.membership_fee_valid_until
    else:
        membership_fee_valid_until = None
    template_name = get_repanier_template_name("published_customer_form.html")
    if request.method == "POST":  # If the form has been submitted...
        form = CustomerForm(request.POST)  # A form bound to the POST data
        if form.is_valid():  # All validation rules pass
            # Process the data in form.cleaned_data
            # ...
            if customer is not None:
                customer.long_name = form.cleaned_data.get("long_name")
                customer.phone1 = form.cleaned_data.get("phone1")
                customer.phone2 = form.cleaned_data.get("phone2")
                customer.email2 = form.cleaned_data.get("email2").lower()
                customer.subscribe_to_email = form.cleaned_data.get(
                    "subscribe_to_email"
                )
                customer.city = form.cleaned_data.get("city")
                customer.address = form.cleaned_data.get("address")
                customer.picture = form.cleaned_data.get("picture")
                customer.about_me = form.cleaned_data.get("about_me")
                customer.zero_waste = form.cleaned_data.get("zero_waste")
                customer.save()
                # Important : place this code after because form = CustomerForm(data, request=request) delete form.cleaned_data
                email = form.cleaned_data.get("email1")
                user_model = get_user_model()
                user = user_model.objects.filter(email=email).order_by("?").first()
                if user is None or user.email != email:
                    # user.email != email for case unsensitive SQL query
                    customer.user.username = customer.user.email = email.lower()
                    # customer.user.first_name = EMPTY_STRING
                    # customer.user.last_name = customer.short_name
                    customer.user.save()
                # User feed back : Display email in lower case.
                data = form.data.copy()
                data["email1"] = customer.user.email
                data["email2"] = customer.email2
                form = CustomerForm(data, request=request)
            return render(
                request,
                template_name,
                {
                    "form": form,
                    "membership_fee_valid_until": membership_fee_valid_until,
                    "display_who_is_who": REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO,
                    "update": True,
                },
            )
        return render(
            request,
            template_name,
            {
                "form": form,
                "membership_fee_valid_until": membership_fee_valid_until,
                "display_who_is_who": REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO,
                "update": False,
            },
        )
    else:
        form = CustomerForm()  # An unbound form
        field = form.fields["long_name"]
        field.initial = customer.long_name
        field = form.fields["phone1"]
        field.initial = customer.phone1
        field = form.fields["phone2"]
        field.initial = customer.phone2
        field = form.fields["email1"]
        field.initial = customer.user.email
        field = form.fields["email2"]
        field.initial = customer.email2
        field = form.fields["subscribe_to_email"]
        field.initial = customer.subscribe_to_email
        field = form.fields["city"]
        field.initial = customer.city
        field = form.fields["address"]
        field.initial = customer.address
        field = form.fields["picture"]
        field.initial = customer.picture
        if hasattr(field.widget, "upload_to"):
            field.widget.upload_to = "{}{}{}".format("customer", os_sep, customer.id)
        field = form.fields["about_me"]
        field.initial = customer.about_me
        field = form.fields["zero_waste"]
        field.initial = customer.zero_waste

    return render(
        request,
        template_name,
        {
            "form": form,
            "membership_fee_valid_until": membership_fee_valid_until,
            "display_who_is_who": REPANIER_SETTINGS_DISPLAY_WHO_IS_WHO,
            "update": None,
        },
    )
