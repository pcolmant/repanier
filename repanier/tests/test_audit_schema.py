from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from repanier.management.commands.audit_schema import audit_table
from repanier.models.customer import Customer

MODEL_COLUMNS = [
    field.column for field in Customer._meta.concrete_fields
]


class AuditTableTest(TestCase):
    """The comparator of one table, spoken the way postgres speaks
    it: (nullable?, default). The pigal case is the whole point: a
    fossil column with NOT NULL and no default breaks every INSERT,
    while the nullable fossils and the defaulted fossils only
    collect dust."""

    def test_the_pigal_fossil_is_blocking_and_only_it(self):
        description = {
            "id": (False, None),  # a column the model knows too
            "email": (True, None),
            "cache_part_a_v2": (False, None),  # the pigal fossil
            "cache_part_b_v2": (False, "'0'"),  # saved by its default
            "cache_v2": (True, None),  # saved by its NULL
        }
        model_columns = ["id", "email"]
        stale, blocking_stale, missing = audit_table(
            "repanier_customer", model_columns, description=description
        )
        self.assertEqual(blocking_stale, ["cache_part_a_v2"])
        self.assertEqual(
            stale, ["cache_part_a_v2", "cache_part_b_v2", "cache_v2"]
        )
        self.assertEqual(missing, [])

    def test_missing_columns_speak_like_a_migration_never_run(self):
        # A table which misses most of its model: the database
        # stopped half way, every SELECT of the model will fail.
        description = {
            "id": (False, None),
            "short_basket_name": (True, None),
        }
        stale, blocking_stale, missing = audit_table(
            "repanier_customer", model_columns=MODEL_COLUMNS,
            description=description,
        )
        self.assertEqual(stale, [])
        self.assertEqual(blocking_stale, [])
        self.assertIn("city", missing)
        self.assertIn("picture", missing)


class AuditSchemaCommandTest(TestCase):
    """The command walks every model of repanier and reads only:
    the verdict matches on a clean database, a dormant fossil is
    listed without alarm, and the blocked tables raise."""

    def _run(self, expect_error=False):
        from io import StringIO

        stdout = StringIO()
        try:
            call_command("audit_schema", stdout=stdout)
        except Exception as error:
            if not expect_error:
                raise
            return stdout.getvalue(), error
        self.assertFalse(expect_error, "the command should have raised")
        return stdout.getvalue(), None

    def test_a_clean_database_matches_the_models(self):
        output, error = self._run()
        self.assertIsNone(error)
        self.assertIn("the database and the models match", output)

    def test_a_stale_dormant_column_is_listed_without_alarm(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "ALTER TABLE repanier_customer ADD COLUMN cache_v2 VARCHAR(50)"
            )
        try:
            output, error = self._run()
        finally:
            with connection.cursor() as cursor:
                cursor.execute("ALTER TABLE repanier_customer DROP COLUMN cache_v2")
        # Dormant: listed but not alarmed, and the verdict still matches
        # - the dormant fossils do not block anything.
        self.assertIsNone(error)
        self.assertIn("repanier_customer", output)
        self.assertIn("stale dormant  : cache_v2", output)
        self.assertNotIn("stale blocking", output)
