import os
import shutil
from urllib.parse import unquote
from zipfile import ZipFile

from lxml import etree

from core.models import (
    AnnotationComponent,
    AnnotationTaxonomy,
    Block,
    BlockType,
    CascadeUpdate,
    DocumentMetadata,
    DocumentPart,
    Line,
    LineTranscription,
    Metadata,
    TextAnnotation,
    TextAnnotationComponentValue,
)
from core.tests.factory import CoreFactoryTestCase
from escriptorium.test_settings import MEDIA_ROOT
from imports.ephrem_tei import EphremTEIError, tei_schema
from imports.export import ENABLED_EXPORTERS, EphremTEIExporter
from imports.tests.test_tei_profile import NS, profile_errors

MASK = [[10, 10], [90, 10], [90, 20], [10, 20]]


class EphremTEIExporterTestCase(CoreFactoryTestCase):
    """
    A right-to-left Syriac document of two pages, with every kind of region and annotation
    the profile (docs/tei/ephrem-tei-profile.md) maps to TEI.
    """

    def setUp(self):
        super().setUp()
        self.user = self.factory.make_user(username="jdoe", first_name="Jane", last_name="Doe")
        self.document = self.factory.make_document(owner=self.user, name="Example MS 1", read_direction="rtl")
        # every document gets a "manual" transcription layer
        self.transcription = self.document.transcriptions.get(name="manual")
        for key, value in (("repository", "Example Library"), ("shelfmark", "MS 1"), ("settlement", "Example City"),
                           ("work", "Hymns on Faith"), ("author", "Ephrem")):
            self.set_metadata(key, value)
        title, main, margin = (BlockType.objects.create(name=name) for name in ("Title", "Main", "Margin"))
        self.region_types = [title.pk, main.pk, margin.pk, "Orphan", "Undefined"]

        with CascadeUpdate.bypass():
            self.part1 = self.factory.make_part(document=self.document, name="23r", original_filename="MS1 f023r.png")
            self.part2 = self.factory.make_part(document=self.document, name="23v", original_filename="MS1 f023v.png",
                                                image_asset="segmentation/default2.png")
            # 23r: a heading, the main text, a margin note and a line outside any region
            self.head = self.line(self.part1, self.block(self.part1, title), "ܡܕܪܫܐ")
            self.main1 = self.block(self.part1, main)
            self.line1 = self.line(self.part1, self.main1, "ܗܝܡܢܘܬܐ ܕܐܠ")
            self.line2 = self.line(self.part1, self.main1, "ܗܐ ܘ")
            self.line3 = self.line(self.part1, self.main1, "x < y & z")
            self.note = self.line(self.part1, self.block(self.part1, margin), "ܥܘܢܝܬܐ")
            self.orphan = self.line(self.part1, None, "ܣܪ̈ܦܐ")
            # 23v: text, then a heading that starts a section, then text recognised by a model
            main2 = self.block(self.part2, main)
            self.line(self.part2, main2, "ܐ")
            self.line(self.part2, main2, "ܒ")
            self.line(self.part2, self.block(self.part2, title), "ܡܕܪܫܐ ܬܪܝܢܐ")
            self.gap_line = self.line(self.part2, self.block(self.part2, main), "ܓ ... ܕ", source="kraken:syr_test")

        self.unclear = self.annotate("unclear", self.line1, 8, self.line2, 2, reason="faded")
        self.annotate("add", self.line2, 3, self.line2, 4, place="above")
        self.annotate("gap", self.gap_line, 2, self.gap_line, 5)
        DocumentPart.set_editorial_status(DocumentPart.objects.filter(pk=self.part1.pk), "reviewed_1", self.user)

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def set_metadata(self, key, value):
        DocumentMetadata.objects.create(document=self.document, key=Metadata.objects.get_or_create(name=key)[0],
                                        value=value)

    def block(self, part, typology):
        return Block.objects.create(document_part=part, typology=typology, box=MASK)

    def line(self, part, block, text, source="eScriptorium"):
        line = Line.objects.create(document_part=part, block=block, mask=MASK, baseline=[[10, 15], [90, 15]])
        LineTranscription.objects.create(line=line, transcription=self.transcription, content=text,
                                         version_author="jdoe", version_source=source)
        return line

    def annotate(self, taxonomy_name, start_line, start_offset, end_line, end_offset, **components):
        taxonomy, _ = AnnotationTaxonomy.objects.get_or_create(
            document=self.document, name=taxonomy_name, marker_type=AnnotationTaxonomy.MARKER_TYPE_BG_COLOR)
        annotation = TextAnnotation.objects.create(
            taxonomy=taxonomy, part=start_line.document_part, transcription=self.transcription,
            start_line=start_line, start_offset=start_offset, end_line=end_line, end_offset=end_offset)
        for name, value in components.items():
            component, _ = AnnotationComponent.objects.get_or_create(document=self.document, name=name)
            taxonomy.components.add(component)
            TextAnnotationComponentValue.objects.create(component=component, annotation=annotation, value=value)
        return annotation

    def exporter(self, include_images=False):
        return EphremTEIExporter([self.part1.pk, self.part2.pk], list(self.region_types), include_images, False,
                                 self.user, self.document, None, self.transcription)

    def export(self, include_images=False):
        exporter = self.exporter(include_images)
        exporter.render()
        with ZipFile(exporter.filepath) as archive:
            return etree.ElementTree(etree.fromstring(archive.read(f"ephrem-doc-{self.document.pk}.xml"))), archive.namelist()

    def assertProblems(self, *problems):
        exporter = self.exporter()
        with self.assertRaises(EphremTEIError) as context:
            exporter.render()
        for problem in problems:
            self.assertIn(problem, context.exception.problems)
        self.assertEqual(len(context.exception.problems), len(problems), context.exception.problems)
        self.assertFalse(os.path.exists(exporter.filepath))

    @staticmethod
    def xpath(tree, path):
        return tree.xpath(path, namespaces=NS)

    def texts(self, tree, path):
        return [" ".join(el.itertext()) for el in self.xpath(tree, path)]

    def test_registered(self):
        self.assertEqual(ENABLED_EXPORTERS["ephremtei"], {"class": EphremTEIExporter, "label": "TEI (Ephrem)"})

    def test_valid_ephrem_tei(self):
        tree, names = self.export()
        self.assertEqual(names, [f"ephrem-doc-{self.document.pk}.xml"])
        self.assertTrue(tei_schema().validate(tree), str(tei_schema().error_log))
        self.assertEqual(profile_errors(tree), [])

    def test_header(self):
        tree, _ = self.export()

        def text(path):
            return self.texts(tree, path)

        self.assertEqual(tree.getroot().get("{http://www.w3.org/XML/1998/namespace}id"), f"ephrem-doc-{self.document.pk}")
        self.assertEqual(text("//tei:titleStmt/tei:title"), ["Example MS 1"])
        self.assertEqual(text("//tei:respStmt/tei:resp"),
                         ["Syriac text transcribed by", "Reviewed by", "Automatic text recognition by"])
        self.assertEqual(text("//tei:respStmt/tei:persName"), ["Jane Doe"])
        self.assertEqual(text("//tei:respStmt/tei:name[@type='software']"), ["kraken model syr_test"])
        self.assertEqual(text("//tei:msIdentifier/*"), ["Example City", "Example Library", "MS 1"])
        self.assertEqual(text("//tei:msItem/tei:author | //tei:msItem/tei:title"), ["Ephrem", "Hymns on Faith"])
        self.assertEqual([(el.get("from"), el.get("to")) for el in self.xpath(tree, "//tei:locus")], [("23r", "23v")])
        # the current stage is the least advanced page; 23v has no recorded change, so it has no date
        self.assertEqual(self.xpath(tree, "string(//tei:revisionDesc/@status)"), "not_started")
        changes = self.xpath(tree, "//tei:change")
        self.assertEqual([(c.get("status"), c.get("who"), c.get("target"), c.text) for c in changes], [
            ("reviewed_1", "#pers-jdoe", f"#surface-{self.part1.pk}", "23r: Reviewed by Editor 1"),
            ("not_started", None, f"#surface-{self.part2.pk}", "23v: Not started"),
        ])
        self.assertIsNotNone(changes[0].get("when"))
        self.assertIsNone(changes[1].get("when"))

    def test_text(self):
        tree, _ = self.export()
        self.assertEqual(len(self.xpath(tree, "//tei:div[@type='work']")), 1)
        self.assertEqual([pb.get("n") for pb in self.xpath(tree, "//tei:pb")], ["23r", "23v"])
        # 23r: the heading opens the work, the margin note and the orphan line follow the main text
        work = self.xpath(tree, "//tei:div[@type='work']")[0]
        self.assertEqual([etree.QName(el).localname for el in work.iterchildren()],
                         ["pb", "head", "ab", "note", "ab", "pb", "ab", "div"])
        self.assertEqual(self.xpath(tree, "//tei:note")[0].get("place"), "margin")
        self.assertEqual(self.xpath(tree, "//tei:note")[0].get("facs"), f"#zone-r{self.note.block_id}")
        # 23v: the heading after the text starts a section
        section = self.xpath(tree, "//tei:div[@type='section']")[0]
        self.assertEqual(section.get("n"), "1")
        self.assertEqual("".join(section.find("tei:head", NS).itertext()).strip(), "ܡܕܪܫܐ ܬܪܝܢܐ")
        # lines are numbered on each page, and their text is escaped
        self.assertEqual([lb.get("n") for lb in self.xpath(tree, "//tei:lb")], ["1", "2", "3", "4", "5", "6", "1", "2", "3", "4"])
        self.assertEqual(self.xpath(tree, "//tei:lb[@n='4']")[0].tail.strip(), "x < y & z")
        self.assertEqual(self.xpath(tree, "//tei:lb[@n='2']")[0].get("facs"), f"#zone-l{self.line1.pk}")

    def test_annotations(self):
        tree, _ = self.export()
        unclear = self.xpath(tree, "//tei:unclear")[0]
        self.assertEqual(unclear.get("reason"), "faded")
        self.assertEqual("".join(unclear.itertext()).split(), ["ܕܐܠ", "ܗܐ"])
        self.assertEqual(len(unclear.findall("tei:lb", NS)), 1)
        add = self.xpath(tree, "//tei:add")[0]
        self.assertEqual((add.get("place"), add.text), ("above", "ܘ"))
        gap = self.xpath(tree, "//tei:gap")[0]
        self.assertEqual(gap.get("reason"), "illegible")
        self.assertEqual(gap.getparent().xpath("string()").split(), ["ܓ", "ܕ"])

    def test_image_links(self):
        tree, names = self.export(include_images=True)
        urls = [graphic.get("url") for graphic in self.xpath(tree, "//tei:graphic")]
        self.assertEqual(urls, ["MS1%20f023r.png", "MS1%20f023v.png"])
        self.assertEqual(sorted(names), sorted(["MS1 f023r.png", "MS1 f023v.png", f"ephrem-doc-{self.document.pk}.xml"]))
        self.assertEqual([unquote(url) for url in urls], ["MS1 f023r.png", "MS1 f023v.png"])

    def test_source_link(self):
        DocumentPart.objects.filter(pk=self.part1.pk).update(source="https://iiif.example.org/a/full/full/0/default.jpg")
        DocumentPart.objects.filter(pk=self.part2.pk).update(source="pdf//scan.pdf")
        tree, _ = self.export()
        self.assertEqual([graphic.get("url") for graphic in self.xpath(tree, "//tei:graphic[@type='source']")],
                         ["https://iiif.example.org/a/full/full/0/default.jpg"])

    def test_missing_data(self):
        DocumentMetadata.objects.filter(document=self.document, key__name__in=["repository", "shelfmark"]).delete()
        DocumentPart.objects.filter(pk=self.part1.pk).update(name="")
        DocumentPart.objects.filter(pk=self.part2.pk).update(name="f. 23v")
        self.assertProblems(
            'Document: metadata "repository" is missing',
            'Document: metadata "shelfmark" is missing',
            "Page 1 (MS1 f023r.png): no name; set the page Name to the folio, e.g. 23r",
            'Page 2 (MS1 f023v.png): name "f. 23v" contains a space; use the folio alone, e.g. 23r',
        )

    def test_missing_work(self):
        DocumentMetadata.objects.filter(document=self.document, key__name="work").delete()
        self.assertProblems(
            'Page 1 (MS1 f023r.png): no work; set page metadata "work" or document metadata "work"',
            'Page 2 (MS1 f023v.png): no work; set page metadata "work" or document metadata "work"',
        )

    def test_conflicting_values(self):
        self.set_metadata("shelfmark", "MS 2")
        DocumentPart.objects.filter(pk=self.part2.pk).update(name="23r", original_filename="MS1 f023r.png")
        self.assertProblems(
            'Document: metadata "shelfmark" has 2 different values',
            'Pages 1, 2: all are named "23r"',
            'Pages 1, 2: all use the image file name "MS1 f023r.png"',
        )

    def test_annotation_into_another_region(self):
        self.annotate("unclear", self.line3, 0, self.note, 2)
        self.assertProblems('Page 1 (MS1 f023r.png), line 4: the "unclear" annotation runs into another region')

    def test_overlapping_annotations(self):
        self.annotate("add", self.line2, 0, self.line3, 1)
        self.assertProblems('Page 1 (MS1 f023r.png), line 3: the "add" and "unclear" annotations overlap')

    def test_no_pages(self):
        exporter = EphremTEIExporter([], list(self.region_types), False, False,
                                     self.user, self.document, None, self.transcription)
        with self.assertRaises(EphremTEIError) as context:
            exporter.render()
        self.assertEqual(context.exception.problems, ["Document: there are no pages to export"])

    def test_forbidden_character(self):
        LineTranscription.objects.filter(line=self.line3).update(content="x\x07")
        self.assertProblems("Page 1 (MS1 f023r.png), line 4: character U+0007 is not allowed in XML")
