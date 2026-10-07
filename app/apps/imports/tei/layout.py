"""
The text flow of the "TEI (Ephrem)" export, part of stage 2 (checks). From the snapshot alone it
works out what each region and line becomes, the columns of each page and the line numbers in
them, the headings, paragraphs and blocks of the text, where margin notes, additions and page
furniture go, and the annotations in the text. See docs/tei/ephrem-tei-profile.md, section 6.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import profile
from .report import ANNOTATIONS, TYPES

# the kinds of block of the text flow
HEAD_BLOCK = "head"
PARAGRAPH_BLOCK = "p"
TEXT_BLOCK = "ab"
UNKNOWN_BLOCK = "unknown"

COLUMN_LETTERS = "abcdefghijklmnopqrstuvwxyz"


@dataclass
class Block:
    index: int
    kind: str
    type_value: Optional[str] = None  # for an unknown type: the original type name, as @type
    opens_section: bool = False


@dataclass
class FlowLine:
    """A line of the text, in the column flow."""
    line: object  # snapshot.Line
    kind: Optional[str]  # profile.MAIN, HEAD or PARAGRAPH; None if its type is unknown
    type_name: str = ""  # the unknown type
    column: Optional[str] = None
    number: int = 0
    block: Optional[int] = None
    events: list = field(default_factory=list)


@dataclass
class Float:
    """A margin note, an addition or page furniture, placed after a line of the text."""
    role: str
    region: Optional[object]  # snapshot.Region, or None for a single line typed as an addition or furniture
    lines: list
    anchor: Optional[int] = None  # the pk of the line it follows; None: at the start of the page
    events: Dict[int, list] = field(default_factory=dict)  # line pk -> inline events


@dataclass
class PageLayout:
    page: object  # snapshot.Page
    columns: List[str]
    flow: List[FlowLine]
    floats: List[Float]

    def floats_after(self, line_pk):
        return [item for item in self.floats if item.anchor == line_pk]

    @property
    def start_floats(self):
        return [item for item in self.floats if item.anchor is None]


# geometry

def bbox(points):
    if not points:
        return None
    xs, ys = [point[0] for point in points], [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def line_box(line):
    return bbox(line.mask) or bbox(line.baseline)


def center_x(box):
    return (box[0] + box[2]) / 2


def center_y(box):
    return (box[1] + box[3]) / 2


def overlap(a0, a1, b0, b1):
    return max(0, min(a1, b1) - max(a0, b0))


def page_label(page):
    return f"Page {page.number} ({page.filename})"


class Layout:
    """Lays out the pages of a snapshot, recording problems in report."""

    def __init__(self, snapshot, report):
        self.snapshot = snapshot
        self.report = report
        self.blocks = []
        self.unknown_types = {}  # (what, type name) -> [page numbers]
        self.non_text = {}  # region type name -> [page numbers]

    # 1. what each line becomes

    def classify(self, page):
        regions = {region.pk: region for region in page.regions}
        flow, floats, region_floats = [], [], {}
        for line in page.lines:
            region = regions.get(line.region_pk)
            region_role = profile.region_role(region.type_name) if region else profile.MAIN
            if region_role == profile.NON_TEXT:
                if line.text.strip():
                    self.non_text.setdefault(region.type_name, []).append(page.number)
                continue
            if region_role in profile.FLOATING_ROLES:
                if region.pk not in region_floats:
                    region_floats[region.pk] = Float(region_role, region, [])
                    floats.append(region_floats[region.pk])
                region_floats[region.pk].lines.append(line)
                continue
            if region_role is None:
                flow.append(FlowLine(line, None, region.type_name))
                self.unknown_types.setdefault(("Region", region.type_name), []).append(page.number)
                continue
            line_role = profile.line_role(line.type_name)
            if line_role is None:
                flow.append(FlowLine(line, None, line.type_name))
                self.unknown_types.setdefault(("Line", line.type_name), []).append(page.number)
            elif line_role in profile.FLOATING_ROLES:
                floats.append(Float(line_role, None, [line]))
            elif region_role == profile.HEAD or line_role == profile.HEAD:
                flow.append(FlowLine(line, profile.HEAD))
            elif line_role == profile.PARAGRAPH:
                flow.append(FlowLine(line, profile.PARAGRAPH))
            else:
                flow.append(FlowLine(line, profile.MAIN))
        return flow, floats

    # 2. columns and line numbers

    def columns(self, page, flow):
        """Number the lines of the flow, by column if the page has several, and return the columns."""
        regions = {region.pk: region for region in page.regions}
        in_flow = {item.line.region_pk for item in flow}
        main = [regions[pk] for pk in in_flow if pk in regions
                and profile.region_role(regions[pk].type_name) == profile.MAIN and bbox(regions[pk].polygon)]
        groups = []  # [x0, x1, region pks]
        for region in sorted(main, key=lambda region: (center_x(bbox(region.polygon)), region.pk)):
            box = bbox(region.polygon)
            for group in groups:
                narrower = min(box[2] - box[0], group[1] - group[0])
                if narrower > 0 and overlap(box[0], box[2], group[0], group[1]) >= narrower / 2:
                    group[0], group[1] = min(group[0], box[0]), max(group[1], box[2])
                    group[2].append(region.pk)
                    break
            else:
                groups.append([box[0], box[2], [region.pk]])

        columns = []
        if len(groups) > 1:
            # in reading order: the rightmost column is the first of a right-to-left manuscript
            groups.sort(key=lambda group: (group[0] + group[1]) / 2, reverse=self.snapshot.read_direction == "rtl")
            columns = list(COLUMN_LETTERS[:len(groups)])
            of_region = {pk: columns[index] for index, group in enumerate(groups) for pk in group[2]}
            for item in flow:
                item.column = of_region.get(item.line.region_pk) or self.nearest_column(item.line, groups, columns)

        numbers = {}
        for item in flow:
            numbers[item.column] = numbers.get(item.column, 0) + 1
            item.number = numbers[item.column]
        return columns

    @staticmethod
    def nearest_column(line, groups, columns):
        box = line_box(line)
        if box is None:
            return columns[0]
        scores = [(overlap(box[0], box[2], group[0], group[1]), -abs(center_x(box) - (group[0] + group[1]) / 2))
                  for group in groups]
        return columns[scores.index(max(scores))]

    # 3. where notes, additions and page furniture go

    @staticmethod
    def anchor(item, flow):
        """The pk of the text line item goes after, or None for the start of the page."""
        candidates = [(index, entry, line_box(entry.line)) for index, entry in enumerate(flow)]
        candidates = [candidate for candidate in candidates if candidate[2]]
        box = bbox(item.region.polygon) if item.region else line_box(item.lines[0])
        if not candidates or box is None:
            return None
        if item.role in profile.FW_TYPES and box[3] <= min(candidate[2][1] for candidate in candidates):
            return None  # running titles and the like, above the text
        y = center_y(box)
        if item.role == profile.ADD:
            # an interlinear addition belongs to the line under it
            below = [candidate for candidate in candidates if center_y(candidate[2]) > y]
            candidates = below or candidates
        index, entry, _box = min(candidates, key=lambda candidate: (abs(center_y(candidate[2]) - y), candidate[0]))
        return entry.line.pk

    # 4. blocks of text, across pages

    def new_block(self, kind, type_value=None, opens_section=False):
        self.blocks.append(Block(len(self.blocks), kind, type_value, opens_section))
        return self.blocks[-1]

    def assign_blocks(self, runs):
        """runs: the pages of each work division, in order. A block never continues into another division."""
        for layouts in runs:
            current = None
            for layout in layouts:
                for item in layout.flow:
                    if item.kind == profile.HEAD:
                        if current is None or current.kind != HEAD_BLOCK:
                            current = self.new_block(HEAD_BLOCK, opens_section=True)
                    elif item.kind is None:
                        type_value = profile.type_value(item.type_name)
                        if current is None or current.kind != UNKNOWN_BLOCK or current.type_value != type_value:
                            current = self.new_block(UNKNOWN_BLOCK, type_value)
                    elif item.kind == profile.PARAGRAPH:
                        current = self.new_block(PARAGRAPH_BLOCK)
                    elif current is None or current.kind not in (PARAGRAPH_BLOCK, TEXT_BLOCK):
                        current = self.new_block(TEXT_BLOCK)
                    item.block = current.index

    # 5. annotations

    def where(self, layout, item):
        """How a message names a line of the flow."""
        column = f"column {item.column}, " if item.column else ""
        return f"{page_label(layout.page)}, {column}line {item.number}"

    FLOAT_NAMES = {
        profile.NOTE_MARGIN: "a margin note",
        profile.NOTE_COMMENTARY: "a commentary note",
        profile.ADD: "an interlinear addition",
        profile.FW_HEADER: "a running title",
        profile.FW_PAGE_NUMBER: "a page number",
        profile.FW_SIGNATURE: "a quire signature",
    }

    def place_annotations(self, layout):
        """Check the page's annotations and turn them into inline events of their lines."""
        page = layout.page
        # the container of each line: a block of the flow, or a float; and the lines of each container
        container, lines_of = {}, {}
        for item in layout.flow:
            key = ("block", item.block)
            container[item.line.pk] = (key, item)
            lines_of.setdefault(key, []).append(item.line)
        for number, item in enumerate(layout.floats):
            key = ("float", number)
            for line in item.lines:
                container[line.pk] = (key, item)
            lines_of[key] = list(item.lines)
        index_in = {line.pk: index for lines in lines_of.values() for index, line in enumerate(lines)}

        placed = {key: [] for key in lines_of}
        for annotation in page.annotations:
            if annotation.name not in profile.ANNOTATION_ATTRIBUTES:
                continue
            start, end = container.get(annotation.start_line), container.get(annotation.end_line)
            if start is None and end is None:
                continue  # on text that is not exported
            first = start or end
            where = self.where(layout, first[1]) if isinstance(first[1], FlowLine) \
                else f"{page_label(page)}, {self.FLOAT_NAMES[first[1].role]}"
            where = f'{where}: the "{annotation.name}" annotation'
            if start is None or end is None:
                self.report.error(ANNOTATIONS, f"{where} runs into text that is not exported")
                continue
            if start[0] != end[0]:
                self.report.error(ANNOTATIONS, f"{where} crosses {self.boundary(start, end)} boundary")
                continue
            lines = lines_of[start[0]]
            start_at = (index_in[annotation.start_line], annotation.start_offset)
            end_at = (index_in[annotation.end_line], annotation.end_offset)
            if (end_at < start_at or start_at[1] > len(lines[start_at[0]].text)
                    or end_at[1] > len(lines[end_at[0]].text)):
                self.report.error(ANNOTATIONS, f"{where} does not fit the text of its lines")
                continue
            attributes = []
            for name in profile.ANNOTATION_ATTRIBUTES[annotation.name]:
                value = annotation.components.get(name)
                if value:
                    if name in profile.ONE_WORD_ATTRIBUTES and len(value.split()) > 1:
                        self.report.error(ANNOTATIONS, f'{where}: "{name}" must be one word')
                    attributes.append((name, value))
            if annotation.name == "gap" and not annotation.components.get("reason"):
                attributes.insert(0, ("reason", "illegible"))
            placed[start[0]].append(Positioned(annotation.pk, annotation.name, attributes, start_at, end_at, where))

        for key, annotations in placed.items():
            self.check_nesting(annotations)
            events = inline_events(lines_of[key], annotations)
            for line, line_events in zip(lines_of[key], events):
                owner = container[line.pk][1]
                if isinstance(owner, FlowLine):
                    owner.events = line_events
                else:
                    owner.events[line.pk] = line_events

    @staticmethod
    def boundary(start, end):
        owners = (start[1], end[1])
        if any(isinstance(owner, Float) for owner in owners):
            return "a note"
        if any(owner.kind == profile.HEAD for owner in owners):
            return "a heading"
        return "a paragraph"

    def check_nesting(self, annotations):
        stack = []
        for annotation in sorted(annotations, key=annotation_order):
            while stack and stack[-1].end <= annotation.start:
                stack.pop()
            if stack and annotation.end > stack[-1].end:
                self.report.error(ANNOTATIONS, f'{annotation.where} overlaps the "{stack[-1].name}" annotation')
            elif stack and stack[-1].name == "gap":
                self.report.error(ANNOTATIONS, f"{annotation.where} is inside a gap, whose text is not exported")
            stack.append(annotation)

    # all of it

    def lay_out(self, runs):
        """runs: the pages of each work division, as lists of snapshot pages. Returns the same, as PageLayouts."""
        layout_runs = []
        for pages in runs:
            layouts = []
            for page in pages:
                flow, floats = self.classify(page)
                columns = self.columns(page, flow)
                for item in floats:
                    item.anchor = self.anchor(item, flow)
                layouts.append(PageLayout(page, columns, flow, floats))
            layout_runs.append(layouts)
        self.assign_blocks(layout_runs)
        for layouts in layout_runs:
            for layout in layouts:
                self.place_annotations(layout)

        for (what, type_name), numbers in sorted(self.unknown_types.items()):
            self.report.warning(TYPES, '%s type "%s" is not in the Ephrem profile: its text is exported as '
                                       '<ab type="%s"> (pages %s)'
                                % (what, type_name, profile.type_value(type_name), page_list(numbers)))
        for type_name, numbers in sorted(self.non_text.items()):
            self.report.warning(TYPES, 'Region type "%s" holds no text in the Ephrem profile: the text of its '
                                       'lines is not exported (pages %s)' % (type_name, page_list(numbers)))
        return layout_runs


