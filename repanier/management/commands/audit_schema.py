"""Audit the schema of the site against the models. Read only.

The migrations of a Repanier site live per site, and the databases
carry years of history - a restore of an old dump can bring back
columns the code dropped long ago. The invisible kills: a stale
column with NOT NULL and no default breaks every INSERT of its
table, and nothing in the code can see it. This command walks every
model of the repanier app and compares the table of the database
with the fields of the model:

- stale columns live in the database but not anymore in the model -
  dormant when a default or a NULL saves the INSERTs, blocking when
  nothing saves them (the pigal cache_part_a_v2);
- missing columns live in the model but not in the database - the
  migrations of this site did not run to the end, or the restore of
  a dump brought back an old schema.

It reads, it decides nothing, it changes nothing. Run it anywhere,
anytime:

    ./manage.py audit_schema

Exit: 0 when everything matches, 1 when something blocks.
"""
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

APP_LABEL = "repanier"


def describe_table(table):
    """The columns of a table as the database knows them:
    name -> (nullable?, default). The introspection speaks to
    sqlite, postgres and friends alike."""
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(
            cursor, table
        )
    return {
        column.name: (column.null_ok, column.default) for column in description
    }


def audit_table(table, model_columns, description=None):
    """Compare one table with the columns the model claims. Returns
    (stale, blocking_stale, missing) - blocking_stale is the pigal
    case: a column the INSERTs cannot fill. The description may be
    injected: the tests speak like postgres without a postgres."""
    if description is None:
        description = describe_table(table)
    stale = sorted(set(description) - set(model_columns))
    blocking_stale = sorted(
        column
        for column in stale
        if not description[column][0] and description[column][1] is None
    )
    missing = sorted(set(model_columns) - set(description))
    return stale, blocking_stale, missing


class Command(BaseCommand):
    help = (
        "Compare the schema of the database with the models of repanier. "
        "Read only: stale columns, missing columns, nothing else."
    )

    def handle(self, *args, **options):
        blocking_tables = 0
        for model in sorted(
            apps.get_app_config(APP_LABEL).get_models(),
            key=lambda model: model._meta.db_table,
        ):
            if model._meta.proxy:
                continue
            table = model._meta.db_table
            model_columns = [
                field.column for field in model._meta.concrete_fields
            ]
            try:
                stale, blocking_stale, missing = audit_table(
                    table, model_columns
                )
            except Exception as error:
                self.stdout.write(
                    "{}: table unreadable ({})".format(table, error)
                )
                continue
            if not (stale or missing):
                continue
            self.stdout.write(table)
            for column in stale:
                if column in blocking_stale:
                    self.stdout.write(
                        self.style.ERROR(
                            "  stale blocking : {} (NOT NULL, no default:"
                            " every INSERT fails)".format(column)
                        )
                    )
                else:
                    self.stdout.write(
                        "  stale dormant  : {}".format(column)
                    )
            for column in missing:
                self.stdout.write(
                    self.style.ERROR(
                        "  missing        : {} (the models expect it,"
                        " the database does not have it)".format(column)
                    )
                )
            if blocking_stale or missing:
                blocking_tables += 1
        if blocking_tables:
            raise CommandError(
                "{} table(s) need surgery before they work again: the "
                "blocking stale columns want a DROP COLUMN, the missing "
                "columns want the migrations of this site to run. "
                "Read the report above.".format(blocking_tables)
            )
        self.stdout.write(
            "repanier audit schema : the database and the models match."
        )
