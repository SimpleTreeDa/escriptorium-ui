"""
TEI export for the Ephrem Project: one TEI document per eScriptorium document, built
from the pages marked "Ready for TEI export", with the manuscript and work identification
taken from the document's metadata, responsibility from who transcribed and approved the
pages, and the text as page breaks, one anonymous block per region and line breaks.

The result is checked against a RelaxNG schema (tei/ephrem_tei.rng) describing the subset
of TEI written here, so that a malformed document is never handed out.
"""
import os.path
import re
from itertools import groupby
from urllib.parse import quote

from django.apps import apps
from django.conf import settings
from django.utils import timezone
from lxml import etree

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "tei", "ephrem_tei.rng")

READY_STATUS = "ready_for_tei"

# document (or page) metadata read, by field name; the first name found is used,
# ignoring case and spaces around it
METADATA_FIELDS = {
    "identifier": ("Identifier", "Record identifier", "ID"),
    "work": ("Work", "Work title"),
    "work_uri": ("Work URI",),
    "author": ("Author",),
    "shelfmark": ("Shelfmark", "Shelf mark", "Call number"),
    "repository": ("Repository", "Library"),
    "settlement": ("Settlement", "City"),
    "language": ("Language",),
}
REQUIRED_FIELDS = ("work", "shelfmark")
DEFAULT_LANGUAGE = ("syr", "Syriac")
# BCP 47 language tag, as xml:lang wants
LANGUAGE_CODE = re.compile(r"^[a-zA-Z]{2,8}(-[a-zA-Z0-9]{1,8})*$")


class TEIExportError(Exception):
    """The export cannot be made; the messages tell the user what to fix."""

    def __init__(self, messages):
        self.messages = messages
        super().__init__("\n".join(messages))

    @property
    def user_message(self):
        """A short message for the notification, the full list is in the task report."""
        more = len(self.messages) - 1
        return "The TEI export could not be made: %s%s" % (
            self.messages[0], " (%d more problems in the report)" % more if more else "")


def tei(tag):
    return "{%s}%s" % (TEI_NS, tag)


def sub(parent, tag, text=None, **attributes):
    element = etree.SubElement(parent, tei(tag))
    for name, value in attributes.items():
        if value is None:
            continue
        name = "{%s}%s" % (XML_NS, name[4:]) if name.startswith("xml_") else name
        element.set(name, str(value))
    if text is not None:
        element.text = text
    return element


def read_metadata(entries):
    """
    The METADATA_FIELDS values found in (field name, value) pairs.
    """
    by_name = {}
    for name, value in entries:
        if value and value.strip():
            by_name.setdefault(name.strip().lower(), value.strip())
    found = {}
    for field, names in METADATA_FIELDS.items():
        for name in names:
            if name.lower() in by_name:
                found[field] = by_name[name.lower()]
                break
    return found


def xml_id(prefix, value):
    """An xml:id (NCName) made of a prefix and any string."""
    return "%s-%s" % (prefix, re.sub(r"[^\w.-]", "_", str(value)))


