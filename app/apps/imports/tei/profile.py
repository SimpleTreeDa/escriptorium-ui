"""
The Ephrem TEI profile (docs/tei/ephrem-tei-profile.md) as data: the metadata keys, the status
vocabulary, the approved language tags, the map from eScriptorium region and line types to TEI,
and the Ephrem ontology. Nothing here reads the database.
"""
import os
import re

from django.conf import settings

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"

# the schema every file is validated against: TEI P5 4.12.0 tei_all, committed unchanged
TEI_SCHEMA_URL = "https://www.tei-c.org/Vault/P5/4.12.0/xml/tei/custom/schema/relaxng/tei_all.rng"


def schema_path():
    return getattr(settings, "EPHREM_TEI_SCHEMA_PATH", "") or os.path.join(settings.PROJECT_ROOT, "static", "tei_all.rng")


def uri_base():
    """The start of every record's URI (idno type="URI"); the record id is appended to it."""
    return getattr(settings, "EPHREM_TEI_URI_BASE", "")


# The brief's editorial status vocabulary, from the least to the most advanced.
# It is the vocabulary of DocumentPart.EDITORIAL_STATUS_CHOICES.
STATUSES = (
    ("not_started", "Not started"),
    ("in_progress", "In progress"),
    ("transcribed", "Initial transcription complete"),
    ("reviewed_1", "Reviewed by Editor 1"),
    ("reviewed_2", "Reviewed by Editor 2"),
    ("ground_truth", "Ground truth"),
    ("final", "Final edited copy"),
    ("ready_for_tei", "Ready for TEI export"),
)
STATUS_ORDER = [code for code, label in STATUSES]
STATUS_LABELS = dict(STATUSES)

# responsibility, in the wording of the Digital Syriac Corpus
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
# document metadata naming people who did not work in eScriptorium, and the role it gives them
CREDIT_KEYS = {
    "transcribed_by": TRANSCRIBED,
    "reviewed_by": REVIEWED,
    "edited_by": EDITED,
}
MODEL_ROLE = "Automatic text recognition by"

# Metadata keys, each with the names it is recognised by, in order of preference.
# Names are compared ignoring case and surrounding spaces; the first name that has a value wins,
# so an editor's "shelfmark" takes precedence over a "Call number" copied from a IIIF manifest.
METADATA_KEYS = {
    "record_id": ("record_id", "record id"),
    "repository": ("repository", "holding institution", "institution", "library"),
    "shelfmark": ("shelfmark", "shelf mark", "shelf-mark", "call number", "classmark"),
    "settlement": ("settlement", "location", "city"),
    "work": ("work",),
    "work_uri": ("work_uri", "work uri"),
    "author": ("author",),
    "tei_language": ("tei_language",),
    "transcribed_by": ("transcribed_by", "transcribed by"),
    "reviewed_by": ("reviewed_by", "reviewed by"),
    "edited_by": ("edited_by", "edited by"),
}
REQUIRED_DOCUMENT_KEYS = ("record_id", "repository", "shelfmark")
# page metadata, each with the document's value as the default for every page
PAGE_KEYS = ("work", "work_uri", "author")
# the keys the Images page can set on several pages at once
BULK_PAGE_KEYS = ("work", "work_uri")


def key_names(key):
    """The lower-case names a profile key is recognised by."""
    return METADATA_KEYS.get(key, (key,))


def normalize_key_name(name):
    return re.sub(r"\s+", " ", (name or "").strip().lower())


WEB_ADDRESS = re.compile(r"^https?://\S+$")


def is_web_address(value):
    """True for an http(s) URL without spaces, such as a Syriaca.org work URI."""
    return bool(WEB_ADDRESS.match(value or ""))


# The page Name is the folio: a number and r (recto) or v (verso), e.g. 23r.
FOLIO = re.compile(r"^\s*(\d+)\s*([rv])\s*$", re.IGNORECASE)


def folio_sequence(start, count):
    """
    count folios from start, recto then verso: folio_sequence("1r", 4) is 1r, 1v, 2r, 2v.
    Raises ValueError if start is not a folio.
    """
    match = FOLIO.match(start or "")
    if not match or int(match.group(1)) < 1:
        raise ValueError(start)
    number, side = int(match.group(1)), match.group(2).lower()
    folios = []
    for _ in range(count):
        folios.append(f"{number}{side}")
        if side == "v":
            number += 1
        side = "v" if side == "r" else "r"
    return folios


# A record id becomes TEI/@xml:id, the end of the record's URI and the file name.
RECORD_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9._-]*$")
# prefixes of the other ids in the file, which a record id must not start with
GENERATED_ID_PREFIXES = ("surface-", "zone-", "work-", "pers-", "htr-", "status-")

# The language of the text: plain "syr" unless the document's "tei_language" metadata says otherwise.
# These are Syriaca.org's codes: script subtags are an editorial choice
# (Syrj and Syrn are for vocalised text), never derived from eScriptorium's script setting.
DEFAULT_LANGUAGE = "syr"
LANGUAGES = {
    "syr": "Syriac",
    "syr-Syre": "Syriac in Estrangela script",
    "syr-Syrj": "Syriac in vocalised West Syriac script",
    "syr-Syrn": "Syriac in vocalised East Syriac script",
    "syr-x-syrm": "Syriac in Melkite script",
}


