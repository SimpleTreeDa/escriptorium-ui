"""
The data of the "TEI (Ephrem)" export, as defined in docs/tei/ephrem-tei-profile.md:
read the document, check that it has everything the profile requires,
and arrange it for the export/ephrem_tei.xml template.
"""
import functools
import os
import re

from django.apps import apps
from django.conf import settings
from django.db.models import Avg
from django.utils import timezone
from django.utils.translation import override
from lxml import etree

from core.models import Block

TEI_SCHEMA_PATH = os.path.join(settings.PROJECT_ROOT, "static", "tei_all.rng")

REQUIRED_DOCUMENT_KEYS = ("repository", "shelfmark")
DOCUMENT_KEYS = ("repository", "shelfmark", "settlement", "work", "author")

TRANSCRIBED = "Syriac text transcribed by"
REVIEWED = "Reviewed by"
EDITED = "Edited by"
ROLES = (TRANSCRIBED, REVIEWED, EDITED)
# the role of whoever sets a page to a status
STATUS_ROLES = {
    "in_progress": TRANSCRIBED,
    "transcribed": TRANSCRIBED,
    "reviewed_1": REVIEWED,
    "reviewed_2": REVIEWED,
    "ground_truth": EDITED,
    "final": EDITED,
    "ready_for_tei": EDITED,
}

# region types (lower case) that are not plain blocks of text; any other region is an <ab>
HEAD = ("head", ())
MARGIN_NOTE = ("note", (("place", "margin"),))
REGION_ELEMENTS = {
    "title": HEAD,
    "heading": HEAD,
    "rubric": HEAD,
    "margin": MARGIN_NOTE,
    "marginalia": MARGIN_NOTE,
    "margintextzone": MARGIN_NOTE,
    "running header": ("fw", (("type", "header"),)),
    "runningtitlezone": ("fw", (("type", "header"),)),
    "numberingzone": ("fw", (("type", "pageNum"),)),
    "quiremarkszone": ("fw", (("type", "sig"),)),
}

# text annotation taxonomies (lower case) exported as TEI elements, with the components copied as attributes
ANNOTATION_ATTRIBUTES = {
    "unclear": ("reason",),
    "gap": ("reason", "extent", "unit"),
    "add": ("place",),
}
ONE_WORD_ATTRIBUTES = ("unit",)

# characters XML 1.0 does not allow
XML_FORBIDDEN = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


class EphremTEIError(Exception):
    """The export can't go ahead; the message lists every problem, one per line."""

    def __init__(self, problems, intro="The TEI export was stopped. Fix these problems and export again:"):
        self.problems = problems
        super().__init__("\n".join([intro] + ["- " + problem for problem in problems]))


@functools.lru_cache(maxsize=1)
def tei_schema():
    # compiling tei_all.rng takes several seconds, so it is done once per process
    return etree.RelaxNG(etree.parse(TEI_SCHEMA_PATH))


def validate(content):
    """Raise EphremTEIError if content (bytes) is not valid TEI."""
    intro = "The TEI file made by the exporter is not valid TEI. This is a bug in the exporter, please report it:"
    try:
        tree = etree.fromstring(content)
    except etree.XMLSyntaxError as e:
        raise EphremTEIError([f"line {e.lineno}: {e.msg}"], intro=intro)
    schema = tei_schema()
    if not schema.validate(tree):
        raise EphremTEIError([f"line {e.line}: {e.message}" for e in list(schema.error_log)[:5]], intro=intro)


def xml_id(prefix, name, taken):
    """An xml:id for name, made of lower case letters, digits, '.', '_' and '-', unique in taken."""
    base = prefix + re.sub(r"[^a-z0-9._-]", "-", name.lower())
    candidate, number = base, 1
    while candidate in taken:
        number += 1
        candidate = f"{base}-{number}"
    taken.add(candidate)
    return candidate


