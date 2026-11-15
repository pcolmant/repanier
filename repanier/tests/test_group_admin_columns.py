"""The group list shows the passport state and the member counter.

Two columns on the admin of the groups: the passport flag of the
mirror group (Passeport) and the members it counts today (#
passeports, an empty cell when there is none - like the other
optional cells of the admin).
"""
from django.contrib import admin as django_admin
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from repanier.admin.group import GroupWithUserDataAdmin
from repanier.models.customer import Customer
from repanier.models.group import Group


def group_admin():
    # A ModelAdmin is not deep copyable: build one per test instead
    # of sharing it through setUpTestData.
    return GroupWithUserDataAdmin(Group, django_admin.site)


class GroupAdminColumnsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        group_user = User.objects.create_user(
            username="groupe@example.com", email="groupe@example.com", password="x"
        )
        cls.group = Customer.objects.create(
            user=group_user,
            short_basket_name="MonGroupe",
            may_order=True,
            is_group=True,
        )
        member_user = User.objects.create_user(
            username="membre@example.com",
            email="membre@example.com",
            password="x",
        )
        cls.member = Customer.objects.create(
            user=member_user,
            short_basket_name="Membre",
            may_order=True,
            group_id=cls.group.id,
        )

    def test_the_two_columns_belong_to_the_list(self):
        self.assertIn("get_passport", group_admin().list_display)
        self.assertIn("get_passport_members", group_admin().list_display)

    def test_the_passport_column_follows_the_flag(self):
        group = Group.objects.get(id=self.group.id)
        self.assertIs(group_admin().get_passport(group), False)
        Customer.objects.filter(id=self.group.id).update(
            accepts_passport_members=True
        )
        group = Group.objects.get(id=self.group.id)
        self.assertIs(group_admin().get_passport(group), True)

    def test_the_members_column_counts_without_one_query_per_row(self):
        request = RequestFactory().get("/")
        query_set = group_admin().get_queryset(request)
        group = query_set.get(id=self.group.id)
        # The counter travels with the queryset: one query for the
        # whole list, not one per row - and it counts one member.
        self.assertEqual(group.member_counter, 1)
        self.assertEqual(group_admin().get_passport_members(group), "1")

    def test_a_group_without_member_shows_an_empty_cell(self):
        Customer.objects.filter(id=self.member.id).update(group_id=None)
        request = RequestFactory().get("/")
        query_set = group_admin().get_queryset(request)
        group = query_set.get(id=self.group.id)
        self.assertEqual(group.member_counter, 0)
        self.assertEqual(group_admin().get_passport_members(group), "")
