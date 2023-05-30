from django.conf import settings
from django.views.generic import ListView

from repanier.const import EMPTY_STRING
from repanier.models.customer import Customer
from repanier.models.lut import LUT_DepartmentForCustomer
from repanier.models.offeritem import OfferItemReadOnly
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.staff import Staff
from repanier.tools import (
    sint,
    permanence_ok_or_404,
    get_repanier_template_name,
)


class OrderView(ListView):
    context_object_name = "offeritem_list"
    template_name = get_repanier_template_name("order_form.html")
    success_url = "/"
    paginate_by = 18
    paginate_orphans = 2

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.user = None
        self.customer = None
        self.first_page = False
        self.producer_id = "all"
        self.department_id = "all"
        self.communication = 0
        self.q = None
        self.is_basket = False
        self.is_like = False
        self.may_order = False
        self.permanence = None

    def get(self, request, *args, **kwargs):
        self.first_page = kwargs.get("page", True)
        permanence_id = sint(kwargs.get("permanence_id", 0))
        self.permanence = (
            Permanence.objects.filter(id=permanence_id)
            .only("id", "status", "permanence_date", "with_delivery_point")
            .first()
        )
        permanence_ok_or_404(self.permanence)
        self.user = request.user
        self.is_basket = self.request.GET.get("is_basket", False)
        self.is_like = self.request.GET.get("is_like", False)
        if not self.user.is_anonymous:
            self.customer = Customer.objects.filter(id=self.user.customer_id).first()
        if self.customer is None:
            self.may_order = False
        else:
            self.may_order = self.customer.may_order

        self.q = self.request.GET.get("q", None)
        if not self.q:
            self.producer_id = self.request.GET.get("producer", "all")
            if self.producer_id != "all":
                self.producer_id = sint(self.producer_id)
            self.department_id = self.request.GET.get("department", "all")
            if self.department_id != "all":
                self.department_id = sint(self.department_id)
        if len(request.GET) == 0:
            # This to let display a communication into a popup when the user is on the first order screen
            self.communication = True
        else:
            self.communication = False

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from repanier.apps import (
            REPANIER_SETTINGS_DISPLAY_ANONYMOUS_ORDER_FORM,
            REPANIER_SETTINGS_NOTIFICATION,
        )

        context = super().get_context_data(**kwargs)
        context["first_page"] = self.first_page
        context["permanence"] = self.permanence
        context["permanence_id"] = self.permanence.id
        context[
            "notification"
        ] = REPANIER_SETTINGS_NOTIFICATION.get_notification_display()
        if self.first_page:
            if settings.REPANIER_SETTINGS_SHOW_PRODUCER_ON_ORDER_FORM:
                producer_set = Producer.objects.filter(
                    permanence=self.permanence.id
                ).only("id", "short_profile_name")
            else:
                producer_set = None
            context["producer_set"] = producer_set
            if self.producer_id == "all":
                department_set = (
                    LUT_DepartmentForCustomer.objects.filter(
                        offeritem__permanence_id=self.permanence.id,
                        offeritem__is_active=True,
                    )
                    .order_by("tree_id", "lft")
                    .distinct("id", "tree_id", "lft")
                )
            else:
                department_set = (
                    LUT_DepartmentForCustomer.objects.filter(
                        offeritem__producer_id=self.producer_id,
                        offeritem__permanence_id=self.permanence.id,
                        offeritem__is_active=True,
                    )
                    .order_by("tree_id", "lft")
                    .distinct("id", "tree_id", "lft")
                )
            context["department_set"] = department_set
            context["staff_order"] = Staff.get_or_create_order_responsible()

        # use of str() to avoid "12 345" when rendering the template
        context["producer_id"] = str(self.producer_id)
        # use of str() to avoid "12 345" when rendering the template
        context["department_id"] = str(self.department_id)

        if self.is_basket:
            context["is_basket"] = "yes"
            context["is_select_view"] = EMPTY_STRING
            context["is_basket_view"] = "active"
        else:
            context["is_basket"] = EMPTY_STRING
            context["is_select_view"] = "active"
            context["is_basket_view"] = EMPTY_STRING

        context["is_like"] = "yes" if self.is_like else EMPTY_STRING
        context["communication"] = self.communication
        context["q"] = self.q
        context["may_order"] = self.may_order
        context[
            "display_anonymous_order_form"
        ] = REPANIER_SETTINGS_DISPLAY_ANONYMOUS_ORDER_FORM
        return context

    def get_queryset(self):
        from repanier.apps import REPANIER_SETTINGS_DISPLAY_ANONYMOUS_ORDER_FORM

        if self.customer is None and (
            not REPANIER_SETTINGS_DISPLAY_ANONYMOUS_ORDER_FORM
            or self.is_basket
            or self.is_like
        ):
            return OfferItemReadOnly.objects.none()

        if self.is_basket:
            qs = OfferItemReadOnly.objects.filter(
                permanence_id=self.permanence.id,
                may_order=True,  # Don't display technical products.
                purchase__customer__user=self.user,
                purchase__quantity_ordered__gt=0,
            )
        else:
            qs = OfferItemReadOnly.objects.filter(
                permanence_id=self.permanence.id,
                is_active=True,
                may_order=True,  # Don't display technical products.
            )
            if self.producer_id != "all":
                qs = qs.filter(producer_id=self.producer_id)
            if self.department_id != "all":
                department = (
                    LUT_DepartmentForCustomer.objects.filter(id=self.department_id)
                    .only("lft", "rght", "tree_id")
                    .first()
                )
                if department is not None:
                    tmp_qs = qs.filter(
                        department_for_customer__lft__gte=department.lft,
                        department_for_customer__rght__lte=department.rght,
                        department_for_customer__tree_id=department.tree_id,
                    )
                    if tmp_qs.exists():
                        # Restrict to this department only if no product exists in it
                        qs = tmp_qs
                    else:
                        # otherwise, act like self.department_id == 'all'
                        self.department_id = "all"
            if self.q and self.may_order:
                qs = qs.filter(
                    long_name_v2__icontains=self.q,
                )
        qs = qs.order_by("order_sort_order_v2")
        if self.is_like:
            qs = qs.filter(product__likes__id=self.user.id)
        return qs.distinct()
