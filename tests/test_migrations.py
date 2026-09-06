import unittest
from pathlib import Path

from apps.api import database
from apps.api import migrations


class MigrationContractTests(unittest.TestCase):
    def test_migration_files_are_ordered_and_versioned(self):
        files = migrations.discover_migrations()

        self.assertEqual(files[0].name, "001_init.sql")
        self.assertEqual(files[-1].name, "041_job_provenance.sql")
        self.assertEqual(len(files), len({path.name for path in files}))
        self.assertEqual(
            [path.name for path in files],
            sorted(path.name for path in files),
        )

    def test_sql_splitter_keeps_semicolons_inside_literals(self):
        statements = migrations.split_sql_statements(
            "-- comment\n"
            "CREATE TABLE sample (name TEXT DEFAULT 'a;b');\n"
            "CREATE INDEX sample_name ON sample(name);"
        )

        self.assertEqual(len(statements), 2)
        self.assertIn("'a;b'", statements[0])
        self.assertTrue(statements[1].startswith("CREATE INDEX"))

    def test_database_uses_the_migration_runner(self):
        source = Path(database.__file__).read_text(encoding="utf-8")

        self.assertIn("apply_migrations(conn)", source)
        self.assertNotIn("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS", source)
