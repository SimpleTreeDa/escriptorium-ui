from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import override_settings

from core.models import Document, Script
from core.tests.factory import CoreFactoryTestCase

SYRIAC_SCRIPTS_RTL = ("core", "0076_syriac_scripts_rtl")

# the scripts as 0019_load_scripts created them, and two that must not change
SCRIPTS_BEFORE = {
    "Syrc": "horizontal-rl",
    "Syre": "horizontal-lr",
    "Syrj": "horizontal-lr",
    "Syrn": "horizontal-lr",
    "Arab": "horizontal-rl",
    "Latn": "horizontal-lr",
}


# The test settings disable migrations and build the test database from the
# models: load the real migrations to run this one.
@override_settings(MIGRATION_MODULES={})
class SyriacScriptsRtlMigrationTestCase(CoreFactoryTestCase):
    def setUp(self):
        super().setUp()
        for iso_code, text_direction in SCRIPTS_BEFORE.items():
            Script.objects.create(name=iso_code, iso_code=iso_code, text_direction=text_direction)
        self.document = self.factory.make_document(main_script=Script.objects.get(iso_code="Syre"))

    def migrate(self, backwards=False):
        # what `manage.py migrate` runs, from the state before the migration,
        # without recording it
        loader = MigrationLoader(connection)
        migration = loader.get_migration(*SYRIAC_SCRIPTS_RTL)
        state = loader.project_state(SYRIAC_SCRIPTS_RTL, at_end=False)
        with connection.schema_editor(atomic=migration.atomic) as schema_editor:
            if backwards:
                migration.unapply(state, schema_editor)
            else:
                migration.apply(state, schema_editor)

    def text_directions(self):
        return dict(Script.objects.values_list("iso_code", "text_direction"))

    def default_text_direction(self):
        # a new instance, default_text_direction is a cached property
        return Document.objects.get(pk=self.document.pk).default_text_direction

    def test_forwards(self):
        self.assertEqual(self.default_text_direction(), "ltr")

        self.migrate()

        self.assertEqual(self.text_directions(), {
            "Syrc": "horizontal-rl",
            "Syre": "horizontal-rl",
            "Syrj": "horizontal-rl",
            "Syrn": "horizontal-rl",
            "Arab": "horizontal-rl",
            "Latn": "horizontal-lr",
        })
        self.assertEqual(self.default_text_direction(), "rtl")
        # the order of lines and regions stays as it was
        self.assertEqual(Document.objects.get(pk=self.document.pk).read_direction, "ltr")

    def test_backwards(self):
        self.migrate()
        self.migrate(backwards=True)

        # Syrc stays right-to-left
        self.assertEqual(self.text_directions(), SCRIPTS_BEFORE)
        self.assertEqual(self.default_text_direction(), "ltr")
