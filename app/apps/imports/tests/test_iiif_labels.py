"""IIIF imports keep the canvas labels as page names, and reuse metadata keys whatever their case."""
import os
from unittest import mock

from django.test import SimpleTestCase
from django.urls import reverse

from core.models import DocumentMetadata, Metadata
from core.tests.factory import CoreFactoryTestCase
from imports.parsers import iiif_text

MOCK_MANIFEST = os.path.join(os.path.dirname(__file__), 'mocks', 'iiif.json')


class IIIFTextTestCase(SimpleTestCase):
    def test_labels(self):
        self.assertEqual(iiif_text(" f. 1r "), "f. 1r")
        self.assertEqual(iiif_text({"@value": "f. 1v", "@language": "en"}), "f. 1v")
        self.assertEqual(iiif_text([{"@value": "f. 2r"}, {"@value": "fol. 2r"}]), "f. 2r")
        self.assertEqual(iiif_text({"none": ["2v"]}), "2v")
        self.assertEqual(iiif_text(12), "12")
        self.assertEqual(iiif_text(None), "")
        self.assertEqual(iiif_text([]), "")

    def test_values(self):
        self.assertEqual(iiif_text(["Syriac", {"@value": "Greek"}], join="; "), "Syriac; Greek")
        self.assertEqual(iiif_text({"en": ["Add MS 14571"]}, join="; "), "Add MS 14571")


class IIIFImportTestCase(CoreFactoryTestCase):
    def setUp(self):
        super().setUp()
        self.doc = self.factory.make_document()
        self.user = self.doc.owner

    def import_manifest(self):
        self.client.force_login(self.user)
        # the image downloads get the manifest too, which doesn't matter here
        with open(MOCK_MANIFEST, 'rb') as fh:
            response = mock.Mock(content=fh.read(), status_code=200)
        with mock.patch('requests.get', return_value=response), \
                mock.patch('imports.parsers.ParserDocument.post_process_image'):
            resp = self.client.post(reverse('api:import-list', kwargs={'document_pk': self.doc.pk}),
                                    {'mode': 'iiif', 'iiif_uri': 'http://some.com/url/'})
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_canvas_labels_are_page_names(self):
        self.import_manifest()
        parts = list(self.doc.parts.order_by('order'))
        self.assertEqual([part.name for part in parts], ['NP', '1', '64', '121', '134'])
        # the stored file names are still generated, and the image's address is kept
        self.assertTrue(all(part.original_filename.endswith('default.jpg') for part in parts))
        self.assertTrue(all(part.source.startswith('http') for part in parts))

    def test_metadata_keys_in_any_case(self):
        existing = Metadata.objects.create(name='shelfmark')
        self.import_manifest()
        shelfmark = DocumentMetadata.objects.get(document=self.doc, key__name__iexact='shelfmark')
        self.assertEqual(shelfmark.key, existing)
        self.assertTrue(shelfmark.value.endswith('Ms.0.033'))
        self.assertFalse(Metadata.objects.filter(name='Shelfmark').exists())
        # empty values are not imported
        self.assertFalse(DocumentMetadata.objects.filter(document=self.doc, key__name='Repository').exists())
