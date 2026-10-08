"""
Stage 3 of the "TEI (Ephrem)" export: write the TEI file from the plan of stage 2, with lxml.
Text is always set as text, never parsed as markup, so it needs no escaping by hand.
"""
from urllib.parse import quote

from lxml import etree
from lxml.builder import ElementMaker

from . import profile
from .layout import HEAD_BLOCK, PARAGRAPH_BLOCK, UNKNOWN_BLOCK

E = ElementMaker(namespace=profile.TEI_NS, nsmap={None: profile.TEI_NS})
XML_ID = "{%s}id" % profile.XML_NS
XML_LANG = "{%s}lang" % profile.XML_NS

EDITORIAL_DECLARATION = (
    'Diplomatic transcription made in Transcriptus, from the transcription layer "{}". '
    "One lb element per manuscript line, one pb element per page and one cb element per column. "
    "Headings (head) and paragraphs (p) are those the editors marked; the rest of the text is in ab elements. "
    "Line text is as entered: not normalised and not punctuated."
)


def points(polygon):
    return " ".join(",".join(str(int(value)) for value in point) for point in polygon)


def attributes(*pairs, **named):
    """Element attributes in the order given, without the empty ones."""
    values = dict(pairs)
    values.update(named)
    return {name: str(value) for name, value in values.items() if value not in (None, "")}


def append_text(parent, text):
    if not text:
        return
    if len(parent):
        parent[-1].tail = (parent[-1].tail or "") + text
    else:
        parent.text = (parent.text or "") + text


def header(plan):
    title_stmt = E.titleStmt(E.title(plan.title))
    for person in plan.people:
        title_stmt.append(E.respStmt(*[E.resp(role) for role in person.roles],
                                     E.persName(person.name, attributes((XML_ID, person.id)))))
    for model in plan.models:
        name = E.name("kraken model %s" % model.name, attributes(("type", "software"), (XML_ID, model.id)))
        title_stmt.append(E.respStmt(E.resp(profile.MODEL_ROLE), name))

    publication = E.publicationStmt(E.authority(plan.authority), E.idno(plan.record_id, type="ephrem"))
    if plan.uri:
        publication.append(E.idno(plan.uri, type="URI"))
    publication.append(E.date(when=plan.export_date))

    identifier = E.msIdentifier()
    if plan.settlement:
        identifier.append(E.settlement(plan.settlement))
    identifier.append(E.repository(plan.repository))
    identifier.append(E.idno(plan.shelfmark, type="shelfmark"))
    contents = E.msContents()
    for work in plan.works:
        item = E.msItem(attributes((XML_ID, work.id), ("n", work.n)))
        for first, last in work.loci:
            item.append(E.locus(attributes(("from", first), ("to", last))))
        if work.author:
            item.append(E.author(work.author))
        item.append(E.title(work.title, attributes(("ref", work.uri))))
        contents.append(item)

    revisions = E.revisionDesc(status=plan.stage)
    for change in plan.changes:
        revisions.append(E.change(change.label, attributes(
            (XML_ID, change.id), ("when", change.when), ("who", change.who and "#" + change.who),
            ("status", change.status), ("target", f"#surface-{change.page.pk}"))))

    return E.teiHeader(
        E.fileDesc(title_stmt, publication, E.sourceDesc(E.msDesc(identifier, contents))),
        E.encodingDesc(E.editorialDecl(E.p(EDITORIAL_DECLARATION.format(plan.transcription)))),
        E.profileDesc(E.langUsage(E.language("English", ident="en"),
                                  E.language(profile.LANGUAGES[plan.language], ident=plan.language))),
        revisions,
    )


def facsimile(plan):
    facsimile = E.facsimile()
    for layout in plan.pages:
        page = layout.page
        surface = E.surface(attributes((XML_ID, f"surface-{page.pk}"), ("n", page.name), ("ulx", 0), ("uly", 0),
                                       ("lrx", page.width), ("lry", page.height),
                                       ("change", "#" + plan.page_change[page.pk])))
        # the image file name, percent-encoded: decoding the URL gives the exact name back
        surface.append(E.graphic(url=quote(page.filename, safe="/"), width=f"{page.width}px",
                                 height=f"{page.height}px"))
        if profile.is_web_address(page.source):
            surface.append(E.graphic(type="source", url=page.source))
        zones = {}
        for region in page.regions:
            zones[region.pk] = E.zone(attributes((XML_ID, f"zone-r{region.pk}"),
                                                 ("type", profile.type_value(region.type_name)),
                                                 ("points", points(region.polygon))))
            surface.append(zones[region.pk])
        for line in page.lines:
            if line.mask:
                zone = E.zone(attributes((XML_ID, f"zone-l{line.pk}"), ("type", "line"), ("points", points(line.mask))))
                zones.get(line.region_pk, surface).append(zone)
        facsimile.append(surface)
    return facsimile


