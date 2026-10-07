"""
Stage 4 of the "TEI (Ephrem)" export: check the file made in stage 3.

- schema_errors(): RelaxNG validation against TEI P5 tei_all.rng (profile.schema_path()).
- link_errors(): every internal pointer (#surface-…, #zone-…, #work-…, #pers-…, #status-…) points to an
  element of the right kind in the file. RelaxNG can't check this: pointers are just URIs to it.
- requirement_errors(): the brief's eleven required items are in the file, with the profile's conventions.

The data checks of stage 2 should make all three pass, so an error here is a bug in the exporter.
These functions take a parsed file and use nothing else, so they can check any Ephrem TEI file.
"""
import functools
from urllib.parse import quote, unquote

from lxml import etree

from . import profile

NS = {"tei": profile.TEI_NS}
TEI = "{%s}" % profile.TEI_NS
XML_ID = "{%s}id" % profile.XML_NS
LINK_ATTRIBUTES = ("facs", "who", "target", "corresp", "change")
# what each pointer must point to: (element, attribute) -> allowed target elements (and zone type)
TARGETS = {
    ("pb", "facs"): ("surface",),
    ("lb", "facs"): ("zone/line",),
    ("note", "facs"): ("zone",),
    ("fw", "facs"): ("zone",),
    ("add", "facs"): ("zone",),
    ("change", "target"): ("surface",),
    ("change", "who"): ("persName",),
    ("div", "corresp"): ("msItem",),
    ("surface", "change"): ("change",),
}


@functools.lru_cache(maxsize=1)
def tei_schema():
    # compiling tei_all.rng takes several seconds, so it is done once per process
    return etree.RelaxNG(etree.parse(profile.schema_path()))


def parse(content):
    """The file (bytes) as an lxml tree, or raise etree.XMLSyntaxError."""
    return etree.ElementTree(etree.fromstring(content))


def schema_errors(tree, limit=5):
    schema = tei_schema()
    if schema.validate(tree):
        return []
    return [f"line {error.line}: {error.message}" for error in list(schema.error_log)[:limit]]


def localname(element):
    return etree.QName(element).localname


def link_errors(tree):
    root = tree.getroot()
    ids = {element.get(XML_ID): element for element in root.iter(etree.Element) if element.get(XML_ID)}
    errors = []
    for element in root.iter(etree.Element):
        for attribute in LINK_ATTRIBUTES:
            for value in (element.get(attribute) or "").split():
                target = ids.get(value[1:]) if value.startswith("#") else None
                if target is None:
                    errors.append(f'line {element.sourceline}: @{attribute}="{value}" does not point to an id in the file')
                    continue
                allowed = TARGETS.get((localname(element), attribute))
                kind = localname(target)
                if kind == "zone" and target.get("type") == "line":
                    kind = "zone/line"
                if allowed and kind not in allowed and not (kind == "zone/line" and "zone" in allowed):
                    errors.append(f'line {element.sourceline}: {localname(element)}/@{attribute}="{value}" '
                                  f'points to a {localname(target)}, not a {" or ".join(allowed)}')
    return errors


def xpath(element, path):
    return element.xpath(path, namespaces=NS)