class TEIDocumentBuilder:
    """
    Build the TEI document of the given parts of a document, from a transcription layer.
    `region_filters` is a Q object on LineTranscriptions, see Block.get_filters.
    """

    def __init__(self, document, parts, transcription, region_filters, document_url):
        self.document = document
        self.parts = list(parts)
        self.transcription = transcription
        self.region_filters = region_filters
        self.document_url = document_url
        self.warnings = []
        # xml:ids of the people already named in the header
        self.declared = set()

    # data

    def document_metadata(self):
        DocumentMetadata = apps.get_model("core", "DocumentMetadata")
        entries = (DocumentMetadata.objects.filter(document=self.document)
                   .values_list("key__name", "value"))
        return read_metadata(entries)

    def part_metadata(self, part):
        return read_metadata((m.key.name, m.value) for m in part.metadata.all())

    def lines_by_part(self):
        LineTranscription = apps.get_model("core", "LineTranscription")
        lines = (
            LineTranscription.objects
            .filter(transcription=self.transcription,
                    line__document_part__in=[p.pk for p in self.parts])
            .filter(self.region_filters)
            .exclude(content="")
            .select_related("line", "line__block", "line__block__typology")
            .order_by("line__document_part__order", "line__order")
        )
        by_part = {}
        for lt in lines:
            by_part.setdefault(lt.line.document_part_id, []).append(lt)
        return by_part

    def users(self, usernames):
        User = apps.get_model("users", "User")
        return {u.username: u for u in User.objects.filter(username__in=usernames)}

    # checks

    def check(self, metadata, parts_metadata):
        errors = []
        if not self.parts:
            errors.append(
                'None of the selected images is "Ready for TEI export". Set their status '
                'on the Images page (select them, then "Set status") once they are reviewed.')
        if "shelfmark" not in metadata:
            errors.append(
                'The manuscript is not identified: add a metadata field named "Shelfmark" '
                "to the document (Edit document > Metadata), e.g. \"Add. 14572\".")
        missing_work = [p for p in self.parts
                        if "work" not in metadata and "work" not in parts_metadata[p.pk]]
        if missing_work:
            names = ", ".join(p.title for p in missing_work[:10])
            errors.append(
                'The work is not identified: add a metadata field named "Work" to the '
                "document (Edit document > Metadata), or to each image of a different work "
                "(Element details > Metadata). Missing for: %s%s." % (
                    names, " and %d more" % (len(missing_work) - 10) if len(missing_work) > 10 else ""))
        if "language" in metadata and not LANGUAGE_CODE.match(metadata["language"]):
            errors.append(
                'The "Language" metadata field must be a language code such as "syr" '
                '(Syriac), not "%s".' % metadata["language"])
        if errors:
            raise TEIExportError(errors)

    # building

    def build(self):
        metadata = self.document_metadata()
        parts_metadata = {p.pk: self.part_metadata(p) for p in self.parts}
        self.check(metadata, parts_metadata)
        lines = self.lines_by_part()
        for part in self.parts:
            if not lines.get(part.pk):
                self.warnings.append(
                    'No transcription on %s in the layer "%s".' % (part.title, self.transcription.name))

        manual_authors = sorted({lt.version_author for part_lines in lines.values()
                                 for lt in part_lines
                                 if lt.version_author
                                 and lt.version_source == settings.VERSIONING_DEFAULT_SOURCE})
        models = sorted({lt.version_source.split(":", 1)[1] for part_lines in lines.values()
                         for lt in part_lines
                         if lt.version_source and lt.version_source.startswith("kraken:")})
        approvers = sorted({p.editorial_status_by.username for p in self.parts
                            if p.editorial_status_by})
        users = self.users(set(manual_authors) | set(approvers))

        root = etree.Element(tei("TEI"), nsmap={None: TEI_NS})
        root.set("{%s}lang" % XML_NS, "en")
        self.build_header(root, metadata, manual_authors, models, approvers, users)
        self.build_facsimile(root)
        self.build_text(root, metadata, parts_metadata, lines)
        return etree.ElementTree(root)

    def person(self, parent, username, users):
        """
        A user's name; the first mention declares their xml:id, the next ones point to it.
        """
        user = users.get(username)
        full_name = (user.get_full_name().strip() if user else "") or username
        identifier = xml_id("user", username)
        if identifier in self.declared:
            sub(parent, "name", full_name, type="person", ref="#" + identifier)
        else:
            self.declared.add(identifier)
            sub(parent, "name", full_name, type="person", xml_id=identifier)

    def build_header(self, root, metadata, manual_authors, models, approvers, users):
        header = sub(root, "teiHeader")
        file_desc = sub(header, "fileDesc")

        title_stmt = sub(file_desc, "titleStmt")
        sub(title_stmt, "title", metadata.get("work") or self.document.name,
            level="a", ref=metadata.get("work_uri"))
        sub(title_stmt, "title", "%s, %s" % (self.document.name, metadata["shelfmark"]), type="sub")
        if metadata.get("author"):
            sub(title_stmt, "author", metadata["author"])
        if manual_authors:
            resp_stmt = sub(title_stmt, "respStmt")
            sub(resp_stmt, "resp", "Syriac text transcribed by")
            for username in manual_authors:
                self.person(resp_stmt, username, users)
        if models:
            resp_stmt = sub(title_stmt, "respStmt")
            sub(resp_stmt, "resp", "Initial automatic transcription by the kraken model")
            for model in models:
                sub(resp_stmt, "name", model, type="software")
        if approvers:
            resp_stmt = sub(title_stmt, "respStmt")
            sub(resp_stmt, "resp", "Reviewed and approved for publication by")
            for username in approvers:
                self.person(resp_stmt, username, users)

        publication_stmt = sub(file_desc, "publicationStmt")
        sub(publication_stmt, "authority", "Ephrem Project")
        identifier = metadata.get("identifier") or self.document_url
        sub(publication_stmt, "idno", identifier,
            type="URI" if re.match(r"^[a-z][a-z0-9+.-]*:\S+$", identifier, re.I) else "local")
        sub(publication_stmt, "date", when=self.export_date())

        source_desc = sub(file_desc, "sourceDesc")
        ms_desc = sub(source_desc, "msDesc")
        ms_identifier = sub(ms_desc, "msIdentifier")
        if metadata.get("settlement"):
            sub(ms_identifier, "settlement", metadata["settlement"])
        if metadata.get("repository"):
            sub(ms_identifier, "repository", metadata["repository"])
        sub(ms_identifier, "idno", metadata["shelfmark"], type="shelfmark")
        works = []
        for part in self.parts:
            work = self.work_of(part, metadata)
            if work not in works:
                works.append(work)
        ms_contents = sub(ms_desc, "msContents")
        for index, work in enumerate(works, start=1):
            ms_item = sub(ms_contents, "msItem", n=index)
            if metadata.get("author"):
                sub(ms_item, "author", metadata["author"])
            sub(ms_item, "title", work, ref=metadata.get("work_uri") if work == metadata.get("work") else None)

        profile_desc = sub(header, "profileDesc")
        lang_usage = sub(profile_desc, "langUsage")
        language_code, language_name = self.language(metadata)
        sub(lang_usage, "language", language_name, ident=language_code)

        revision_desc = sub(header, "revisionDesc", status=READY_STATUS)
        for part in self.parts:
            change = sub(revision_desc, "change", '%s: Ready for TEI export' % part.title,
                         when=part.editorial_status_at.date().isoformat()
                         if part.editorial_status_at else None,
                         who="#" + xml_id("user", part.editorial_status_by.username)
                         if part.editorial_status_by else None)
            change.set("status", READY_STATUS)

    def build_facsimile(self, root):
        facsimile = sub(root, "facsimile")
        for part in self.parts:
            surface = sub(facsimile, "surface", n=part.title, xml_id=self.surface_id(part))
            sub(surface, "graphic", url=quote(part.filename))

    def build_text(self, root, metadata, parts_metadata, lines):
        language_code, _ = self.language(metadata)
        text = sub(root, "text", xml_lang=language_code)
        body = sub(text, "body")
        div = None
        current_work = None
        for part in self.parts:
            work = self.work_of(part, metadata, parts_metadata[part.pk])
            if div is None or work != current_work:
                current_work = work
                div = sub(body, "div", type="work", n=work)
            sub(div, "pb", n=part.name or str(part.order + 1), facs="#" + self.surface_id(part))
            part_lines = lines.get(part.pk, [])
            # one block per region, in reading order; lines outside regions make their own
            for _, region_lines in groupby(part_lines, key=lambda lt: lt.line.block_id):
                region_lines = list(region_lines)
                block = region_lines[0].line.block
                ab = sub(div, "ab", type=self.region_type(block))
                for lt in region_lines:
                    lb = sub(ab, "lb", n=lt.line.order + 1)
                    lb.tail = lt.content

    # helpers

    def work_of(self, part, metadata, part_metadata=None):
        if part_metadata is None:
            part_metadata = self.part_metadata(part)
        return part_metadata.get("work") or metadata.get("work")

    def language(self, metadata):
        code = metadata.get("language")
        if not code or code == DEFAULT_LANGUAGE[0]:
            return DEFAULT_LANGUAGE
        return code, code

    def region_type(self, block):
        if block is None:
            return "no-region"
        if block.typology:
            return re.sub(r"\s+", "-", block.typology.name.strip()) or "text"
        return "text"

    def surface_id(self, part):
        return xml_id("page", part.pk)

    def export_date(self):
        return timezone.now().date().isoformat()


def validate(tree):
    """
    Errors of the TEI document against the Ephrem Project TEI profile, [] if it is valid.
    """
    schema = etree.RelaxNG(etree.parse(SCHEMA_PATH))
    if schema.validate(tree):
        return []
    return ["line %d: %s" % (error.line, error.message) for error in schema.error_log]


def serialize(tree):
    return etree.tostring(tree, xml_declaration=True, encoding="UTF-8", pretty_print=True)
