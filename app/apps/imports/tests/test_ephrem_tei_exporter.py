"""
The "TEI (Ephrem)" export (docs/tei/ephrem-tei-profile.md) of a right-to-left Syriac manuscript
that uses every region type, line type and annotation the profile maps.
"""
import os
import shutil
from urllib.parse import unquote
from zipfile import ZipFile

from django.test import override_settings
from lxml import etree

from core.models import (
    AnnotationComponent,
    AnnotationTaxonomy,
    Block,
    BlockType,
    CascadeUpdate,
    DocumentMetadata,
    DocumentPart,
    DocumentPartMetadata,
    Line,
    LineTranscription,
    LineType,
    Metadata,
    Script,
    TextAnnotation,
    TextAnnotationComponentValue,
)
from core.tests.factory import CoreFactoryTestCase
from escriptorium.test_settings import MEDIA_ROOT
from imports.export import ENABLED_EXPORTERS, EphremTEIExporter
from imports.tei import EphremTEIError, check_document, file_errors
from imports.tei.validation import NS, link_errors, requirement_errors, schema_errors

XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
URI_BASE = "https://ephrem.example.org/records/"


def box(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


class EphremTEITestCase(CoreFactoryTestCase):
    """Helpers to build documents and export them."""

    def setUp(self):
        super().setUp()
        self.user = self.factory.make_user(username="jdoe", first_name="Jane", last_name="Doe")
        self.document = self.factory.make_document(owner=self.user, name="Example MS 1", read_direction="rtl")
        # every document gets a "manual" transcription layer
        self.transcription = self.document.transcriptions.get(name="manual")
        self.block_types, self.line_types = {}, {}

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def set_metadata(self, key, value, part=None):
        key = Metadata.objects.get_or_create(name=key)[0]
        if part is None:
            DocumentMetadata.objects.create(document=self.document, key=key, value=value)
        else:
            DocumentPartMetadata.objects.create(part=part, key=key, value=value)

    def required_metadata(self):
        for key, value in (("record_id", "example-ms-1"), ("repository", "Example Library"), ("shelfmark", "MS 1"),
                           ("work", "Hymns on Faith")):
            self.set_metadata(key, value)

    def part(self, name, **kwargs):
        with CascadeUpdate.bypass():
            return self.factory.make_part(document=self.document, name=name, original_filename=f"MS1 f{name}.png",
                                          **kwargs)

    def region(self, part, type_name, coordinates):
        if type_name not in self.block_types:
            self.block_types[type_name] = BlockType.objects.get_or_create(name=type_name)[0]
        return Block.objects.create(document_part=part, typology=self.block_types[type_name], box=box(*coordinates))

    def line(self, part, region, text, coordinates, type_name=None, source="eScriptorium", author="jdoe"):
        if type_name and type_name not in self.line_types:
            self.line_types[type_name] = LineType.objects.get_or_create(name=type_name)[0]
        x0, y0, x1, y1 = coordinates
        line = Line.objects.create(document_part=part, block=region, mask=box(*coordinates),
                                   baseline=[[x0, y1], [x1, y1]], typology=self.line_types.get(type_name))
        LineTranscription.objects.create(line=line, transcription=self.transcription, content=text,
                                         version_author=author, version_source=source)
        return line

    def annotate(self, name, start_line, start_offset, end_line, end_offset, **components):
        taxonomy, _ = AnnotationTaxonomy.objects.get_or_create(
            document=self.document, name=name, marker_type=AnnotationTaxonomy.MARKER_TYPE_BG_COLOR)
        annotation = TextAnnotation.objects.create(
            taxonomy=taxonomy, part=start_line.document_part, transcription=self.transcription,
            start_line=start_line, start_offset=start_offset, end_line=end_line, end_offset=end_offset)
        for component_name, value in components.items():
            component, _ = AnnotationComponent.objects.get_or_create(document=self.document, name=component_name)
            taxonomy.components.add(component)
            TextAnnotationComponentValue.objects.create(component=component, annotation=annotation, value=value)
        return annotation

    def region_types(self):
        return [block_type.pk for block_type in self.block_types.values()] + ["Orphan", "Undefined"]

    def parts(self):
        return list(DocumentPart.objects.filter(document=self.document).order_by("order"))

    def exporter(self, include_images=False):
        return EphremTEIExporter([part.pk for part in self.parts()], self.region_types(), include_images, False,
                                 self.user, self.document, None, self.transcription)

    def export(self, include_images=False):
        """The exported TEI file, parsed, and the names of the files written."""
        exporter = self.exporter(include_images)
        exporter.render()
        if include_images:
            self.assertTrue(exporter.filepath.endswith(".zip"))
            with ZipFile(exporter.filepath) as archive:
                names = archive.namelist()
                content = archive.read([name for name in names if name.endswith(".xml")][0])
        else:
            self.assertTrue(exporter.filepath.endswith(".xml"))
            names = [os.path.basename(exporter.filepath)]
            with open(exporter.filepath, "rb") as fh:
                content = fh.read()
        self.assertEqual(file_errors(content), [])
        return etree.ElementTree(etree.fromstring(content)), names

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
        return [" ".join("".join(el.itertext()).split()) for el in self.xpath(tree, path)]

    @staticmethod
    def names(elements):
        return [etree.QName(element).localname for element in elements]

    def around(self, element):
        """The @facs of the text's line breaks just before and just after element."""
        before = self.xpath(element, "preceding::tei:lb[@n][1]")
        after = self.xpath(element, "following::tei:lb[@n][1]")
        return (before[0].get("facs") if before else None, after[0].get("facs") if after else None)


class EphremTEIExporterTestCase(EphremTEITestCase):
    """
    Four pages, three work divisions:
    - 23r: two columns (right-to-left: the right column is a), a running title and a page number at the top,
      a heading, a paragraph, an interlinear addition, a margin note, an illustration with a caption,
      a quire signature at the bottom.
    - 23v: one column; text recognised by a model with a gap; a commentary note; a drop capital and a
      footnotes region, whose types are not in the profile; a line outside any region; a signature line.
    - 24r: another work, without a work URI.
    - 25r: the first work again, without text.
    """

    def setUp(self):
        super().setUp()
        self.required_metadata()
        self.set_metadata("settlement", "Example City")
        self.set_metadata("author", "Ephrem")
        self.set_metadata("work_uri", "http://syriaca.org/work/1505")
        self.set_metadata("reviewed_by", "Sebastian Brock; JDOE")
        self.editor = self.factory.make_user(username="editor", first_name="Ed", last_name="Itor")

        p1, p2, p3, p4 = (self.part(name) for name in ("23r", "23v", "24r", "25r"))
        self.p1, self.p2, self.p3, self.p4 = p1, p2, p3, p4
        with CascadeUpdate.bypass():
            title = self.region(p1, "RunningTitleZone", (300, 0, 700, 20))
            number = self.region(p1, "NumberingZone", (950, 0, 990, 20))
            right = self.region(p1, "MainZone:right", (500, 40, 900, 160))
            left = self.region(p1, "MainZone:left", (100, 40, 450, 160))
            margin = self.region(p1, "MarginTextZone", (950, 100, 990, 120))
            picture = self.region(p1, "Illustration", (100, 170, 450, 200))
            quire = self.region(p1, "QuireMarksZone", (450, 290, 550, 300))
            # in reading order
            self.running_title = self.line(p1, title, "ܡܕܪܫܐ ܕܗܝܡܢܘܬܐ", (300, 2, 700, 18))
            self.page_number = self.line(p1, number, "ܟܓ", (950, 2, 990, 18))
            self.heading = self.line(p1, right, "ܡܕܪܫܐ", (500, 40, 900, 60), "HeadingLine")
            self.line1 = self.line(p1, right, "ܗܝܡܢܘܬܐ ܕܐܠ", (500, 70, 900, 90), "ParagraphStart")
            self.interlinear = self.line(p1, right, "ܘ", (600, 92, 700, 98), "InterlinearLine")
            self.line2 = self.line(p1, right, "ܗܐ ܘܗ", (500, 100, 900, 120))
            self.line3 = self.line(p1, right, "x < y & z", (500, 130, 900, 150))
            self.left1 = self.line(p1, left, "ܐ", (100, 40, 450, 60))
            self.left2 = self.line(p1, left, "ܒ", (100, 70, 450, 90))
            self.note = self.line(p1, margin, "ܥܘܢܝܬܐ", (950, 100, 990, 120))
            self.caption = self.line(p1, picture, "ܨܘܪܬܐ", (100, 170, 450, 200))
            self.signature = self.line(p1, quire, "ܒ", (450, 290, 550, 300))

            main = self.region(p2, "MainZone", (100, 40, 900, 160))
            footnotes = self.region(p2, "Footnotes", (100, 250, 900, 280))
            commentary = self.region(p2, "Commentary", (950, 40, 990, 60))
            self.gap_line = self.line(p2, main, "ܓ ... ܕ", (100, 40, 900, 60), source="kraken:syr_test")
            self.drop_capital = self.line(p2, main, "ܐ", (100, 70, 900, 90), "DropCapitalLine")
            self.after_drop = self.line(p2, main, "ܕ", (100, 100, 900, 120))
            self.signature_line = self.line(p2, main, "ܓ", (500, 150, 600, 160), "Signature")
            self.orphan = self.line(p2, None, "ܣܪ̈ܦܐ", (100, 130, 900, 150))
            self.footnote = self.line(p2, footnotes, "1. ܗ", (100, 250, 900, 280))
            self.commentary = self.line(p2, commentary, "ܦܘܫܩܐ", (950, 40, 990, 60))

            self.other_work_line = self.line(p3, self.region(p3, "MainZone", (100, 40, 900, 160)), "ܗ",
                                             (100, 40, 900, 60))
        self.set_metadata("work", "Hymns on Paradise", part=p3)

        self.unclear = self.annotate("unclear", self.line1, 8, self.line2, 2, reason="faded")
        self.annotate("add", self.line2, 3, self.line2, 4, place="above")
        self.annotate("gap", self.gap_line, 2, self.gap_line, 5, extent="3", unit="chars")
        DocumentPart.set_editorial_status(DocumentPart.objects.filter(pk=p1.pk), "reviewed_1", self.user)
        DocumentPart.set_editorial_status(DocumentPart.objects.filter(pk=p3.pk), "final", self.editor)

    def test_registered(self):
        self.assertEqual(ENABLED_EXPORTERS["ephremtei"], {"class": EphremTEIExporter, "label": "TEI (Ephrem)"})

    def test_valid(self):
        tree, names = self.export()
        self.assertEqual(schema_errors(tree), [])
        self.assertEqual(link_errors(tree), [])
        self.assertEqual(requirement_errors(tree), [])

    # 1. stable record identifier

    @override_settings(EPHREM_TEI_URI_BASE=URI_BASE)
    def test_record_id(self):
        tree, names = self.export()
        self.assertEqual(tree.getroot().get(XML_ID), "example-ms-1")
        self.assertEqual(self.texts(tree, "//tei:publicationStmt/tei:idno[@type='ephrem']"), ["example-ms-1"])
        self.assertEqual(self.texts(tree, "//tei:publicationStmt/tei:idno[@type='URI']"), [URI_BASE + "example-ms-1"])

    def test_record_uri_needs_the_setting(self):
        tree, _ = self.export()
        self.assertEqual(self.xpath(tree, "//tei:idno[@type='URI']"), [])

    def test_record_id_problems(self):
        DocumentMetadata.objects.filter(document=self.document, key__name="record_id").delete()
        self.assertProblems('Document: metadata "record_id" is missing')
        for value, problem in (
                ("12-ms", 'may only contain letters, digits, ".", "_" and "-", and must start with a letter or "_"'),
                ("MS 1", 'may only contain letters, digits'),
                ("surface-1", "starts like the ids the export gives to pages, zones, works, people and statuses")):
            DocumentMetadata.objects.filter(document=self.document, key__name="record_id").delete()
            self.set_metadata("record_id", value)
            with self.assertRaises(EphremTEIError) as context:
                self.exporter().render()
            self.assertIn(problem, context.exception.problems[0])

    def test_record_id_is_unique(self):
        other = self.factory.make_document(owner=self.user)
        DocumentMetadata.objects.create(document=other, key=Metadata.objects.get_or_create(name="Record ID")[0],
                                        value="EXAMPLE-MS-1")
        self.assertProblems('Document: record_id "example-ms-1" is already used by another document')

    # 2. manuscript identification

    def test_manuscript(self):
        tree, _ = self.export()
        self.assertEqual(self.texts(tree, "//tei:msIdentifier/*"), ["Example City", "Example Library", "MS 1"])
        self.assertEqual([el.get("type") for el in self.xpath(tree, "//tei:msIdentifier/tei:idno")], ["shelfmark"])

    def test_metadata_keys_in_any_case_and_aliases(self):
        # as a IIIF manifest gives them; an editor's "shelfmark" would win over "Call number"
        DocumentMetadata.objects.filter(document=self.document, key__name__in=[
            "repository", "shelfmark", "settlement"]).delete()
        self.set_metadata("Holding Institution", "Example Library")
        self.set_metadata("Call number", "Add. 14571")
        self.set_metadata("Location", "London")
        tree, _ = self.export()
        self.assertEqual(self.texts(tree, "//tei:msIdentifier/*"), ["London", "Example Library", "Add. 14571"])
        self.set_metadata("SHELFMARK", "MS 1")
        tree, _ = self.export()
        self.assertEqual(self.texts(tree, "//tei:msIdentifier/tei:idno"), ["MS 1"])

    def test_missing_manuscript_metadata(self):
        DocumentMetadata.objects.filter(document=self.document, key__name__in=["repository", "shelfmark"]).delete()
        self.set_metadata("Shelfmark", "MS 1")
        self.set_metadata("shelfmark", "MS 2")
        self.assertProblems('Document: metadata "repository" is missing',
                            'Document: metadata "shelfmark" has 2 different values')

    # 3. works and their relationship to the manuscript

    def test_works(self):
        tree, _ = self.export()
        items = self.xpath(tree, "//tei:msItem")
        self.assertEqual([(item.get(XML_ID), item.get("n")) for item in items], [("work-1", "1"), ("work-2", "2")])
        self.assertEqual([[(locus.get("from"), locus.get("to")) for locus in self.xpath(item, "tei:locus")]
                          for item in items], [[("23r", "23v"), ("25r", "25r")], [("24r", "24r")]])
        self.assertEqual(self.texts(tree, "//tei:msItem[1]/tei:author | //tei:msItem[1]/tei:title"),
                         ["Ephrem", "Hymns on Faith"])
        self.assertEqual(self.xpath(tree, "//tei:msItem[1]/tei:title")[0].get("ref"), "http://syriaca.org/work/1505")
        self.assertIsNone(self.xpath(tree, "//tei:msItem[2]/tei:title")[0].get("ref"))
        self.assertEqual([div.get("corresp") for div in self.xpath(tree, "//tei:body/tei:div")],
                         ["#work-1", "#work-2", "#work-1"])

    def test_work_problems(self):
        DocumentMetadata.objects.filter(document=self.document, key__name="work").delete()
        self.set_metadata("work_uri", "syriaca.org/work/1", part=self.p3)
        self.set_metadata("author", "Narsai", part=self.p3)
        self.set_metadata("work_uri", "http://syriaca.org/work/2", part=self.p3)
        self.set_metadata("work", "Hymns on Paradise", part=self.p4)
        self.assertProblems(
            'Page 1 (MS1 f23r.png): no work; set page metadata "work" or document metadata "work"',
            'Page 2 (MS1 f23v.png): no work; set page metadata "work" or document metadata "work"',
            'Page 3 (MS1 f24r.png): metadata "work_uri" has 2 different values',
            'Page 3 (MS1 f24r.png): work_uri "syriaca.org/work/1" is not a web address (http:// or https://, '
            'without spaces)',
            'Work "Hymns on Paradise": pages give different authors, or only some give one',
            'Work "Hymns on Paradise": pages give different work URIs, or only some give one',
        )

    def test_work_without_uri_is_a_warning(self):
        report = check_document(self.document, [p.pk for p in self.parts()], self.transcription, self.region_types())
        self.assertTrue(report["ready"], report["errors"])
        self.assertIn('Work "Hymns on Paradise": no work_uri; set it to the work\'s Syriaca.org URI',
                      [warning["message"] for warning in report["warnings"]])

    # 4. language

    def test_language(self):
        # the main script is not used: Syriaca.org keeps script subtags for an editorial decision
        self.document.main_script = Script.objects.create(name="Syriac (Western variant)", iso_code="Syrj",
                                                          text_direction="horizontal-rl")
        self.document.save()
        tree, _ = self.export()
        self.assertEqual(self.xpath(tree, "string(//tei:text/@xml:lang)"), "syr")
        self.assertEqual([(el.get("ident"), el.text) for el in self.xpath(tree, "//tei:language")],
                         [("en", "English"), ("syr", "Syriac")])

    def test_language_override(self):
        for value, tag in (("syr-Syre", "syr-Syre"), ("SYR-SYRN", "syr-Syrn"), ("syr-x-syrm", "syr-x-syrm")):
            DocumentMetadata.objects.filter(document=self.document, key__name="tei_language").delete()
            self.set_metadata("tei_language", value)
            tree, _ = self.export()
            self.assertEqual(self.xpath(tree, "string(//tei:text/@xml:lang)"), tag)
            self.assertEqual(self.xpath(tree, "//tei:language")[1].get("ident"), tag)

    def test_unapproved_language(self):
        self.set_metadata("tei_language", "syc")
        self.assertProblems('Document: tei_language "syc" is not one of the approved tags: '
                            'syr, syr-Syre, syr-Syrj, syr-Syrn, syr-x-syrm')

    # 5. responsibility

    def test_credits(self):
        tree, _ = self.export()
        people = [(el.get(XML_ID), el.text, self.texts(el.getparent(), "tei:resp"))
                  for el in self.xpath(tree, "//tei:respStmt/tei:persName")]
        self.assertEqual(people, [
            (f"pers-{self.editor.pk}", "Ed Itor", ["Edited by"]),
            (f"pers-{self.user.pk}", "Jane Doe", ["Syriac text transcribed by", "Reviewed by"]),
            ("pers-x-sebastian-brock", "Sebastian Brock", ["Reviewed by"]),
        ])
        self.assertEqual(self.texts(tree, "//tei:respStmt/tei:name[@type='software']"), ["kraken model syr_test"])

    # 6. review status

    def test_status(self):
        tree, _ = self.export()
        self.assertEqual(self.xpath(tree, "string(//tei:revisionDesc/@status)"), "not_started")
        changes = [(c.get(XML_ID), c.get("status"), c.get("who"), c.get("target"), c.text)
                   for c in self.xpath(tree, "//tei:change")]
        self.assertEqual(changes, [
            (f"status-{self.p3.pk}", "final", f"#pers-{self.editor.pk}", f"#surface-{self.p3.pk}", "24r: Final edited copy"),
            (f"status-{self.p1.pk}", "reviewed_1", f"#pers-{self.user.pk}", f"#surface-{self.p1.pk}",
             "23r: Reviewed by Editor 1"),
            (f"status-{self.p2.pk}", "not_started", None, f"#surface-{self.p2.pk}", "23v: Not started"),
            (f"status-{self.p4.pk}", "not_started", None, f"#surface-{self.p4.pk}", "25r: Not started"),
        ])
        self.assertTrue(self.xpath(tree, "//tei:change[1]")[0].get("when").startswith("20"))
        self.assertEqual([s.get("change") for s in self.xpath(tree, "//tei:surface")],
                         [f"#status-{part.pk}" for part in (self.p1, self.p2, self.p3, self.p4)])

    # 7, 12, 13. works, sections, headings, paragraphs

    def test_structure(self):
        tree, _ = self.export()
        work = self.xpath(tree, "//tei:body/tei:div")[0]
        self.assertEqual(self.names(work), ["div"])
        section = work[0]
        self.assertEqual((section.get("type"), section.get("n")), ("section", "1"))
        # the page's milestones and running material come before the heading, which starts the section
        self.assertEqual(self.names(section), ["pb", "fw", "fw", "cb", "head", "p", "ab", "ab", "ab"])
        self.assertEqual(self.texts(section, "tei:head"), ["ܡܕܪܫܐ"])
        # the paragraph runs on to the next page; the unknown types are blocks of their own
        paragraph = section.find("tei:p", NS)
        self.assertEqual([pb.get("n") for pb in paragraph.findall("tei:pb", NS)], ["23v"])
        self.assertEqual([ab.get("type") for ab in section.findall("tei:ab", NS)],
                         ["dropcapitalline", None, "footnotes"])

    def test_paragraphs_only_where_marked(self):
        Line.objects.filter(pk=self.line1.pk).update(typology=None)
        tree, _ = self.export()
        section = self.xpath(tree, "//tei:div[@type='section']")[0]
        self.assertEqual(self.names(section)[4:6], ["head", "ab"])
        self.assertEqual(self.xpath(tree, "//tei:body//tei:p"), [])

    def test_consecutive_headings_are_one_head(self):
        Line.objects.filter(pk=self.line1.pk).update(typology=self.line_types["HeadingLine"])
        self.unclear.delete()
        tree, _ = self.export()
        self.assertEqual(len(self.xpath(tree, "//tei:div[@type='section']")), 1)
        head = self.xpath(tree, "//tei:head")[0]
        self.assertEqual([lb.get("n") for lb in head.findall(".//tei:lb", NS)], ["1", "2"])

    def test_heading_after_text_starts_a_new_section(self):
        Line.objects.filter(pk=self.after_drop.pk).update(typology=self.line_types["HeadingLine"])
        tree, _ = self.export()
        sections = self.xpath(tree, "//tei:div[@type='work'][1]/tei:div[@type='section']")
        self.assertEqual([section.get("n") for section in sections], ["1", "2"])
        self.assertEqual(self.names(sections[1])[0], "head")

    # 8, 9, 14. pages, columns, line numbers

    def test_pages(self):
        tree, _ = self.export()
        pbs = self.xpath(tree, "//tei:pb")
        self.assertEqual([(pb.get("n"), pb.get("facs")) for pb in pbs],
                         [(name, f"#surface-{part.pk}") for name, part in (
                             ("23r", self.p1), ("23v", self.p2), ("24r", self.p3), ("25r", self.p4))])

    def test_columns(self):
        tree, _ = self.export()
        body = self.xpath(tree, "//tei:body")[0]
        milestones = [(etree.QName(el).localname, el.get("n"), el.get("facs"))
                      for el in body.iter("{*}pb", "{*}cb", "{*}lb") if el.get("n")]
        self.assertEqual(milestones, [
            ("pb", "23r", f"#surface-{self.p1.pk}"),
            # right-to-left: the right column is a
            ("cb", "a", None),
            ("lb", "1", f"#zone-l{self.heading.pk}"),
            ("lb", "2", f"#zone-l{self.line1.pk}"),
            ("lb", "3", f"#zone-l{self.line2.pk}"),
            ("lb", "4", f"#zone-l{self.line3.pk}"),
            ("cb", "b", None),
            ("lb", "1", f"#zone-l{self.left1.pk}"),
            ("lb", "2", f"#zone-l{self.left2.pk}"),
            # one column: no cb, the lines of the page counted from 1
            ("pb", "23v", f"#surface-{self.p2.pk}"),
            ("lb", "1", f"#zone-l{self.gap_line.pk}"),
            ("lb", "2", f"#zone-l{self.drop_capital.pk}"),
            ("lb", "3", f"#zone-l{self.after_drop.pk}"),
            ("lb", "4", f"#zone-l{self.orphan.pk}"),
            ("lb", "5", f"#zone-l{self.footnote.pk}"),
            ("pb", "24r", f"#surface-{self.p3.pk}"),
            ("lb", "1", f"#zone-l{self.other_work_line.pk}"),
            ("pb", "25r", f"#surface-{self.p4.pk}"),
        ])

    def test_columns_left_to_right(self):
        self.document.read_direction = "ltr"
        self.document.save()
        tree, _ = self.export()
        first_lines = [self.xpath(cb, "following::tei:lb[1]")[0].get("facs") for cb in self.xpath(tree, "//tei:cb")]
        # the left column is a
        self.assertEqual([cb.get("n") for cb in self.xpath(tree, "//tei:cb")], ["b", "a"])
        self.assertEqual(first_lines, [f"#zone-l{self.heading.pk}", f"#zone-l{self.left1.pk}"])

    # 15, 16. margin notes, interlinear additions, page furniture, non-text regions

    def test_margin_note_after_the_nearest_line(self):
        tree, _ = self.export()
        note = self.xpath(tree, "//tei:note[@place='margin']")[0]
        self.assertEqual(note.get("facs"), f"#zone-r{self.note.block_id}")
        self.assertEqual(self.texts(tree, "//tei:note[@place='margin']"), ["ܥܘܢܝܬܐ"])
        # the note sits level with line 3: after its text, before line 4
        self.assertEqual(self.around(note), (f"#zone-l{self.line2.pk}", f"#zone-l{self.line3.pk}"))
        # its own lines are not counted with the text's
        self.assertIsNone(note.find("tei:lb", NS).get("n"))
        commentary = self.xpath(tree, "//tei:note[@type='commentary']")[0]
        self.assertEqual(self.around(commentary)[0], f"#zone-l{self.gap_line.pk}")

    def test_interlinear_addition_after_the_line_under_it(self):
        tree, _ = self.export()
        add = self.xpath(tree, "//tei:add[@facs='#zone-l%s']" % self.interlinear.pk)[0]
        self.assertEqual((add.get("place"), add.text), ("above", "ܘ"))
        # after the text of line 3, which it is written above
        self.assertEqual(self.around(add), (f"#zone-l{self.line2.pk}", f"#zone-l{self.line3.pk}"))

    def test_page_furniture(self):
        tree, _ = self.export()
        self.assertEqual([(fw.get("type"), " ".join("".join(fw.itertext()).split()))
                          for fw in self.xpath(tree, "//tei:fw")],
                         [("header", "ܡܕܪܫܐ ܕܗܝܡܢܘܬܐ"), ("pageNum", "ܟܓ"), ("sig", "ܒ"), ("sig", "ܓ")])
        # the quire signature is at the foot of the page: after the last line of the right column
        signature = self.xpath(tree, "//tei:fw[@type='sig']")[0]
        self.assertEqual(self.around(signature)[0], f"#zone-l{self.line3.pk}")
        # a single line typed as a signature points to its line zone
        self.assertEqual(self.xpath(tree, "//tei:fw[@type='sig']")[1].get("facs"), f"#zone-l{self.signature_line.pk}")

    def test_non_text_regions(self):
        tree, _ = self.export()
        self.assertTrue(self.xpath(tree, "//tei:zone[@xml:id='zone-r%s'][@type='illustration']" % self.caption.block_id))
        self.assertNotIn("ܨܘܪܬܐ", "".join(self.xpath(tree, "//tei:body")[0].itertext()))

    # 17. types the profile doesn't know

    def test_unknown_types(self):
        tree, _ = self.export()
        self.assertEqual(self.texts(tree, "//tei:ab[@type='dropcapitalline']"), ["ܐ"])
        self.assertEqual(self.texts(tree, "//tei:ab[@type='footnotes']"), ["1. ܗ"])
        report = check_document(self.document, [p.pk for p in self.parts()], self.transcription, self.region_types())
        warnings = [warning["message"] for warning in report["warnings"] if warning["category"] == "types"]
        self.assertEqual(warnings, [
            'Line type "DropCapitalLine" is not in the Ephrem profile: its text is exported as '
            '<ab type="dropcapitalline"> (pages 2)',
            'Region type "Footnotes" is not in the Ephrem profile: its text is exported as <ab type="footnotes"> '
            '(pages 2)',
            'Region type "Illustration" holds no text in the Ephrem profile: the text of its lines is not exported '
            '(pages 1)',
        ])

    # 10. facsimile and image links

    def test_facsimile(self):
        tree, _ = self.export()
        surface = self.xpath(tree, "//tei:surface")[0]
        self.assertEqual(surface.get(XML_ID), f"surface-{self.p1.pk}")
        self.assertEqual(surface.get("n"), "23r")
        region_zones = self.xpath(surface, "tei:zone")
        self.assertEqual(len(region_zones), 7)
        self.assertEqual([zone.get("type") for zone in region_zones[2].findall("tei:zone", NS)], ["line"] * 5)
        orphan = self.xpath(tree, "//tei:surface[2]/tei:zone[@xml:id='zone-l%s']" % self.orphan.pk)
        self.assertEqual(len(orphan), 1)

    def test_image_links(self):
        tree, names = self.export(include_images=True)
        urls = [graphic.get("url") for graphic in self.xpath(tree, "//tei:graphic")]
        self.assertEqual(urls, ["MS1%20f23r.png", "MS1%20f23v.png", "MS1%20f24r.png", "MS1%20f25r.png"])
        self.assertEqual(sorted(names), sorted([unquote(url) for url in urls] + ["example-ms-1.xml"]))

    def test_plain_xml_without_images(self):
        _tree, names = self.export()
        self.assertTrue(names[0].endswith(".xml"))

    def test_source_link(self):
        DocumentPart.objects.filter(pk=self.p1.pk).update(source="https://iiif.example.org/a/full/full/0/default.jpg")
        DocumentPart.objects.filter(pk=self.p2.pk).update(source="pdf//scan.pdf")
        tree, _ = self.export()
        self.assertEqual([graphic.get("url") for graphic in self.xpath(tree, "//tei:graphic[@type='source']")],
                         ["https://iiif.example.org/a/full/full/0/default.jpg"])

    # 11. uncertain, illegible and added text

    def test_annotations(self):
        tree, _ = self.export()
        unclear = self.xpath(tree, "//tei:unclear")[0]
        self.assertEqual(unclear.get("reason"), "faded")
        self.assertEqual("".join(unclear.itertext()).split(), ["ܕܐܠ", "ܗܐ"])
        self.assertEqual(len(unclear.findall("tei:lb", NS)), 1)
        add = self.xpath(tree, "//tei:add[not(@facs)]")[0]
        self.assertEqual((add.get("place"), add.text), ("above", "ܘ"))
        gap = self.xpath(tree, "//tei:gap")[0]
        self.assertEqual((gap.get("reason"), gap.get("extent"), gap.get("unit")), ("illegible", "3", "chars"))
        # the placeholder is dropped: the line reads ܓ, the gap, then ܕ
        self.assertEqual((gap.getprevious().get("facs"), gap.getprevious().tail.strip(), gap.tail.split()[0]),
                         (f"#zone-l{self.gap_line.pk}", "ܓ", "ܕ"))

    def test_text_is_escaped(self):
        tree, _ = self.export()
        lb = self.xpath(tree, "//tei:lb[@facs='#zone-l%s']" % self.line3.pk)[0]
        self.assertEqual(lb.tail.strip(), "x < y & z")

    # 18. annotations across the structure

    def test_annotation_into_a_heading(self):
        self.annotate("unclear", self.heading, 0, self.line1, 2)
        self.assertProblems('Page 1 (MS1 f23r.png), column a, line 1: the "unclear" annotation crosses a heading boundary')

    def test_annotation_into_a_note(self):
        self.annotate("unclear", self.line3, 0, self.note, 2)
        self.assertProblems('Page 1 (MS1 f23r.png), column a, line 4: the "unclear" annotation crosses a note boundary')

    def test_annotation_into_another_paragraph(self):
        self.annotate("add", self.gap_line, 6, self.drop_capital, 1)
        self.assertProblems('Page 2 (MS1 f23v.png), line 1: the "add" annotation crosses a paragraph boundary')

    def test_annotation_into_text_not_exported(self):
        self.annotate("unclear", self.left2, 0, self.caption, 1)
        self.assertProblems('Page 1 (MS1 f23r.png), column b, line 2: the "unclear" annotation runs into text that is '
                            'not exported')

    def test_overlapping_annotations(self):
        self.annotate("add", self.line2, 0, self.line3, 1)
        self.assertProblems('Page 1 (MS1 f23r.png), column a, line 3: the "add" annotation overlaps the "unclear" '
                            'annotation')

    def test_annotation_outside_the_text(self):
        self.annotate("unclear", self.line3, 5, self.line3, 50)
        self.assertProblems('Page 1 (MS1 f23r.png), column a, line 4: the "unclear" annotation does not fit the text '
                            'of its lines')

    # other checks

    def test_folio_problems(self):
        DocumentPart.objects.filter(pk=self.p1.pk).update(name="")
        DocumentPart.objects.filter(pk=self.p2.pk).update(name="f. 23v")
        DocumentPart.objects.filter(pk=self.p4.pk).update(name="24r")
        self.assertProblems(
            "Page 1 (MS1 f23r.png): no name; set the page Name to the folio, e.g. 23r",
            'Page 2 (MS1 f23v.png): name "f. 23v" contains a space; use the folio alone, e.g. 23r',
            'Pages 3, 4: all are named "24r"',
        )

    def test_forbidden_character(self):
        LineTranscription.objects.filter(line=self.line3).update(content="x\x07")
        self.assertProblems("Page 1 (MS1 f23r.png), column a, line 4: character U+0007 is not allowed in XML")

    def test_no_pages(self):
        exporter = EphremTEIExporter([], self.region_types(), False, False,
                                     self.user, self.document, None, self.transcription)
        with self.assertRaises(EphremTEIError) as context:
            exporter.render()
        self.assertEqual(context.exception.problems, ["Document: there are no pages to export"])


class ReadinessTestCase(EphremTEITestCase):
    """The readiness check runs the export's checks and writes nothing."""

    def test_report(self):
        self.set_metadata("Shelfmark", "MS 1")
        part = self.part("")
        with CascadeUpdate.bypass():
            region = self.region(part, "TableZone", (0, 0, 10, 10))
            first = self.line(part, region, "ܐ", (0, 0, 10, 5))
            second = self.line(part, None, "ܒ", (0, 6, 10, 10))
        self.annotate("unclear", first, 0, second, 1)
        report = check_document(self.document, [part.pk], self.transcription, self.region_types())
        self.assertFalse(report["ready"])
        self.assertIsNone(report["record_id"])
        self.assertEqual(report["pages"], 1)
        self.assertEqual({problem["category"]: problem["message"] for problem in report["errors"]}, {
            "metadata": 'Document: metadata "repository" is missing',
            "work": 'Page 1 (MS1 f.png): no work; set page metadata "work" or document metadata "work"',
            "folio": "Page 1 (MS1 f.png): no name; set the page Name to the folio, e.g. 23r",
            "annotations": 'Page 1 (MS1 f.png), line 1: the "unclear" annotation crosses a paragraph boundary',
        })
        self.assertEqual(sum(1 for problem in report["errors"] if problem["category"] == "metadata"), 2)
        self.assertEqual(report["summary"]["types"], {"errors": 0, "warnings": 1})
        self.assertEqual(os.listdir(self.user.get_document_store_path()) if os.path.exists(
            self.user.get_document_store_path()) else [], [])

    def test_ready(self):
        self.required_metadata()
        part = self.part("1r")
        with CascadeUpdate.bypass():
            self.line(part, self.region(part, "MainZone", (0, 0, 10, 10)), "ܐ", (0, 0, 10, 5))
        report = check_document(self.document, [part.pk], self.transcription, self.region_types())
        self.assertTrue(report["ready"], report["errors"])
        self.assertEqual(report["record_id"], "example-ms-1")
