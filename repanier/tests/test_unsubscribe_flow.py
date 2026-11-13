"""The unsubscribe flow.

The mail footer link must stop the general mails without login - the
token signs the click - and the landing page must let the customer
change his mind alone: the announcement mails are the only ones
carrying the link. Order confirmations are transactional, they keep
arriving in both states.
"""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from repanier.models.customer import Customer


# The unsubscribe link is clicked - and the coming back form posted -
# over plain http in the test client: the real site stays https only.
@override_settings(
    SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False
)
class UnsubscribeFlowTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="reader@example.com", email="reader@example.com", password="x"
        )
        cls.customer = Customer.objects.create(
            user=cls.user, short_basket_name="Reader", may_order=True
        )

    def _unsubscribe_url(self):
        customer_id, token = self.customer.make_token().split(":", 1)
        # The mails of the tests run with the French catalog: the
        # language aware middleware prefixes the unprefixed url with
        # /fr, turning a posted form into a get - the browser lands on
        # the prefixed page, so the test uses it directly.
        return "/fr/repanier/unsubscribe/{}/{}/".format(customer_id, token)

    def _refresh(self):
        self.customer.refresh_from_db()

    def test_the_link_stops_the_mails(self):
        self.assertTrue(self.customer.subscribe_to_email)
        response = self.client.get(self._unsubscribe_url(), follow=True)
        self.assertEqual(response.status_code, 200)
        self._refresh()
        self.assertFalse(self.customer.subscribe_to_email)

    def test_the_landing_page_offers_the_way_back(self):
        response = self.client.get(self._unsubscribe_url(), follow=True)
        # The re-subscribe action is a post form on the landing page.
        self.assertContains(response, 'method="post"')

    def test_the_way_back_restarts_the_mails(self):
        self.client.get(self._unsubscribe_url(), follow=True)
        self._refresh()
        self.assertFalse(self.customer.subscribe_to_email)
        response = self.client.post(self._unsubscribe_url(), follow=True)
        self.assertEqual(response.status_code, 200)
        self._refresh()
        self.assertTrue(self.customer.subscribe_to_email)

    def test_a_wrong_token_is_refused(self):
        self.customer.make_token()
        response = self.client.get(
            "/fr/repanier/unsubscribe/{}/wrong/".format(self.customer.id), follow=True
        )
        self.assertEqual(response.status_code, 200)
        self._refresh()
        self.assertTrue(self.customer.subscribe_to_email)

    def test_an_unknown_customer_is_refused(self):
        token = self.customer.make_token().split(":", 1)[1]
        response = self.client.get(
            "/fr/repanier/unsubscribe/999999/{}/".format(token), follow=True
        )
        self.assertEqual(response.status_code, 200)
        self._refresh()
        self.assertTrue(self.customer.subscribe_to_email)
