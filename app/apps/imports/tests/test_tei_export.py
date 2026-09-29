import os
import shutil
from unittest.mock import patch
from zipfile import ZipFile

from django.utils import timezone
from lxml import etree

from core.models import (
    Block,
    BlockType,
    DocumentMetadata,
    DocumentPart,
    DocumentPartMetadata,
    Line,
    LineTranscription,
    Metadata,
)
from core.tests.factory import CoreFactoryTestCase
from escriptorium.test_settings import MEDIA_ROOT
from imports.export import ENABLED_EXPORTERS, EphremTEIExporter
from imports.tei import TEIExportError, validate
from reporting.models import TaskReport

NS = {"tei": "http://www.tei-c.org/ns/1.0"}
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


class EphremTEIExportTestCase(CoreFactoryTestCase):
    """TEI export of the pages Ready for TEI export, for the Ephrem Project website."""

    def setUp(self):
        super().setUp()
        self.owner = self.factory.make_user(first_name="Maria", last_name="Doolittle")
        self.editor = self.factory.make_user(username="editor1")
        self.doc = self.factory.make_document(owner=self.owner, name="Hymns manuscript")
        self.transcription = self.factory.make_transcription(document=self.doc)
        self.set_metadata(Work="Hymns on Faith", Shelfmark="Add. 14572",
                          Repository="British Library", Settlement="London",
                          Author="Ephrem the Syrian")
        body = BlockType.objects.create(name="Main text")
        margin = BlockType.objects.create(name="margin")
        self.parts = []
        for index, name in enumerate(["f. 23r", "f. 23v", "f. 24r"]):
            part = self.factory.make_part(document=self.doc, name=name)
            main = Block.objects.create(document_part=part, typology=body, box=[[0, 0], [9, 9]])
            note = Block.objects.create(document_part=part, typology=margin, box=[[0, 0], [9, 9]])
            for order, (block, content) in enumerate([
                (main, "ܫܠܡܐ ܥܠܝܟ %d" % index),
                (main, "second line & <more> %d" % index),
                (note, "margin note %d" % index),
                (None, "line outside regions %d" % index),
            ]):
                line = Line.objects.create(document_part=part, block=block, order=order,
                                           baseline=[[0, order], [9, order]])
                LineTranscription.objects.create(
                    transcription=self.transcription, line=line, content=content,
                    version_author=self.owner.username, version_source="eScriptorium")
            self.parts.append(part)
        # the first line of the first page was only transcribed by a model
        LineTranscription.objects.filter(line__document_part=self.parts[0], line__order=0).update(
            version_source="kraken:syriac_base")
        self.region_types = [body.pk, margin.pk, "Orphan"]
        self.report = TaskReport.objects.create(user=self.owner, label="export", document=self.doc,
                                                method="imports.tasks.document_export")

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def set_metadata(self, **fields):
        for name, value in fields.items():
            key, _ = Metadata.objects.get_or_create(name=name)
            DocumentMetadata.objects.update_or_create(document=self.doc, key=key,
                                                      defaults={"value": value})

    def ready(self, *parts, by=None):
        DocumentPart.set_editorial_status(
            DocumentPart.objects.filter(pk__in=[p.pk for p in parts]), "ready_for_tei",
            by or self.editor)

    def export(self, parts=None, include_images=False, region_types=None):
        exporter = EphremTEIExporter(
            [p.pk for p in (parts or self.parts)],
            list(region_types or self.region_types),
            include_images, False, self.owner, self.doc, self.report, self.transcription)
        exporter.render()
        return exporter

    def exported_tree(self, **kwargs):
        exporter = self.export(**kwargs)
        return exporter, etree.parse(exporter.filepath)

    def test_registered_as_an_export_format(self):
        self.assertIs(ENABLED_EXPORTERS["tei"]["class"], EphremTEIExporter)
        self.assertEqual(ENABLED_EXPORTERS["tei"]["label"], "TEI (Ephrem Project)")

    def test_ready_pages_are_exported_as_valid_tei(self):
        self.ready(*self.parts)
        exporter, tree = self.exported_tree()
        self.assertTrue(exporter.filepath.endswith(".xml"))
        self.assertEqual(validate(tree), [])
        root = tree.getroot()
        self.assertEqual(root.tag, "{http://www.tei-c.org/ns/1.0}TEI")

        # identification
        self.assertEqual(root.findtext(".//tei:titleStmt/tei:title[@level='a']", namespaces=NS),
                         "Hymns on Faith")
        self.assertEqual(root.findtext(".//tei:msIdentifier/tei:idno[@type='shelfmark']",
                                       namespaces=NS), "Add. 14572")
        self.assertEqual(root.findtext(".//tei:msIdentifier/tei:repository", namespaces=NS),
                         "British Library")
        self.assertEqual(root.findtext(".//tei:msIdentifier/tei:settlement", namespaces=NS), "London")
        idno = root.find(".//tei:publicationStmt/tei:idno", namespaces=NS)
        self.assertEqual(idno.get("type"), "URI")
        self.assertTrue(idno.text.endswith("/document/%d/images/" % self.doc.pk), idno.text)
        # language
        self.assertEqual(root.find(".//tei:language", namespaces=NS).get("ident"), "syr")
        self.assertEqual(root.find("tei:text", namespaces=NS).get(XML_LANG), "syr")

        # responsibility: people by full name when known, the model that transcribed
        resp = {r.findtext("tei:resp", namespaces=NS): [n.text for n in r.findall("tei:name", NS)]
                for r in root.findall(".//tei:respStmt", NS)}
        self.assertEqual(resp["Syriac text transcribed by"], ["Maria Doolittle"])
        self.assertEqual(resp["Initial automatic transcription by the kraken model"], ["syriac_base"])
        self.assertEqual(resp["Reviewed and approved for publication by"], ["editor1"])

        # review status of each page, pointing to who set it
        changes = root.findall(".//tei:revisionDesc/tei:change", NS)
        self.assertEqual([c.text for c in changes],
                         ["f. 23r: Ready for TEI export", "f. 23v: Ready for TEI export",
                          "f. 24r: Ready for TEI export"])
        self.assertEqual(changes[0].get("who"), "#user-editor1")
        self.assertEqual(changes[0].get("when"), timezone.now().date().isoformat())
        self.assertIn("user-editor1", [n.get(XML_ID) for n in root.iterfind(".//tei:name", NS)])

        # images, page breaks linking to them, regions and lines in reading order
        surfaces = root.findall(".//tei:facsimile/tei:surface", NS)
        self.assertEqual([s.find("tei:graphic", NS).get("url") for s in surfaces],
                         [p.filename for p in self.parts])
        body = root.find(".//tei:body", NS)
        [div] = body.findall("tei:div", NS)
        self.assertEqual((div.get("type"), div.get("n")), ("work", "Hymns on Faith"))
        page_breaks = div.findall("tei:pb", NS)
        self.assertEqual([pb.get("n") for pb in page_breaks], ["f. 23r", "f. 23v", "f. 24r"])
        self.assertEqual(page_breaks[0].get("facs"), "#" + surfaces[0].get(XML_ID))
        blocks = [(ab.get("type"), [(lb.get("n"), lb.tail) for lb in ab.findall("tei:lb", NS)])
                  for ab in div.findall("tei:ab", NS)[:3]]
        self.assertEqual(blocks, [
            ("Main-text", [("1", "ܫܠܡܐ ܥܠܝܟ 0"), ("2", "second line & <more> 0")]),
            ("margin", [("3", "margin note 0")]),
            ("no-region", [("4", "line outside regions 0")]),
        ])

    def test_only_ready_pages_are_exported(self):
        self.ready(self.parts[0], self.parts[2])
        exporter, tree = self.exported_tree()
        self.assertEqual([pb.get("n") for pb in tree.getroot().iterfind(".//tei:pb", NS)],
                         ["f. 23r", "f. 24r"])
        self.assertIn('Skipped f. 23v: its status is "Not started", not "Ready for TEI export".',
                      self.report.messages)

    def test_nothing_ready(self):
        with self.assertRaises(TEIExportError) as error:
            self.export()
        self.assertIn('None of the selected images is "Ready for TEI export"', str(error.exception))
        self.assertIn("The TEI export could not be made", error.exception.user_message)

    def test_missing_manuscript_and_work_are_explained(self):
        DocumentMetadata.objects.filter(document=self.doc).delete()
        self.ready(*self.parts)
        with self.assertRaises(TEIExportError) as error:
            self.export()
        messages = error.exception.messages
        self.assertEqual(len(messages), 2)
        self.assertIn('add a metadata field named "Shelfmark"', messages[0])
        self.assertIn('add a metadata field named "Work"', messages[1])
        self.assertIn("f. 23r, f. 23v, f. 24r", messages[1])
        self.assertIn("(1 more problems in the report)", error.exception.user_message)

    def test_metadata_names_are_matched_loosely(self):
        DocumentMetadata.objects.filter(document=self.doc).delete()
        self.set_metadata(**{"work title": "  Hymns on Paradise ", "SHELF MARK": "Vat. sir. 118"})
        self.ready(*self.parts)
        _, tree = self.exported_tree()
        root = tree.getroot()
        self.assertEqual(root.findtext(".//tei:title[@level='a']", namespaces=NS), "Hymns on Paradise")
        self.assertEqual(root.findtext(".//tei:idno[@type='shelfmark']", namespaces=NS), "Vat. sir. 118")

    def test_work_per_page_makes_divisions(self):
        key, _ = Metadata.objects.get_or_create(name="Work")
        DocumentPartMetadata.objects.create(part=self.parts[2], key=key, value="Hymns on Paradise")
        self.ready(*self.parts)
        _, tree = self.exported_tree()
        root = tree.getroot()
        divs = root.findall(".//tei:body/tei:div", NS)
        self.assertEqual([(d.get("n"), [pb.get("n") for pb in d.findall("tei:pb", NS)]) for d in divs],
                         [("Hymns on Faith", ["f. 23r", "f. 23v"]), ("Hymns on Paradise", ["f. 24r"])])
        self.assertEqual([t.text for t in root.findall(".//tei:msItem/tei:title", NS)],
                         ["Hymns on Faith", "Hymns on Paradise"])
        self.assertEqual(validate(tree), [])

    def test_identifier_and_language_from_metadata(self):
        self.set_metadata(Identifier="EP-0001", Language="syr-Syrj")
        self.ready(*self.parts)
        _, tree = self.exported_tree()
        idno = tree.getroot().find(".//tei:publicationStmt/tei:idno", NS)
        self.assertEqual((idno.text, idno.get("type")), ("EP-0001", "local"))
        self.assertEqual(tree.getroot().find("tei:text", NS).get(XML_LANG), "syr-Syrj")
        self.assertEqual(validate(tree), [])

    def test_invalid_language_is_explained(self):
        self.set_metadata(Language="Syriac (Estrangela)")
        self.ready(*self.parts)
        with self.assertRaises(TEIExportError) as error:
            self.export()
        self.assertIn('must be a language code such as "syr"', str(error.exception))

    def test_region_filter(self):
        self.ready(*self.parts)
        margin = BlockType.objects.get(name="margin")
        _, tree = self.exported_tree(region_types=[margin.pk])
        texts = [lb.tail for lb in tree.getroot().iterfind(".//tei:lb", NS)]
        self.assertEqual(texts, ["margin note 0", "margin note 1", "margin note 2"])

    def test_page_without_text_is_reported(self):
        LineTranscription.objects.filter(line__document_part=self.parts[1]).update(content="")
        self.ready(*self.parts)
        _, tree = self.exported_tree()
        self.assertIn('No transcription on f. 23v in the layer "%s".' % self.transcription.name,
                      self.report.messages)
        self.assertEqual(validate(tree), [])

    def test_with_images(self):
        self.ready(*self.parts)
        exporter = self.export(include_images=True)
        self.assertTrue(exporter.filepath.endswith(".zip"))
        with ZipFile(exporter.filepath) as zip_:
            names = zip_.namelist()
            xml_name = os.path.splitext(os.path.basename(exporter.filepath))[0] + ".xml"
            self.assertEqual(sorted(names), sorted([p.filename for p in self.parts] + [xml_name]))
            tree = etree.fromstring(zip_.read(xml_name)).getroottree()
        self.assertEqual(validate(tree), [])

    def test_filenames_are_valid_pointers(self):
        DocumentPart.objects.filter(pk=self.parts[0].pk).update(
            original_filename="BL Add 14572 f023r.tif")
        self.ready(*self.parts)
        _, tree = self.exported_tree()
        graphic = tree.getroot().find(".//tei:graphic", NS)
        self.assertEqual(graphic.get("url"), "BL%20Add%2014572%20f023r.tif")
        self.assertEqual(validate(tree), [])

    def test_schema_rejects_documents_missing_what_the_project_needs(self):
        self.ready(*self.parts)
        _, tree = self.exported_tree()
        idno = tree.getroot().find(".//tei:msIdentifier/tei:idno", NS)
        idno.getparent().remove(idno)
        self.assertTrue(validate(tree))

    @patch("imports.export.validate", return_value=["line 3: something is wrong"])
    def test_invalid_output_is_never_handed_out(self, _):
        self.ready(*self.parts)
        exporter = EphremTEIExporter([p.pk for p in self.parts], list(self.region_types), False,
                                     False, self.owner, self.doc, self.report, self.transcription)
        with self.assertRaises(TEIExportError) as error:
            exporter.render()
        self.assertIn("line 3: something is wrong", str(error.exception))
        self.assertFalse(os.path.exists(exporter.filepath))
