"""
Stage 1 of the "TEI (Ephrem)" export: read what the export needs from eScriptorium into plain data.

This is the only stage that reads the database. The later stages (plan, checks, builder,
validation) only see a Snapshot, so a PAGE XML → TEI converter could reuse them by building a
Snapshot from PAGE files and a metadata table instead.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from django.apps import apps
from django.db.models import Avg, Q
from django.utils import timezone

from core.models import Block

from . import profile


@dataclass
class Region:
    pk: int
    type_name: str  # "" if the region has no type
    polygon: List[List[int]]


@dataclass
class Line:
    pk: int
    region_pk: Optional[int]  # None for a line outside any region
    type_name: str  # "" if the line has no type
    mask: Optional[List[List[int]]]
    baseline: Optional[List[List[int]]]
    text: str
    # who made the current version of the text and the versions in its history, newest first:
    # (source, author), e.g. ("eScriptorium", "jdoe") or ("kraken:model name", "")
    versions: List[Tuple[str, str]] = field(default_factory=list)


@dataclass
class Annotation:
    pk: int
    name: str  # the taxonomy name, lower case
    start_line: int
    start_offset: int
    end_line: int
    end_offset: int
    components: Dict[str, str] = field(default_factory=dict)  # component name (lower case) -> value


@dataclass
class StatusChange:
    status: str
    person: Optional[str]  # username
    when: Optional[datetime]


@dataclass
class Page:
    pk: int
    number: int  # the page's position in the document, from 1
    name: str  # the page Name: the folio
    filename: str
    width: int
    height: int
    source: str  # where the image came from, e.g. a IIIF image URL
    status: str
    changes: List[StatusChange]  # newest first
    metadata: Dict[str, List[str]]  # key (lower case) -> values
    regions: List[Region]  # the exported regions, in reading order
    lines: List[Line]  # the exported lines, in reading order
    annotations: List[Annotation]
    image_path: Optional[str] = None  # the image file, for exports with images


@dataclass
class Person:
    username: str
    user_id: Optional[int]  # None if no eScriptorium user has this name
    name: str


@dataclass
class Snapshot:
    document_name: str
    project_name: str
    transcription_name: str
    read_direction: str  # "ltr" or "rtl"
    metadata: Dict[str, List[str]]  # document metadata: key (lower case) -> values
    pages: List[Page]
    people: Dict[str, Person]  # by username
    # record ids already used by other documents (lower case), among this document's record_id values
    record_ids_in_use: List[str]
    export_date: date


def metadata_values(items):
    """Metadata items (with .key.name and .value) as {key name in lower case: [non-empty values]}."""
    values = {}
    for item in items:
        value = item.value.strip()
        if value:
            values.setdefault(profile.normalize_key_name(item.key.name), []).append(value)
    return values


def status_changes(part):
    """
    The status changes of a page, newest first, as StatusChange.
    Only the latest change is recorded for now; the history from #19 will replace it here.
    """
    if part.editorial_status_by or part.editorial_status_at:
        user = part.editorial_status_by
        return [StatusChange(part.editorial_status, user.username if user else None, part.editorial_status_at)]
    return []


def collect(document, part_pks, transcription, region_types):
    """The Snapshot of the given pages of the document, from the transcription layer."""
    DocumentMetadata = apps.get_model("core", "DocumentMetadata")
    DocumentPart = apps.get_model("core", "DocumentPart")
    Line_ = apps.get_model("core", "Line")
    TextAnnotation = apps.get_model("core", "TextAnnotation")
    User = apps.get_model("users", "User")

    region_types = list(region_types or [])
    include_orphans = "Orphan" in region_types
    metadata = metadata_values(DocumentMetadata.objects.filter(document=document).select_related("key"))

    pages, usernames = [], set()
    parts = (DocumentPart.objects.filter(document=document, pk__in=part_pks)
             .select_related("editorial_status_by").prefetch_related("metadata__key").order_by("order"))
    for part in parts:
        blocks = list(
            part.blocks.filter(Block.get_filters(block_types=list(region_types), filtering_lines=False))
            .select_related("typology")
            .annotate(avglo=Avg("lines__order"))
            .order_by("avglo", "order")
        )
        exported = {block.pk for block in blocks}
        lines = []
        for line in (Line_.objects.prefetch_transcription(transcription).filter(document_part=part)
                     .select_related("typology")):
            if line.block_id in exported or (line.block_id is None and include_orphans):
                version = line.transcription[0] if line.transcription else None
                versions = []
                if version is not None:
                    versions = [(version.version_source or "", version.version_author or "")] + [
                        (v.get("source") or "", v.get("author") or "") for v in version.versions]
                usernames.update(author for _source, author in versions if author)
                lines.append(Line(
                    pk=line.pk, region_pk=line.block_id,
                    type_name=line.typology.name.strip() if line.typology else "",
                    mask=line.mask, baseline=line.baseline,
                    text=version.content if version else "", versions=versions,
                ))
        changes = status_changes(part)
        usernames.update(change.person for change in changes if change.person)
        annotations = [
            Annotation(
                pk=annotation.pk, name=annotation.taxonomy.name.strip().lower(),
                start_line=annotation.start_line_id, start_offset=annotation.start_offset,
                end_line=annotation.end_line_id, end_offset=annotation.end_offset,
                components={value.component.name.strip().lower(): value.value.strip()
                            for value in annotation.components.all()},
            )
            for annotation in (TextAnnotation.objects.filter(part=part, transcription=transcription)
                               .select_related("taxonomy").prefetch_related("components__component")
                               .order_by("pk"))
        ]
        pages.append(Page(
            pk=part.pk, number=part.order + 1, name=part.name.strip(), filename=part.filename,
            width=part.image.width, height=part.image.height, source=part.source or "",
            status=part.editorial_status, changes=changes,
            metadata=metadata_values(part.metadata.all()),
            regions=[Region(block.pk, block.typology.name.strip() if block.typology else "", block.box)
                     for block in blocks],
            lines=lines, annotations=annotations, image_path=part.image.path,
        ))

    people = {
        user.username: Person(user.username, user.pk, user.get_full_name() or user.username)
        for user in User.objects.filter(username__in=usernames)
    }
    for username in usernames - set(people):
        people[username] = Person(username, None, username)

    return Snapshot(
        document_name=document.name,
        project_name=document.project.name,
        transcription_name=transcription.name,
        read_direction=document.read_direction,
        metadata=metadata,
        pages=pages,
        people=people,
        record_ids_in_use=record_ids_in_use(document, metadata),
        export_date=timezone.localdate(),
    )


def record_ids_in_use(document, metadata):
    """This document's record_id values that another document also uses, in lower case."""
    DocumentMetadata = apps.get_model("core", "DocumentMetadata")
    values = [value for name in profile.key_names("record_id") for value in metadata.get(name, [])]
    if not values:
        return []
    names = Q()
    for name in profile.key_names("record_id"):
        names |= Q(key__name__iexact=name)
    same = Q()
    for value in values:
        same |= Q(value__iexact=value)
    used = (DocumentMetadata.objects.filter(names).filter(same).exclude(document=document)
            .values_list("value", flat=True))
    return sorted({value.strip().lower() for value in used})
