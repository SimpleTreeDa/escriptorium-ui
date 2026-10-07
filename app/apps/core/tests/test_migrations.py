from importlib import import_module

from django.apps import apps

from core.models import Document, Script
from core.tests.factory import CoreFactoryTestCase

# Test settings disable migrations, so the data migration's functions are
# called directly against rows created here.
syriac_scripts_rtl = import_module("core.migrations.0076_syriac_scripts_rtl")


class SyriacScriptsRtlMigrationTestCase(CoreFactoryTestCase):
    def setUp(self):
        super().setUp()
        for iso_code in ["Syre", "Syrj", "Syrn", "Latn"]:
            Script.objects.create(name=iso_code, iso_code=iso_code,
                                  text_direction=Script.TEXT_DIRECTION_HORIZONTAL_LTR)
        Script.objects.create(name="Syriac", iso_code="Syrc",
                              text_direction=Script.TEXT_DIRECTION_HORIZONTAL_RTL)

    def directions(self):
        return dict(Script.objects.values_list("iso_code", "text_direction"))

    def test_forward(self):
        syriac_scripts_rtl.set_rtl(apps, None)

        self.assertEqual(self.directions(), {
            "Syre": "horizontal-rl",
            "Syrj": "horizontal-rl",
            "Syrn": "horizontal-rl",
            "Syrc": "horizontal-rl",
            "Latn": "horizontal-lr",
        })

        document = self.factory.make_document(main_script=Script.objects.get(iso_code="Syre"))
        document = Document.objects.get(pk=document.pk)
        self.assertEqual(document.default_text_direction, "rtl")

    def test_backward(self):
        syriac_scripts_rtl.set_rtl(apps, None)
        syriac_scripts_rtl.set_ltr(apps, None)

        self.assertEqual(self.directions(), {
            "Syre": "horizontal-lr",
            "Syrj": "horizontal-lr",
            "Syrn": "horizontal-lr",
            "Syrc": "horizontal-rl",
            "Latn": "horizontal-lr",
        })