def type_value(name):
    """A region type name as a TEI @type value: lower case, without spaces."""
    return re.sub(r"\s+", "-", name.strip().lower()) or None


def status_changes(part):
    """
    The status changes of a page, newest first, as (status, user, date) tuples.
    Only the latest change is recorded for now; the history from #19 will replace it.
    """
    if part.editorial_status_by or part.editorial_status_at:
        return [(part.editorial_status, part.editorial_status_by, part.editorial_status_at)]
    return []


class Annotation:
    """A text annotation placed in its region: positions are (line index in the region, offset)."""

    def __init__(self, annotation, name, attributes, start, end):
        self.pk = annotation.pk
        self.name = name
        self.attributes = attributes
        self.start = start
        self.end = end


class EphremTEI:
    """
    The document as the profile needs it. context() checks the data and returns
    the template context, or raises EphremTEIError listing every problem found.
    """

    def __init__(self, document, part_pks, transcription, region_types):
        self.document = document
        self.transcription = transcription
        self.region_types = list(region_types or [])
        self.problems = []
        DocumentPart = apps.get_model("core", "DocumentPart")
        self.parts = list(
            DocumentPart.objects.filter(document=document, pk__in=part_pks)
            .select_related("editorial_status_by")
            .prefetch_related("metadata__key")
            .order_by("order")
        )

    def problem(self, message):
        self.problems.append(message)

    def check_characters(self, text, where):
        match = XML_FORBIDDEN.search(text or "")
        if match:
            self.problem("%s: character U+%04X is not allowed in XML" % (where, ord(match.group())))

    @staticmethod
    def label(part):
        return f"Page {part.order + 1} ({part.filename})"

    @staticmethod
    def page_list(parts):
        return ", ".join(str(part.order + 1) for part in parts)

    @staticmethod
    def metadata_values(items):
        values = {}
        for item in items:
            value = item.value.strip()
            if value:
                values.setdefault(item.key.name.strip().lower(), []).append(value)
        return values

    def single_value(self, values, key, where):
        distinct = list(dict.fromkeys(values.get(key, [])))
        if len(distinct) > 1:
            self.problem(f'{where}: metadata "{key}" has {len(distinct)} different values')
        if distinct:
            self.check_characters(distinct[0], f'{where}: metadata "{key}"')
            return distinct[0]
        return None

    def context(self):
        with override("en"):
            if not self.parts:
                raise EphremTEIError(["Document: there are no pages to export"])
            metadata = self.read_metadata()
            pages = [self.read_page(part, metadata) for part in self.parts]
            self.check_pages(pages)
            if self.problems:
                raise EphremTEIError(self.problems)
            return self.make_context(metadata, pages)

    def read_metadata(self):
        DocumentMetadata = apps.get_model("core", "DocumentMetadata")
        values = self.metadata_values(
            DocumentMetadata.objects.filter(document=self.document).select_related("key")
        )
        metadata = {key: self.single_value(values, key, "Document") for key in DOCUMENT_KEYS}
        for key in REQUIRED_DOCUMENT_KEYS:
            if not metadata[key]:
                self.problem(f'Document: metadata "{key}" is missing')
        for text, where in ((self.document.name, "Document name"),
                            (self.document.project.name, "Project name"),
                            (self.transcription.name, "Transcription layer name")):
            self.check_characters(text, where)
        return metadata

    def read_page(self, part, metadata):
        label = self.label(part)
        values = self.metadata_values(part.metadata.all())
        name = part.name.strip()
        if not name:
            self.problem("%s: no name; set the page Name to the folio, e.g. 23r" % label)
        elif len(name.split()) > 1:
            self.problem('%s: name "%s" contains a space; use the folio alone, e.g. 23r' % (label, name))
        self.check_characters(name, f"{label}: name")
        work = self.single_value(values, "work", label) or metadata["work"]
        if not work:
            self.problem('%s: no work; set page metadata "work" or document metadata "work"' % label)
        page = {
            "part": part,
            "pk": part.pk,
            "name": name,
            "work": work,
            "author": self.single_value(values, "author", label) or metadata["author"],
            "image_name": part.filename,
            "source_url": part.source if part.source.startswith(("http://", "https://")) else None,
        }
        self.read_content(page)
        return page

    def check_pages(self, pages):
        for key, problem in (("name", 'Pages {}: all are named "{}"'),
                             ("image_name", 'Pages {}: all use the image file name "{}"')):
            seen = {}
            for page in pages:
                seen.setdefault(page[key], []).append(page["part"])
            for value, parts in seen.items():
                if value and len(parts) > 1:
                    self.problem(problem.format(self.page_list(parts), value))
        authors = {}
        for page in pages:
            if page["work"]:
                authors.setdefault(page["work"], set()).add(page["author"])
        for work, values in authors.items():
            if len(values) > 1:
                self.problem(f'Work "{work}": pages give different authors, or only some pages give one')

    def read_content(self, page):
        """The page's regions and lines, in export order, and the text annotations on them."""
        part, label = page["part"], self.label(page["part"])
        Line = apps.get_model("core", "Line")
        include_orphans = "Orphan" in self.region_types
        blocks = (
            part.blocks.filter(Block.get_filters(block_types=list(self.region_types), filtering_lines=False))
            .select_related("typology")
            .annotate(avglo=Avg("lines__order"))
            .order_by("avglo")
        )
        lines = list(Line.objects.prefetch_transcription(self.transcription).filter(document_part=part))
        groups = [(block, [line for line in lines if line.block_id == block.pk]) for block in blocks]
        groups = [(block, block_lines) for block, block_lines in groups if block_lines]
        orphans = [line for line in lines if line.block_id is None] if include_orphans else []
        if orphans:
            groups.append((None, orphans))

        page["regions"], page["items"], page["lines"] = [], [], []
        positions = {}  # line pk -> (group index, index in the group)
        number = 0
        for group_index, (block, group_lines) in enumerate(groups):
            line_entries = []
            for index, line in enumerate(group_lines):
                number += 1
                version = line.transcription[0] if line.transcription else None
                text = version.content if version else ""
                self.check_characters(text, f"{label}, line {number}")
                entry = {"line": line, "number": number, "text": text, "version": version}
                line_entries.append(entry)
                page["lines"].append(entry)
                positions[line.pk] = (group_index, index)
            region = {"block": block, "lines": line_entries, "annotations": []}
            if block is not None:
                type_name = block.typology.name.strip() if block.typology else ""
                element, attributes = REGION_ELEMENTS.get(type_name.lower(), ("ab", ()))
                if element == "ab" and type_name:
                    attributes = (("type", type_value(type_name)),)
                region.update(element=element, attributes=list(attributes) + [("facs", f"#zone-r{block.pk}")],
                              type=type_value(type_name) if type_name else None)
                page["regions"].append(region)
            else:
                region.update(element="ab", attributes=[])
            page["items"].append(region)
        page["orphan_lines"] = [entry for entry in page["lines"] if entry["line"].block_id is None]

        self.read_annotations(page, positions)

    def read_annotations(self, page, positions):
        part, label = page["part"], self.label(page["part"])
        TextAnnotation = apps.get_model("core", "TextAnnotation")
        annotations = (
            TextAnnotation.objects.filter(part=part, transcription=self.transcription)
            .select_related("taxonomy")
            .prefetch_related("components__component")
            .order_by("pk")
        )
        for annotation in annotations:
            name = annotation.taxonomy.name.strip().lower()
            if name not in ANNOTATION_ATTRIBUTES:
                continue
            start, end = positions.get(annotation.start_line_id), positions.get(annotation.end_line_id)
            if start is None and end is None:
                continue  # on regions that are not exported
            where = f'{label}, line {self.line_number(page, start or end)}: the "{name}" annotation'
            if start is None or end is None or start[0] != end[0]:
                self.problem(f"{where} runs into another region")
                continue
            region = page["items"][start[0]]
            start = (start[1], annotation.start_offset)
            end = (end[1], annotation.end_offset)
            if (end < start
                    or start[1] > len(region["lines"][start[0]]["text"])
                    or end[1] > len(region["lines"][end[0]]["text"])):
                self.problem(f"{where} does not fit the text of its lines")
                continue
            attributes = []
            values = {value.component.name.strip().lower(): value.value.strip() for value in annotation.components.all()}
            for attribute in ANNOTATION_ATTRIBUTES[name]:
                value = values.get(attribute)
                if value:
                    if attribute in ONE_WORD_ATTRIBUTES and len(value.split()) > 1:
                        self.problem(f'{where}: "{attribute}" must be one word')
                    self.check_characters(value, f'{where}, "{attribute}"')
                    attributes.append((attribute, value))
            if name == "gap" and not values.get("reason"):
                attributes.insert(0, ("reason", "illegible"))
            region["annotations"].append(Annotation(annotation, name, attributes, start, end))

        for region in page["items"]:
            self.check_nesting(page, region)

    @staticmethod
    def line_number(page, position):
        group, index = position
        return page["items"][group]["lines"][index]["number"]

    def check_nesting(self, page, region):
        stack = []
        for annotation in sorted(region["annotations"], key=self.annotation_order):
            while stack and stack[-1].end <= annotation.start:
                stack.pop()
            where = f'{self.label(page["part"])}, line {region["lines"][annotation.start[0]]["number"]}'
            if stack and annotation.end > stack[-1].end:
                self.problem(f'{where}: the "{annotation.name}" and "{stack[-1].name}" annotations overlap')
            elif stack and stack[-1].name == "gap":
                self.problem(f'{where}: the "{annotation.name}" annotation is inside a gap, whose text is not exported')
            stack.append(annotation)

    @staticmethod
    def annotation_order(annotation):
        # outer annotations first
        return (annotation.start, -annotation.end[0], -annotation.end[1], annotation.pk)

    @classmethod
    def events(cls, region):
        """The content of a region for the template: line breaks, text, and the annotations' tags."""
        at = {}  # position -> [(order, sequence, event)]: closing tags, then empty elements, then opening tags
        skipped = []
        for sequence, annotation in enumerate(sorted(region["annotations"], key=cls.annotation_order)):
            if annotation.name == "gap" or annotation.start == annotation.end:
                event = {"kind": "empty", "name": annotation.name, "attributes": annotation.attributes}
                at.setdefault(annotation.start, []).append((1, sequence, event))
                if annotation.name == "gap":
                    skipped.append((annotation.start, annotation.end))
                    at.setdefault(annotation.end, [])  # the text resumes there
            else:
                event = {"kind": "open", "name": annotation.name, "attributes": annotation.attributes}
                at.setdefault(annotation.start, []).append((2, sequence, event))
                at.setdefault(annotation.end, []).append((0, -sequence, {"kind": "close", "name": annotation.name}))

        events = []
        for index, entry in enumerate(region["lines"]):
            line, text = entry["line"], entry["text"]
            events.append({"kind": "lb", "n": entry["number"], "facs": f"zone-l{line.pk}" if line.mask else None})
            cuts = sorted({0, len(text)} | {offset for (i, offset) in at if i == index})
            for k, offset in enumerate(cuts):
                events.extend(event for _, _, event in sorted(at.get((index, offset), []), key=lambda e: e[:2]))
                if k + 1 < len(cuts) and not any(start <= (index, offset) < end for start, end in skipped):
                    events.append({"kind": "text", "text": text[offset:cuts[k + 1]]})
        return events

    def make_context(self, metadata, pages):
        works, msitems = [], {}
        current_work = None
        for page in pages:
            if page["work"] not in msitems:
                msitems[page["work"]] = {"n": len(msitems) + 1, "title": page["work"],
                                         "author": page["author"], "loci": []}
            msitem = msitems[page["work"]]
            if current_work is None or current_work["title"] != page["work"]:
                current_work = {"n": msitem["n"], "title": page["work"], "items": [], "sections": [], "has_text": False}
                works.append(current_work)
                msitem["loci"].append([page["name"], page["name"]])
            msitem["loci"][-1][1] = page["name"]

            def container():
                return current_work["sections"][-1]["items"] if current_work["sections"] else current_work["items"]

            container().append({"kind": "pb", "n": page["name"], "facs": f"surface-{page['pk']}"})
            for region in page["items"]:
                if region["element"] == "head" and current_work["has_text"]:
                    current_work["sections"].append({"n": len(current_work["sections"]) + 1, "items": []})
                if region["element"] == "ab":
                    current_work["has_text"] = True
                container().append({"kind": "region", "element": region["element"],
                                    "attributes": region["attributes"], "events": self.events(region)})

        people, models, changes = self.credits_and_changes(pages)
        current = [page["part"].editorial_status for page in pages]
        statuses = [code for code, label in self.parts[0].EDITORIAL_STATUS_CHOICES] if self.parts else []
        record_id = f"ephrem-doc-{self.document.pk}"
        return {
            "record_id": record_id,
            "title": self.document.name,
            "people": people,
            "models": models,
            "authority": self.document.project.name,
            "date": timezone.localdate().isoformat(),
            "metadata": metadata,
            "msitems": list(msitems.values()),
            "transcription": self.transcription.name,
            "stage": min(current, key=statuses.index) if current else None,
            "changes": changes,
            "pages": pages,
            "works": works,
        }

    def credits_and_changes(self, pages):
        User = apps.get_model("users", "User")
        DocumentPart = apps.get_model("core", "DocumentPart")
        labels = dict(DocumentPart.EDITORIAL_STATUS_CHOICES)
        roles, models = {}, []
        for page in pages:
            for entry in page["lines"]:
                version = entry["version"]
                if version is None:
                    continue
                for source, author in [(version.version_source, version.version_author)] + [
                        (v.get("source"), v.get("author")) for v in version.versions]:
                    source = source or ""
                    if source.startswith("kraken:"):
                        if source[len("kraken:"):] not in models:
                            models.append(source[len("kraken:"):])
                    elif source in (settings.VERSIONING_DEFAULT_SOURCE, "import") and author:
                        roles.setdefault(author, set()).add(TRANSCRIBED)

        dated, undated = [], []
        for page in pages:
            part = page["part"]
            history = status_changes(part)
            for status, user, date in history:
                if user is not None and status in STATUS_ROLES:
                    roles.setdefault(user.username, set()).add(STATUS_ROLES[status])
                change = {"status": status, "user": user, "when": date.isoformat() if date else None,
                          "part": part.pk, "label": f"{page['name']}: {labels.get(status, status)}"}
                (dated if date else undated).append(change)
            if not history:
                status = part.editorial_status
                undated.append({"status": status, "user": None, "when": None, "part": part.pk,
                                "label": f"{page['name']}: {labels.get(status, status)}"})
        dated.sort(key=lambda change: change["when"], reverse=True)

        taken = set()
        names = {user.username: user.get_full_name() for user in User.objects.filter(username__in=roles)}
        people, ids = [], {}
        for username in sorted(roles):
            ids[username] = xml_id("pers-", username, taken)
            people.append({"id": ids[username], "name": names.get(username, username),
                           "roles": [role for role in ROLES if role in roles[username]]})
        for change in dated + undated:
            change["who"] = ids.get(change["user"].username) if change["user"] else None
        for person in people:
            self.check_characters(person["name"], f'User "{person["name"]}"')
        models = [{"id": xml_id("htr-", model, taken), "name": model} for model in models]
        return people, models, dated + undated
