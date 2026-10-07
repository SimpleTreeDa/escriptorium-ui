"""
The Ephrem TEI profile (docs/tei/ephrem-tei-profile.md) checked on its two reference files:
the canonical sample, made from real eScriptorium data, and a synthetic document that uses
every construct in the profile. The TEI exporter's tests can run the same checks on its output.
"""
import copy
import os
from urllib.parse import quote, unquote

from django.conf import settings
from django.test import SimpleTestCase
from lxml import etree

SAMPLES_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "samples",
)
TEI_SCHEMA = os.path.join(settings.PROJECT_ROOT, "static", "tei_all.rng")

NS = {"tei": "http://www.tei-c.org/ns/1.0"}
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
TEI = "{http://www.tei-c.org/ns/1.0}"

# page editorial statuses, from the least to the most advanced
STATUSES = [
    "not_started", "in_progress", "transcribed", "reviewed_1",
    "reviewed_2", "ground_truth", "final", "ready_for_tei",
]
LINK_ATTRIBUTES = ("facs", "who", "target", "corresp")


def profile_errors(tree):
    """
    The profile rules that tei_all.rng can't check, as a list of messages (empty if the file follows them).
    """
    errors = []
    root = tree.getroot()
    ids = {el.get(XML_ID): el for el in root.iter() if el.get(XML_ID)}

    def xpath(path, el=root):
        return el.xpath(path, namespaces=NS)

    def linked(el, attribute):
        return ids.get((el.get(attribute) or "")[1:])

    # every link points to an id in the file
    for el in root.iter(etree.Element):
        for attribute in LINK_ATTRIBUTES:
            for value in (el.get(attribute) or "").split():
                if not value.startswith("#") or value[1:] not in ids:
                    errors.append(f"line {el.sourceline}: @{attribute}=\"{value}\" does not point to an id in the file")

    # record identifier
    record_id = root.get(XML_ID) or ""
    if not record_id.startswith("ephrem-doc-") or not record_id[len("ephrem-doc-"):].isdigit():
        errors.append("TEI/@xml:id \"%s\" is not ephrem-doc-{pk}" % record_id)
    if xpath("string(//tei:publicationStmt/tei:idno[@type='ephrem'])") != record_id:
        errors.append("publicationStmt/idno[@type='ephrem'] is not the record identifier")

    # manuscript and language
    for path in ("tei:repository", "tei:idno[@type='shelfmark']"):
        if not xpath("string(//tei:msIdentifier/%s)" % path).strip():
            errors.append("msIdentifier has no %s" % path)
    if xpath("string(//tei:text/@xml:lang)") != "syr" or not xpath("//tei:langUsage/tei:language[@ident='syr']"):
        errors.append("Syriac is not declared on text and in langUsage")

    # works
    for div in xpath("//tei:div[@type='work']"):
        if linked(div, "corresp") is None or linked(div, "corresp").tag != TEI + "msItem":
            errors.append(f"line {div.sourceline}: work div does not point to an msItem")

    # pages: one pb per surface, named alike, one word, unique
    surfaces, pbs = xpath("//tei:surface"), xpath("//tei:pb")
    if len(pbs) != len(surfaces):
        errors.append(f"{len(pbs)} page breaks for {len(surfaces)} surfaces")
    names = [pb.get("n") or "" for pb in pbs]
    for pb in pbs:
        surface = linked(pb, "facs")
        if surface is None or surface.tag != TEI + "surface" or surface.get("n") != pb.get("n"):
            errors.append(f"line {pb.sourceline}: pb does not point to a surface with the same n")
        if not pb.get("n") or len(pb.get("n").split()) != 1 or names.count(pb.get("n")) > 1:
            errors.append(f"line {pb.sourceline}: page name \"{pb.get('n')}\" is not one unique word")

    # lines: numbered from 1 on each page, linked to line zones; regions linked to region zones
    expected = 1
    for el in xpath("//tei:body//tei:pb | //tei:body//tei:lb"):
        if el.tag == TEI + "pb":
            expected = 1
            continue
        if el.get("n") != str(expected):
            errors.append(f"line {el.sourceline}: lb n=\"{el.get('n')}\", expected {expected}")
        expected += 1
        if el.get("facs") and (linked(el, "facs") is None or linked(el, "facs").get("type") != "line"):
            errors.append(f"line {el.sourceline}: lb does not point to a line zone")
    for el in xpath("//tei:body//*[self::tei:ab or self::tei:head or self::tei:note or self::tei:fw][@facs]"):
        zone = linked(el, "facs")
        if zone is None or zone.tag != TEI + "zone" or zone.get("type") == "line":
            errors.append(f"line {el.sourceline}: {etree.QName(el).localname} does not point to a region zone")

    # facsimile: zones hold no text, image file names are percent-encoded
    for zone in xpath("//tei:zone"):
        if "".join(zone.xpath("text()")).strip():
            errors.append(f"line {zone.sourceline}: zone contains text")
    for graphic in xpath("//tei:surface/tei:graphic[not(@type)]"):
        url = graphic.get("url")
        if quote(unquote(url), safe="/") != url:
            errors.append(f"line {graphic.sourceline}: image url \"{url}\" is not a percent-encoded file name")

    # status: known codes, every page has one, the current stage is the least advanced page
    changes = xpath("//tei:revisionDesc/tei:change")
    for el in [xpath("//tei:revisionDesc")[0]] + changes:
        if el.get("status") not in STATUSES:
            errors.append(f"line {el.sourceline}: unknown status \"{el.get('status')}\"")
    current = {}
    for change in changes:  # newest first, so the first change of a page is its current status
        current.setdefault(change.get("target"), change.get("status"))
    for surface in surfaces:
        if "#" + surface.get(XML_ID) not in current:
            errors.append(f"page {surface.get('n')} has no change")
    statuses = [s for s in current.values() if s in STATUSES]
    stage = xpath("string(//tei:revisionDesc/@status)")
    if statuses and stage != min(statuses, key=STATUSES.index):
        errors.append(f"revisionDesc/@status \"{stage}\" is not the least advanced page status")

    return errors


