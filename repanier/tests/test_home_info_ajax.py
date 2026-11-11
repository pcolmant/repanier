"""Tests of the home page opened permanences box (template rendering).

home_info_ajax now renders repanier/home_info.html instead of building
the markup in the Python view.
"""
import datetime

from django.test import TestCase, override_settings

from repanier.const import SaleStatus
from repanier.models.permanence import Permanence


# The test suite otherwise upgrades every http request to https (301).
@override_settings(
    SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False
)
class HomeInfoAjaxTest(TestCase):
    def _get(self):
        return self.client.get("/fr/repanier/ajax/home-info/")

    def test_without_opened_permanence_the_fragment_is_not_served(self):
        response = self._get()
        self.assertEqual(response.status_code, 404)

    def test_with_an_opened_permanence_the_box_renders_from_the_template(self):
        permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.OPENED,
            highest_status=SaleStatus.OPENED,
        )
        permanence.offer_description_v2 = "Come and order fresh products."
        permanence.save()
        response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "repanier/home_info.html")
        data = response.json()
        self.assertIn("#containerInfo", data)
        fragment = data["#containerInfo"]
        self.assertIn('class="card-header"', fragment)
        self.assertIn("Come and order fresh products.", fragment)
        self.assertIn('class="card-body"', fragment)
        self.assertIn('class="card border-default mb-3"', fragment)

    def test_a_permanence_without_description_shows_only_its_header(self):
        permanence = Permanence.objects.create(
            permanence_date=datetime.date.today(),
            status=SaleStatus.OPENED,
            highest_status=SaleStatus.OPENED,
        )
        response = self._get()
        fragment = response.json()["#containerInfo"]
        self.assertIn('class="card-header"', fragment)
        self.assertNotIn('class="card-body"', fragment)
