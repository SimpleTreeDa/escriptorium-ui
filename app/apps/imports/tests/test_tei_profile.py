"""
The Ephrem TEI profile (docs/tei/ephrem-tei-profile.md) checked on its two reference files: the
canonical sample, made from real eScriptorium data, and a synthetic document that uses every construct
in the profile. Also checks that the validation of stage 4 (imports/tei/validation.py) catches broken files.
"""
import copy
import os

from django.test import SimpleTestCase
from lxml import etree

from imports.tei.validation import NS, link_errors, requirement_errors, schema_errors

SAMPLES_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "samples",
)


def parse(filename):
    return etree.parse(os.path.join(SAMPLES_DIR, filename))


class EphremTEIProfileTestCase(SimpleTestCase):
    def assertEphremTEI(self, tree):
        self.assertEqual(schema_errors(tree), [])
        self.assertEqual(link_errors(tree), [])
        self.assertEqual(requirement_errors(tree), [])

    def test_canonical_sample(self):
        self.assertEphremTEI(parse("ephrem_tei_sample.xml"))

    def test_features_document(self):
        self.assertEphremTEI(parse("ephrem_tei_features.xml"))

    def broken(self, path, change, check=requirement_errors):
        """The errors check finds in the features document, after change(element) on the first element at path."""
        tree = copy.deepcopy(parse("ephrem_tei_features.xml"))
        change(tree.xpath(path, namespaces=NS)[0])
        return check(tree)

    # internal links

    def test_broken_link(self):
        errors = self.broken("//tei:lb[@facs]", lambda el: el.set("facs", "#zone-l0"), link_errors)
        self.assertEqual(len(errors), 1)
        self.assertIn('@facs="#zone-l0" does not point to an id in the file', errors[0])

    def test_link_without_hash(self):
        errors = self.broken("//tei:change[@who]", lambda el: el.set("who", "pers-1"), link_errors)
        self.assertIn('@who="pers-1" does not point to an id in the file', errors[0])

    def test_link_to_the_wrong_kind_of_element(self):
        errors = self.broken("//tei:pb", lambda el: el.set("facs", "#zone-r1"), link_errors)
        self.assertIn('pb/@facs="#zone-r1" points to a zone, not a surface', errors[0])
        errors = self.broken("//tei:body//tei:lb[@n]", lambda el: el.set("facs", "#zone-r3"), link_errors)
        self.assertIn('lb/@facs="#zone-r3" points to a zone, not a zone/line', errors[0])
        errors = self.broken("//tei:div[@type='work']", lambda el: el.set("corresp", "#pers-1"), link_errors)
        self.assertIn('div/@corresp="#pers-1" points to a persName, not a msItem', errors[0])

    def test_broken_status_link(self):
        errors = self.broken("//tei:surface", lambda el: el.set("change", "#status-0"), link_errors)
        self.assertIn('@change="#status-0" does not point to an id in the file', errors[0])

    # the eleven required items

    def test_record_id(self):
        errors = self.broken("//tei:publicationStmt/tei:idno", lambda el: setattr(el, "text", "other"))
        self.assertIn("Item 1: publicationStmt/idno[@type='ephrem'] is not the record id", errors)

    def test_manuscript(self):
        errors = self.broken("//tei:msIdentifier/tei:repository", lambda el: el.getparent().remove(el))
        self.assertIn("Item 2: msIdentifier has no tei:repository", errors)

    def test_work_without_division(self):
        errors = self.broken("//tei:msItem[2]", lambda el: el.set("{http://www.w3.org/XML/1998/namespace}id", "work-9"))
        self.assertIn("Item 3: no work division points to msItem work-9", errors)

    def test_language(self):
        errors = self.broken("//tei:text", lambda el: el.set("{http://www.w3.org/XML/1998/namespace}lang", "syc"))
        self.assertIn('Item 4: text/@xml:lang "syc" is not an approved Syriac tag', errors)

    def test_wrong_current_stage(self):
        errors = self.broken("//tei:revisionDesc", lambda el: el.set("status", "final"))
        self.assertEqual(errors, ['Item 6: revisionDesc/@status "final" is not the least advanced page status'])

    def test_page_without_status(self):
        errors = self.broken("//tei:surface[@n='25r']", lambda el: el.attrib.pop("change"))
        self.assertIn("Item 6: surface 25r is not linked to its status", errors)

    def test_section_without_heading(self):
        errors = self.broken("//tei:div[@type='section']/tei:head", lambda el: el.getparent().remove(el))
        # the heading's line goes too, so the line numbers are wrong as well
        self.assertTrue(any("a section does not start with a head" in error for error in errors), errors)

    def test_page_name_with_space(self):
        def rename(pb):
            pb.set("n", "f. 23r")
            pb.getroottree().xpath("//tei:surface[@n='23r']", namespaces=NS)[0].set("n", "f. 23r")
        errors = self.broken("//tei:pb", rename)
        self.assertEqual(len(errors), 1)
        self.assertIn('folio "f. 23r" is not one unique word', errors[0])

    def test_line_numbering(self):
        # the second column restarts at 1
        errors = self.broken("//tei:cb[@n='b']/following::tei:lb[1]", lambda el: el.set("n", "5"))
        self.assertEqual(len(errors), 1)
        self.assertIn('lb n="5", expected 1', errors[0])

    def test_unencoded_image_url(self):
        errors = self.broken("//tei:graphic", lambda el: el.set("url", "f#23r.jpg"))
        self.assertIn('image url "f#23r.jpg" is not a percent-encoded file name', errors[0])

    def test_text_in_zone(self):
        errors = self.broken("//tei:zone[@type='line']", lambda el: setattr(el, "text", "ܐ"))
        self.assertIn("zone contains text", errors[0])

    def test_gap_with_content(self):
        errors = self.broken("//tei:gap", lambda el: setattr(el, "text", "..."))
        self.assertIn("gap has content", errors[0])