def requirement_errors(tree):
    """The brief's eleven required items, each checked on the file; empty if they are all there."""
    root = tree.getroot()
    errors = []

    def require(item, condition, message):
        if not condition:
            errors.append(f"Item {item}: {message}")

    # 1. stable record identifier
    record_id = root.get(XML_ID) or ""
    require(1, profile.RECORD_ID.match(record_id), "TEI/@xml:id is not a record id")
    require(1, xpath(root, "string(//tei:publicationStmt/tei:idno[@type='ephrem'])") == record_id,
            "publicationStmt/idno[@type='ephrem'] is not the record id")
    for uri in xpath(root, "//tei:publicationStmt/tei:idno[@type='URI']"):
        require(1, (uri.text or "").endswith(record_id), "the record URI does not end with the record id")

    # 2. manuscript identification
    for path in ("tei:repository", "tei:idno[@type='shelfmark']"):
        require(2, xpath(root, "string(//tei:msDesc/tei:msIdentifier/%s)" % path).strip(), f"msIdentifier has no {path}")

    # 3. works, and their relationship to the manuscript
    items = xpath(root, "//tei:msContents/tei:msItem")
    require(3, items, "msContents has no msItem")
    for item in items:
        require(3, xpath(item, "tei:locus") and xpath(item, "string(tei:title)").strip(),
                f"msItem {item.get(XML_ID)} has no locus or no title")
    divs = xpath(root, "//tei:body/tei:div[@type='work']")
    require(3, divs, "the text has no work division")
    linked = {div.get("corresp") for div in divs}
    for item in items:
        require(3, "#" + (item.get(XML_ID) or "") in linked, f"no work division points to msItem {item.get(XML_ID)}")

    # 4. language
    language = xpath(root, "string(//tei:text/@xml:lang)")
    require(4, language in profile.LANGUAGES, 'text/@xml:lang "%s" is not an approved Syriac tag' % language)
    require(4, xpath(root, "//tei:profileDesc/tei:langUsage/tei:language[@ident='%s']" % language),
            "the language of the text is not declared in langUsage")

    # 5. responsibility: every credit names someone, and every change's @who is credited
    for statement in xpath(root, "//tei:titleStmt/tei:respStmt"):
        require(5, xpath(statement, "tei:resp") and xpath(statement, "tei:persName | tei:name"),
                "a respStmt has no resp or no name")

    # 6. review status: the current stage is the least advanced page, every page is linked to its status
    surfaces = xpath(root, "//tei:facsimile/tei:surface")
    ids = {element.get(XML_ID): element for element in root.iter(etree.Element) if element.get(XML_ID)}
    current = []
    for surface in surfaces:
        change = ids.get((surface.get("change") or "")[1:])
        status = change.get("status") if change is not None else None
        require(6, status in profile.STATUS_ORDER, f"surface {surface.get('n')} is not linked to its status")
        current.append(status)
    stage = xpath(root, "string(//tei:revisionDesc/@status)")
    if current and all(status in profile.STATUS_ORDER for status in current):
        require(6, stage == min(current, key=profile.STATUS_ORDER.index),
                f'revisionDesc/@status "{stage}" is not the least advanced page status')

    # 7. divisions: a section starts with its heading
    for section in xpath(root, "//tei:div[@type='section']"):
        first = [child for child in section.iterchildren(etree.Element) if localname(child) not in ("pb", "cb", "fw", "note")]
        require(7, first and localname(first[0]) == "head", f"line {section.sourceline}: a section does not start with a head")

    # 8. folio and page breaks: one pb per surface, with the same folio
    pbs = xpath(root, "//tei:body//tei:pb")
    require(8, len(pbs) == len(surfaces), f"{len(pbs)} page breaks for {len(surfaces)} pages")
    names = [pb.get("n") or "" for pb in pbs]
    for pb in pbs:
        surface = ids.get((pb.get("facs") or "")[1:])
        require(8, surface is not None and surface.get("n") == pb.get("n"),
                f"line {pb.sourceline}: pb does not point to a surface with the same folio")
        require(8, pb.get("n") and len(pb.get("n").split()) == 1 and names.count(pb.get("n")) == 1,
                f'line {pb.sourceline}: folio "{pb.get("n")}" is not one unique word')

    # 9. lines: numbered from 1 in each column of each page
    errors.extend(line_number_errors(root))

    # 10. image links: every page has a percent-encoded image file name; source links are web addresses
    for surface in surfaces:
        graphics = xpath(surface, "tei:graphic[not(@type)]")
        require(10, len(graphics) == 1, f"surface {surface.get('n')} has no image link")
        for graphic in graphics:
            url = graphic.get("url") or ""
            require(10, url and quote(unquote(url), safe="/") == url,
                    f'line {graphic.sourceline}: image url "{url}" is not a percent-encoded file name')
        for graphic in xpath(surface, "tei:graphic[@type='source']"):
            require(10, profile.is_web_address(graphic.get("url")), f"line {graphic.sourceline}: source is not a web address")
    for zone in xpath(root, "//tei:zone"):
        require(10, not "".join(zone.xpath("text()")).strip(), f"line {zone.sourceline}: zone contains text")

    # 11. uncertain and illegible readings: gaps are empty, nothing else is
    for gap in xpath(root, "//tei:body//tei:gap"):
        require(11, not len(gap) and not (gap.text or "").strip(), f"line {gap.sourceline}: gap has content")
    for element in xpath(root, "//tei:body//tei:unclear | //tei:body//tei:add"):
        require(11, "".join(element.itertext()).strip() or len(element),
                f"line {element.sourceline}: {localname(element)} is empty")
    return errors


def line_number_errors(root):
    """Item 9: the numbered lines count from 1 on each page, and in each column of the page."""
    errors, counters, column = [], {}, None
    for element in xpath(root, "//tei:body//tei:pb | //tei:body//tei:cb | //tei:body//tei:lb[@n]"):
        if localname(element) == "pb":
            counters, column = {}, None
        elif localname(element) == "cb":
            column = element.get("n")
        else:
            counters[column] = counters.get(column, 0) + 1
            if element.get("n") != str(counters[column]):
                errors.append(f'Item 9: line {element.sourceline}: lb n="{element.get("n")}", '
                              f'expected {counters[column]}')
    return errors