def approved_language(value):
    """The approved language tag that value spells, ignoring case, or None."""
    for tag in LANGUAGES:
        if tag.lower() == (value or "").strip().lower():
            return tag
    return None


# What region and line types become. Type names are compared ignoring case, and without a
# SegmOnto subtype or number: "MainZone:left" and "MainZone#2" are both MainZone.
MAIN = "main"                        # the text, in the column flow
HEAD = "head"                        # a heading: opens a div type="section"
PARAGRAPH = "paragraph"              # a main-text line that starts a p
NOTE_MARGIN = "note-margin"          # note place="margin", after the nearest text line
NOTE_COMMENTARY = "note-commentary"  # note type="commentary", after the nearest text line
ADD = "add"                          # add place="above", after the text line below it
FW_HEADER = "fw-header"              # fw type="header"
FW_PAGE_NUMBER = "fw-pageNum"        # fw type="pageNum"
FW_SIGNATURE = "fw-sig"              # fw type="sig"
NON_TEXT = "non-text"                # a facsimile zone only, no text

FW_TYPES = {FW_HEADER: "header", FW_PAGE_NUMBER: "pageNum", FW_SIGNATURE: "sig"}
NOTE_ROLES = (NOTE_MARGIN, NOTE_COMMENTARY)
FLOATING_ROLES = NOTE_ROLES + (ADD,) + tuple(FW_TYPES)

REGION_ROLES = {
    # SegmOnto and eScriptorium's default types
    "mainzone": MAIN,
    "main": MAIN,
    "title": HEAD,
    "margintextzone": NOTE_MARGIN,
    "commentary": NOTE_COMMENTARY,
    "runningtitlezone": FW_HEADER,
    "numberingzone": FW_PAGE_NUMBER,
    "quiremarkszone": FW_SIGNATURE,
    "illustration": NON_TEXT,
    "graphiczone": NON_TEXT,
    "decorationzone": NON_TEXT,
    # other names already in use on the project's instance
    "heading": HEAD,
    "rubric": HEAD,
    "margin": NOTE_MARGIN,
    "marginalia": NOTE_MARGIN,
    "running header": FW_HEADER,
    "left column": MAIN,
    "middle column": MAIN,
    "right column": MAIN,
    "mainleft": MAIN,
    "mainright": MAIN,
}
LINE_ROLES = {
    "defaultline": MAIN,
    "main": MAIN,
    "headingline": HEAD,
    "paragraphstart": PARAGRAPH,
    "interlinearline": ADD,
    "correction": ADD,
    "numbering": FW_PAGE_NUMBER,
    "signature": FW_SIGNATURE,
}


def type_key(name):
    """A type name without its SegmOnto subtype or number, in lower case."""
    return re.split(r"[:#]", name or "", maxsplit=1)[0].strip().lower()


def region_role(type_name):
    """The role of a region of this type: MAIN for untyped regions, None if the type is unknown."""
    if not (type_name or "").strip():
        return MAIN
    return REGION_ROLES.get(type_key(type_name))


def line_role(type_name):
    """The role of a line of this type: MAIN for untyped lines, None if the type is unknown."""
    if not (type_name or "").strip():
        return MAIN
    return LINE_ROLES.get(type_key(type_name))


def type_value(name):
    """A type name as a TEI @type value: lower case, without spaces."""
    return re.sub(r"\s+", "-", (name or "").strip().lower()) or None


# Text annotation taxonomies (names compared ignoring case) exported as TEI elements,
# with the annotation components copied as attributes.
ANNOTATION_ATTRIBUTES = {
    "unclear": ("reason",),
    "gap": ("reason", "extent", "unit"),
    "add": ("place",),
}
# TEI allows one value only in these
ONE_WORD_ATTRIBUTES = ("unit",)

# The Ephrem ontology: the region types, line types and annotation taxonomies the profile maps.
# Apply it with `python manage.py apply_ephrem_ontology`, or import docs/tei/ephrem-ontology.json
# in a document's ontology page. It uses the format of the ontology export (version 1).
ONTOLOGY = {
    "version": 1,
    "region_types": [
        "MainZone", "MainZone:left", "MainZone:right", "Main",
        "Title",
        "MarginTextZone", "Commentary",
        "RunningTitleZone", "NumberingZone", "QuireMarksZone",
        "Illustration", "GraphicZone", "DecorationZone",
    ],
    "line_types": [
        "DefaultLine", "Main",
        "HeadingLine", "ParagraphStart",
        "InterlinearLine", "Correction",
        "Numbering", "Signature",
    ],
    "part_types": [],
    "annotation_components": [
        {"name": "reason", "allowed_values": None},
        {"name": "extent", "allowed_values": None},
        {"name": "unit", "allowed_values": None},
        {"name": "place", "allowed_values": ["above", "below", "margin", "inline", "top", "bottom"]},
    ],
    "taxonomy": [
        {"name": "unclear", "typology": "TEI", "has_comments": False, "abbreviation": "UNC",
         "marker_type": 3, "marker_color": "#f2c94c", "components": ["reason"]},
        {"name": "gap", "typology": "TEI", "has_comments": False, "abbreviation": "GAP",
         "marker_type": 3, "marker_color": "#eb5757", "components": ["reason", "extent", "unit"]},
        {"name": "add", "typology": "TEI", "has_comments": False, "abbreviation": "ADD",
         "marker_type": 3, "marker_color": "#6fcf97", "components": ["place"]},
    ],
}
