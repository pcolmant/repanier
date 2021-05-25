from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import translation
from django.views.generic import ListView

from repanier.const import EMPTY_STRING
from repanier.models import CustomerInvoice
from repanier.models.box import BoxContent
from repanier.models.customer import Customer
from repanier.models.lut import LUT_DepartmentForCustomer
from repanier.models.offeritem import OfferItemReadOnly
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.staff import Staff
from repanier.tools import (
    sint,
    permanence_ok_or_404,
    html_box_content,
    get_repanier_template_name,
    get_html_basket_message,
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
        self.box_id = "all"
        self.is_box = False
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
            self.box_id = self.request.GET.get("box", "all")
            if self.box_id != "all":
                self.box_id = sint(self.box_id)
                self.is_box = True
                # Do not display "all department" as selected
                self.department_id = None
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
                        offeritem__is_box=False,
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
                        offeritem__is_box=False,
                    )
                    .order_by("tree_id", "lft")
                    .distinct("id", "tree_id", "lft")
                )
            context["department_set"] = department_set
            context["box_set"] = OfferItemReadOnly.objects.filter(
                permanence_id=self.permanence.id,
                is_box=True,
                is_active=True,
                may_order=True,
            ).order_by("customer_unit_price", "unit_deposit", "long_name_v2")
            context["staff_order"] = Staff.get_or_create_order_responsible()

        # use of str() to avoid "12 345" when rendering the template
        context["producer_id"] = str(self.producer_id)
        # use of str() to avoid "12 345" when rendering the template
        context["department_id"] = str(self.department_id)

        context["box_id"] = str(self.box_id)
        context["is_box"] = "yes" if self.is_box else EMPTY_STRING
        if self.is_box:
            offer_item = get_object_or_404(OfferItemReadOnly, id=self.box_id)
            context["box_description"] = html_box_content(offer_item, self.user)
        if self.is_basket:
            context["is_basket"] = "yes"
            context["is_select_view"] = EMPTY_STRING
            context["is_basket_view"] = "active"

            if self.may_order:
                translation.activate(self.customer.language)
                customer_invoice = CustomerInvoice.objects.filter(
                    permanence_id=self.permanence.id, customer_id=self.customer.id
                ).first()
                if customer_invoice is None:
                    customer_invoice = CustomerInvoice.objects.create(
                        permanence_id=self.permanence.id,
                        customer_id=self.customer.id,
                        status=self.permanence.status,
                        customer_charged_id=self.customer.id,
                    )
                    customer_invoice.set_order_delivery(delivery=None)
                    customer_invoice.calculate_order_price()
                    customer_invoice.save()
                if customer_invoice.delivery is not None:
                    status = customer_invoice.delivery.status
                else:
                    status = customer_invoice.status
                basket_message = get_html_basket_message(
                    self.customer, self.permanence, status
                )
                html = customer_invoice.get_html_my_order_confirmation(
                    permanence=self.permanence,
                    is_basket=True,
                    basket_message=basket_message,
                )
                context["span_btn_confirm_order"] = html["#span_btn_confirm_order"]
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
        if self.is_box:
            offer_item = (
                OfferItemReadOnly.objects.filter(
                    id=self.box_id, permanence_id=self.permanence.id, may_order=True
                )
                .only("product_id")
                .first()
            )
            if offer_item is not None and offer_item.product_id is not None:
                box_id = offer_item.product_id
            else:
                # A bot is back
                return OfferItemReadOnly.objects.none()
            product_ids = BoxContent.objects.filter(box_id=box_id).only("product_id")
            qs = OfferItemReadOnly.objects.filter(
                Q(
                    permanence_id=self.permanence.id,
                    may_order=True,
                    product=box_id,
                )
                | Q(
                    permanence_id=self.permanence.id,
                    may_order=True,
                    product__box_content__in=product_ids,
                )
            )
        else:
            if self.is_basket:
                qs = OfferItemReadOnly.objects.filter(
                    permanence_id=self.permanence.id,
                    may_order=True,  # Don't display technical products.
                    purchase__customer__user=self.user,
                    purchase__quantity_ordered__gt=0,
                    # is_box=False,
                )
            else:
                qs = OfferItemReadOnly.objects.filter(
                    Q(
                        permanence_id=self.permanence.id,
                        is_active=True,
                        is_box=False,  # Don't display boxes -> Added from customers reactions.
                        may_order=True,  # Don't display technical products.
                    )
                    | Q(
                        permanence_id=self.permanence.id,
                        is_box_content=True,
                        may_order=True,  # Don't display technical products.
                    )
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
