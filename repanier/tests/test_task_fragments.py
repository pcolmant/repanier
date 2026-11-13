"""Tests of the task fragments (display_task, select_task) and the like button.

All three rendered from templates instead of building markup strings in
Python: the tests pin each variant of the task select, the two display
variants and the two like states.
"""
import datetime

from django.contrib.auth.models import User
from django.template import Context, Template
from django.test import RequestFactory, TestCase

from repanier.const import SaleStatus
from repanier.models.customer import Customer
from repanier.models.lut import LUT_PermanenceRole
from repanier.models.permanence import Permanence
from repanier.models.permanenceboard import PermanenceBoard
from repanier.models.producer import Producer
from repanier.models.product import Product


def render_tag(request, template_source, **ctx):
    tpl = Template(template_source)
    return tpl.render(Context({"request": request, **ctx}))


SELECT_TAG = "{% load repanier_tags %}{% repanier_select_task task_id=task.id %}"
DISPLAY_TAG = "{% load repanier_tags %}{% repanier_display_task task_id=task.id %}"
BTN_LIKE_TAG = "{% load repanier_tags %}{% repanier_btn_like offer_item=offer %}"


class TaskFragmentTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.OPENED
        )
        cls.user = User.objects.create_user(
            username="client@example.com", email="client@example.com", password="x"
        )
        cls.customer = Customer.objects.create(
            user=cls.user,
            short_basket_name="Client",
            long_basket_name="Client Long",
            may_order=True,
        )
        other_user = User.objects.create_user(
            username="other@example.com", email="other@example.com", password="x"
        )
        cls.other = Customer.objects.create(
            user=other_user,
            short_basket_name="Autre",
            long_basket_name="Autre Long",
            may_order=True,
        )

    def create_board(self, role, customer=None, status=None):
        if status is not None:
            self.permanence.status = status
            self.permanence.save()
        return PermanenceBoard.objects.create(
            permanence=self.permanence,
            permanence_role=LUT_PermanenceRole.objects.create(short_name_v2=role),
            customer=customer,
        )

    def request(self):
        request = RequestFactory().get("/dummy/")
        request.user = self.user
        return request

    def test_own_task_is_editable_while_ordering(self):
        board = self.create_board("Permanence", customer=self.customer)
        html = render_tag(self.request(), SELECT_TAG, task=board)
        self.assertIn('id="task{}"'.format(board.id), html)
        self.assertIn("task_ajax({})".format(board.id), html)
        self.assertIn("<b><i>", html)
        self.assertIn('<option value="1" selected>Client Long</option>', html)

    def test_foreign_task_is_read_only(self):
        board = self.create_board("Permanence", customer=self.other)
        html = render_tag(self.request(), SELECT_TAG, task=board)
        self.assertIn("<select", html)
        self.assertNotIn("task_ajax", html)
        self.assertNotIn("<b><i>", html)
        self.assertIn('<option value="0" selected>Autre Long</option>', html)

    def test_free_task_is_open_to_registration_while_ordering(self):
        board = self.create_board("Permanence")
        html = render_tag(self.request(), SELECT_TAG, task=board)
        self.assertIn("task_ajax({})".format(board.id), html)
        self.assertIn('<option value="0" selected>---</option>', html)
        self.assertIn('<option value="1">Client Long</option>', html)

    def test_free_task_is_closed_after_the_orders(self):
        board = self.create_board("Permanence", status=SaleStatus.INVOICED)
        html = render_tag(self.request(), SELECT_TAG, task=board)
        self.assertIn("<select", html)
        self.assertNotIn("task_ajax", html)
        self.assertIn('<option value="0" selected>---</option>', html)
        self.assertNotIn('<option value="1">', html)

    def test_task_of_a_role_without_registration_renders_nothing(self):
        role = LUT_PermanenceRole.objects.create(
            short_name_v2="Responsable", customers_may_register=False
        )
        board = PermanenceBoard.objects.create(
            permanence=self.permanence, permanence_role=role
        )
        html = render_tag(self.request(), SELECT_TAG, task=board)
        self.assertEqual(html.strip(), "")

    def test_display_task_bold_when_registration_is_not_allowed(self):
        registerable = LUT_PermanenceRole.objects.create(short_name_v2="Standard")
        board = PermanenceBoard.objects.create(
            permanence=self.permanence, permanence_role=registerable
        )
        html = render_tag(self.request(), DISPLAY_TAG, task=board)
        self.assertIn("Standard", html)
        self.assertNotIn("<p><b>", html)

        closed_role = LUT_PermanenceRole.objects.create(
            short_name_v2="Responsable", customers_may_register=False
        )
        board2 = PermanenceBoard.objects.create(
            permanence=self.permanence, permanence_role=closed_role
        )
        html = render_tag(self.request(), DISPLAY_TAG, task=board2)
        self.assertIn("<p><b>Responsable</b></p>", html)


class BtnLikeFragmentTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="liker@example.com", email="liker@example.com", password="x"
        )
        producer = Producer.objects.create(short_profile_name="Ferme")
        permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(), status=SaleStatus.OPENED
        )
        product = Product.objects.create(
            producer=producer,
            long_name_v2="Pommes",
            order_unit="100",
            producer_unit_price="2.50",
            vat_level="100",
            stock="99",
        )
        product.is_into_offer = True
        product.save()
        cls.product = product
        cls.offer_item = product.get_or_create_offer_item(permanence)

    def request(self):
        request = RequestFactory().get("/dummy/")
        request.user = self.user
        return request

    def test_not_liked_shows_an_empty_heart(self):
        html = render_tag(self.request(), BTN_LIKE_TAG, offer=self.offer_item)
        self.assertIn('class="btn_like{}"'.format(self.offer_item.id), html)
        self.assertIn("bi-heart", html)
        self.assertNotIn("bi-heart-fill", html)
        self.assertIn("like_ajax({})".format(self.offer_item.id), html)

    def test_liked_shows_a_filled_heart(self):
        self.product.likes.add(self.user.id)
        html = render_tag(self.request(), BTN_LIKE_TAG, offer=self.offer_item)
        self.assertIn("bi-heart-fill", html)
        self.assertIn("like_ajax({})".format(self.offer_item.id), html)
