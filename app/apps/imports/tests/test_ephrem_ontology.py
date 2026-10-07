"""
The Ephrem TEI profile's type map and vocabulary (imports/tei/profile.py), and the command that
adds the Ephrem ontology to documents.
"""
import json
import os
from io import StringIO

from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase

from core.models import AnnotationTaxonomy, DocumentPart
from core.tests.factory import CoreFactoryTestCase
from imports.tei import profile


class EphremProfileTestCase(SimpleTestCase):
    def test_statuses_are_the_editorial_statuses(self):
        self.assertEqual([(code, str(label)) for code, label in DocumentPart.EDITORIAL_STATUS_CHOICES],
                         list(profile.STATUSES))

    def test_region_types(self):
        roles = {
            "MainZone": profile.MAIN, "MainZone:left": profile.MAIN, "MainZone:right": profile.MAIN,
            "MainZone#2": profile.MAIN, "Main": profile.MAIN, "": profile.MAIN, None: profile.MAIN,
            "Left Column": profile.MAIN, "MainRight": profile.MAIN,
            "Title": profile.HEAD, "title": profile.HEAD,
            "MarginTextZone": profile.NOTE_MARGIN, "Commentary": profile.NOTE_COMMENTARY,
            "RunningTitleZone": profile.FW_HEADER, "Running Header": profile.FW_HEADER,
            "NumberingZone": profile.FW_PAGE_NUMBER, "QuireMarksZone": profile.FW_SIGNATURE,
            "Illustration": profile.NON_TEXT, "GraphicZone": profile.NON_TEXT, "DecorationZone": profile.NON_TEXT,
            "Footnotes": None, "TableZone": None,
        }
        self.assertEqual({name: profile.region_role(name) for name in roles}, roles)

    def test_line_types(self):
        roles = {
            "DefaultLine": profile.MAIN, "DefaultLine:left": profile.MAIN, "Main": profile.MAIN, None: profile.MAIN,
            "HeadingLine": profile.HEAD, "ParagraphStart": profile.PARAGRAPH,
            "InterlinearLine": profile.ADD, "Correction": profile.ADD,
            "Numbering": profile.FW_PAGE_NUMBER, "Signature": profile.FW_SIGNATURE,
            "DropCapitalLine": None,
        }
        self.assertEqual({name: profile.line_role(name) for name in roles}, roles)

    def test_every_ontology_type_is_mapped(self):
        for name in profile.ONTOLOGY["region_types"]:
            self.assertIsNotNone(profile.region_role(name), name)
        for name in profile.ONTOLOGY["line_types"]:
            self.assertIsNotNone(profile.line_role(name), name)
        self.assertEqual([taxonomy["name"] for taxonomy in profile.ONTOLOGY["taxonomy"]],
                         list(profile.ANNOTATION_ATTRIBUTES))
        for taxonomy in profile.ONTOLOGY["taxonomy"]:
            self.assertEqual(taxonomy["components"], list(profile.ANNOTATION_ATTRIBUTES[taxonomy["name"]]))

    def test_languages(self):
        self.assertEqual(profile.approved_language("SYR-syrj"), "syr-Syrj")
        self.assertEqual(profile.approved_language(" syr-x-syrm "), "syr-x-syrm")
        self.assertIsNone(profile.approved_language("Syriac"))
        self.assertIsNone(profile.approved_language("syc"))

    def test_docs_copy_of_the_ontology(self):
        path = os.path.join(settings.BASE_DIR, os.pardir, "docs", "tei", "ephrem-ontology.json")
        if not os.path.exists(path):
            self.skipTest("docs/ is not in this checkout")
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), profile.ONTOLOGY)


class ApplyEphremOntologyTestCase(CoreFactoryTestCase):
    def apply(self, *args):
        out = StringIO()
        call_command("apply_ephrem_ontology", *args, stdout=out)
        return out.getvalue()

    def assertOntology(self, document):
        self.assertTrue(set(profile.ONTOLOGY["region_types"])
                        <= set(document.valid_block_types.values_list("name", flat=True)))
        self.assertTrue(set(profile.ONTOLOGY["line_types"])
                        <= set(document.valid_line_types.values_list("name", flat=True)))
        taxonomies = AnnotationTaxonomy.objects.filter(document=document).order_by("name")
        self.assertEqual([(t.name, sorted(t.components.values_list("name", flat=True))) for t in taxonomies], [
            ("add", ["place"]), ("gap", ["extent", "reason", "unit"]), ("unclear", ["reason"]),
        ])
        self.assertEqual(sorted(document.annotationcomponent_set.values_list("name", flat=True)),
                         ["extent", "place", "reason", "unit"])

    def test_apply_twice(self):
        document = self.factory.make_document()
        out = self.apply(str(document.pk))
        self.assertIn('Created a new taxonomy named "unclear"', out)
        self.assertOntology(document)

        out = self.apply(str(document.pk))
        self.assertNotIn("Created a new", out)
        self.assertOntology(document)
        self.assertEqual(document.valid_block_types.filter(name="MarginTextZone").count(), 1)

    def test_project(self):
        project = self.factory.make_project(name="Ephrem")
        documents = [self.factory.make_document(project=project, name=name) for name in ("A", "B")]
        self.apply("--project", project.slug)
        for document in documents:
            self.assertOntology(document)

    def test_unknown_document(self):
        with self.assertRaises(CommandError):
            self.apply("999999")
        with self.assertRaises(CommandError):
            self.apply()