class BodyWriter:
    """
    Writes the text flow: the logical structure (div, head, p, ab) as elements and the physical
    structure (pb, cb, lb) as milestones inside them, with notes, additions and page furniture
    after the line they belong to.
    """

    def __init__(self, plan):
        self.plan = plan
        self.body = E.body()
        self.work = self.section = self.block = None
        self.block_index = None
        self.sections = 0
        self.inline = []  # the annotation elements open in the current block
        self.pending = []  # milestones (pb, cb) and page-top furniture waiting for the next text

    def div(self):
        return self.section if self.section is not None else self.work

    def target(self):
        """Where text and milestones go now."""
        if self.inline:
            return self.inline[-1]
        if self.block is not None:
            return self.block
        return self.div()

    def flush(self, parent):
        for element in self.pending:
            parent.append(element)
        self.pending = []

    def close_block(self):
        if self.inline:
            raise RuntimeError("An annotation runs past the end of its block")
        self.block, self.block_index = None, None

    def end_division(self):
        if self.work is not None:
            # milestones of pages without text go where the text stopped
            self.flush(self.target())
        self.close_block()
        self.section, self.sections = None, 0

    def write(self):
        for division in self.plan.divisions:
            self.end_division()
            self.work = E.div(type="work", n=str(division.work.n), corresp="#" + division.work.id)
            self.body.append(self.work)
            for layout in division.layouts:
                self.write_page(layout)
        self.end_division()
        return self.body

    def write_page(self, layout):
        page = layout.page
        self.pending.append(E.pb(n=page.name, facs=f"#surface-{page.pk}"))
        self.pending.extend(self.float_element(item) for item in layout.start_floats)
        column = None
        for item in layout.flow:
            if layout.columns and item.column != column:
                column = item.column
                self.pending.append(E.cb(n=column))
            if item.block != self.block_index:
                block = self.plan.blocks[item.block]
                self.close_block()
                if block.opens_section:
                    # TEI only allows a head at the start of a division
                    self.sections += 1
                    self.section = E.div(type="section", n=str(self.sections))
                    self.work.append(self.section)
                self.flush(self.div())
                self.block, self.block_index = self.block_element(block), item.block
                self.div().append(self.block)
            else:
                self.flush(self.target())
            self.target().append(E.lb(attributes(("n", item.number),
                                                 ("facs", item.line.mask and f"#zone-l{item.line.pk}"))))
            self.write_events(item.events, self.inline, lambda: self.target())
            for float_item in layout.floats_after(item.line.pk):
                self.target().append(self.float_element(float_item))

    @staticmethod
    def block_element(block):
        if block.kind == HEAD_BLOCK:
            return E.head()
        if block.kind == PARAGRAPH_BLOCK:
            return E.p()
        if block.kind == UNKNOWN_BLOCK and block.type_value:
            return E.ab(type=block.type_value)
        return E.ab()

    @staticmethod
    def write_events(events, stack, target):
        for event in events:
            if event[0] == "text":
                append_text(target(), event[1])
            elif event[0] == "open":
                element = E(event[1], attributes(*event[2]))
                target().append(element)
                stack.append(element)
            elif event[0] == "close":
                stack.pop()
            else:
                target().append(E(event[1], attributes(*event[2])))

    def float_element(self, item):
        if item.role == profile.NOTE_MARGIN:
            element = E.note(place="margin")
        elif item.role == profile.NOTE_COMMENTARY:
            element = E.note(type="commentary")
        elif item.role == profile.ADD:
            element = E.add(place="above")
        else:
            element = E.fw(type=profile.FW_TYPES[item.role])
        if item.region is not None:
            element.set("facs", f"#zone-r{item.region.pk}")
        elif item.lines[0].mask:
            element.set("facs", f"#zone-l{item.lines[0].pk}")
        stack = [element]
        for line in item.lines:
            if item.region is not None:
                # a region of its own: its lines are manuscript lines, not counted with the text's
                stack[-1].append(E.lb(attributes(("facs", line.mask and f"#zone-l{line.pk}"))))
            self.write_events(item.events.get(line.pk, []), stack, lambda: stack[-1])
        if len(stack) != 1:
            raise RuntimeError("An annotation runs past the end of its note")
        return element


TEXT_BLOCKS = ("head", "p", "ab", "note", "fw")
BREAKS = ("lb", "pb", "cb", "note", "fw")


def indent(element, level=0):
    """Indent the file for reading, adding whitespace only where it doesn't change the text."""
    if etree.QName(element).localname in TEXT_BLOCKS:
        if any(etree.QName(child).localname in BREAKS for child in element.iter() if child is not element):
            break_lines(element, level)
            last = "\n" + "  " * level
            if len(element):
                element[-1].tail = (element[-1].tail or "") + last
            else:
                element.text = (element.text or "") + last
        return
    children = list(element)
    if not children:
        return
    element.text = "\n" + "  " * (level + 1)
    for child in children:
        indent(child, level + 1)
        child.tail = "\n" + "  " * (level + 1)
    children[-1].tail = "\n" + "  " * level


def break_lines(element, level):
    """In a block of text, start every line break, page break, column break, note and fw on a new line."""
    newline = "\n" + "  " * (level + 1)
    previous = None
    for child in element:
        name = etree.QName(child).localname
        if name in BREAKS:
            if previous is None:
                element.text = (element.text or "") + newline
            else:
                previous.tail = (previous.tail or "") + newline
        if name in ("note", "fw"):
            indent(child, level + 1)
        elif len(child):
            break_lines(child, level)
        previous = child


def build(plan):
    """The TEI file of the plan, as bytes."""
    root = E.TEI(
        header(plan),
        facsimile(plan),
        E.text(BodyWriter(plan).write(), attributes((XML_LANG, plan.language), ("type", "ManuscriptTranscription"))),
        attributes((XML_ID, plan.record_id), (XML_LANG, "en")),
    )
    indent(root)
    # the schema is declared in the file, so that TEI editors such as Oxygen validate it
    prolog = ('<?xml version="1.0" encoding="UTF-8"?>\n'
              f'<?xml-model href="{profile.TEI_SCHEMA_URL}" type="application/xml" '
              'schematypens="http://relaxng.org/ns/structure/1.0"?>\n')
    return prolog.encode("utf-8") + etree.tostring(root, encoding="UTF-8") + b"\n"