class EphremTEIProfileTestCase(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # compiling tei_all.rng takes several seconds, do it once
        cls.schema = etree.RelaxNG(etree.parse(TEI_SCHEMA))

    def parse(self, filename):
        return etree.parse(os.path.join(SAMPLES_DIR, filename))

    def assertEphremTEI(self, tree):
        self.assertTrue(self.schema.validate(tree), str(self.schema.error_log))
        self.assertEqual(profile_errors(tree), [])

    def test_canonical_sample(self):
        self.assertEphremTEI(self.parse("ephrem_tei_sample.xml"))

    def test_features_document(self):
        self.assertEphremTEI(self.parse("ephrem_tei_features.xml"))

    def broken(self, path, change):
        """The features document, with change(element) applied to the first element at path."""
        tree = copy.deepcopy(self.parse("ephrem_tei_features.xml"))
        change(tree.xpath(path, namespaces=NS)[0])
        return profile_errors(tree)

    def test_broken_link(self):
        errors = self.broken("//tei:lb[@facs]", lambda el: el.set("facs", "#zone-l0"))
        self.assertIn('@facs="#zone-l0" does not point to an id in the file', errors[0])

    def test_text_in_zone(self):
        errors = self.broken("//tei:zone[@type='line']", lambda el: setattr(el, "text", "ܐ"))
        self.assertIn("zone contains text", errors[0])

    def test_line_numbering(self):
        errors = self.broken("//tei:lb[@n='2']", lambda el: el.set("n", "3"))
        self.assertIn('lb n="3", expected 2', errors[0])

    def test_page_name_with_space(self):
        def rename(pb):
            pb.set("n", "f. 23r")
            pb.getroottree().xpath("//tei:surface[@n='23r']", namespaces=NS)[0].set("n", "f. 23r")
        errors = self.broken("//tei:pb", rename)
        self.assertIn('page name "f. 23r" is not one unique word', errors[0])

    def test_unencoded_image_url(self):
        errors = self.broken("//tei:graphic", lambda el: el.set("url", "f#23r.jpg"))
        self.assertIn('image url "f#23r.jpg" is not a percent-encoded file name', errors[0])

    def test_wrong_current_stage(self):
        errors = self.broken("//tei:revisionDesc", lambda el: el.set("status", "final"))
        self.assertIn('revisionDesc/@status "final" is not the least advanced page status', errors[0])

    def test_page_without_status(self):
        errors = self.broken("//tei:change[@target='#surface-904']", lambda el: el.getparent().remove(el))
        self.assertIn("page 25r has no change", errors[0])
