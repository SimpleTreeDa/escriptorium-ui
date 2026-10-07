"""The "Check TEI readiness" endpoint: the export's checks, without exporting."""
import os
import shutil

from django.urls import reverse

from core.models import (
    Block,
    BlockType,
    CascadeUpdate,
    DocumentMetadata,
    Line,
    LineTranscription,
    Metadata,
)
from core.tests.factory import CoreFactoryTestCase
from escriptorium.test_settings import MEDIA_ROOT


class TEIReadinessTestCase(CoreFactoryTestCase):
    def setUp(self):
        super().setUp()
        self.document = self.factory.make_document(name="Example MS 1")
        self.owner = self.document.owner
        self.transcription = self.document.transcriptions.get(name="manual")
        main = BlockType.objects.create(name="MainZone")
        self.document.valid_block_types.add(main)
        with CascadeUpdate.bypass():
            self.part = self.factory.make_part(document=self.document, name="1r")
            block = Block.objects.create(document_part=self.part, typology=main, box=[[0, 0], [10, 0], [10, 10]])
            line = Line.objects.create(document_part=self.part, block=block, mask=[[0, 0], [10, 0], [10, 5]])
            LineTranscription.objects.create(line=line, transcription=self.transcription, content="ܐ",
                                             version_author=self.owner.username)
        self.data = {"transcription": self.transcription.pk, "region_types": [main.pk, "Orphan", "Undefined"]}

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def check(self, data=None, user=None):
        self.client.force_login(user or self.owner)
        return self.client.post(reverse("api:document-tei-check", kwargs={"pk": self.document.pk}),
                                data or self.data, content_type="application/json")

    def test_not_ready(self):
        resp = self.check()
        self.assertEqual(resp.status_code, 200, resp.content)
        report = resp.json()
        self.assertFalse(report["ready"])
        self.assertEqual(report["pages"], 1)
        self.assertEqual(sorted(problem["message"] for problem in report["errors"]), [
            'Document: metadata "record_id" is missing',
            'Document: metadata "repository" is missing',
            'Document: metadata "shelfmark" is missing',
            'Page 1 (default.png): no work; set page metadata "work" or document metadata "work"',
        ])
        self.assertEqual(report["summary"]["metadata"]["errors"], 3)
        # nothing was exported
        store = self.owner.get_document_store_path()
        self.assertEqual(os.listdir(store) if os.path.exists(store) else [], [])

    def test_ready(self):
        for key, value in (("record_id", "ms-1"), ("Repository", "Example Library"), ("Shelfmark", "MS 1"),
                           ("work", "Hymns on Faith")):
            DocumentMetadata.objects.create(document=self.document, key=Metadata.objects.get_or_create(name=key)[0],
                                            value=value)
        resp = self.check({**self.data, "schema": True})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()["ready"], resp.json()["errors"])
        self.assertEqual(resp.json()["record_id"], "ms-1")

    def test_invalid_choices(self):
        resp = self.check({"transcription": 0, "region_types": ["Orphan"]})
        self.assertEqual(resp.status_code, 400)

    def test_access(self):
        self.assertEqual(self.check(user=self.factory.make_user()).status_code, 404)