def page_list(numbers):
    return ", ".join(str(number) for number in sorted(set(numbers)))


@dataclass
class Positioned:
    """An annotation placed in its container: positions are (index of the line in the container, offset)."""
    pk: int
    name: str
    attributes: list
    start: tuple
    end: tuple
    where: str


def annotation_order(annotation):
    # outer annotations first
    return (annotation.start, -annotation.end[0], -annotation.end[1], annotation.pk)


def inline_events(lines, annotations):
    """
    The content of each of lines, as events: ("text", text), ("open", name, attributes),
    ("close", name) and ("empty", name, attributes). Annotations must be well nested.
    """
    at = {}  # position -> [(order, sequence, event)]: closing tags, then empty elements, then opening tags
    skipped = []
    for sequence, annotation in enumerate(sorted(annotations, key=annotation_order)):
        if annotation.name == "gap" or annotation.start == annotation.end:
            at.setdefault(annotation.start, []).append((1, sequence, ("empty", annotation.name, annotation.attributes)))
            if annotation.name == "gap":
                skipped.append((annotation.start, annotation.end))
                at.setdefault(annotation.end, [])  # the text resumes there
        else:
            at.setdefault(annotation.start, []).append((2, sequence, ("open", annotation.name, annotation.attributes)))
            at.setdefault(annotation.end, []).append((0, -sequence, ("close", annotation.name)))

    events = []
    for index, line in enumerate(lines):
        text, line_events = line.text, []
        cuts = sorted({0, len(text)} | {offset for (i, offset) in at if i == index})
        for k, offset in enumerate(cuts):
            line_events.extend(event for _, _, event in sorted(at.get((index, offset), []), key=lambda e: e[:2]))
            if k + 1 < len(cuts) and not any(start <= (index, offset) < end for start, end in skipped):
                if cuts[k + 1] > offset:
                    line_events.append(("text", text[offset:cuts[k + 1]]))
        events.append(line_events)
    return events
