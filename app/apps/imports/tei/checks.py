"""
Stage 2 of the "TEI (Ephrem)" export: check a snapshot against the profile and plan the file.

check() reports every problem it finds, as errors (the export stops) or warnings, and returns
the Plan the builder writes: the resolved metadata, the works, the text flow of each page,
the people credited and the status changes. It only reads the snapshot.
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from django.conf import settings

from . import profile
from .layout import Layout, page_label
from .report import FOLIO, METADATA, OTHER, WORK, Report

# characters XML 1.0 does not allow
XML_FORBIDDEN = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


@dataclass(eq=False)
class Work:
    n: int
    title: str
    author: Optional[str]
    uri: Optional[str]
    loci: List[List[str]] = field(default_factory=list)  # [first page name, last page name] of each run

    @property
    def id(self):
        return f"work-{self.n}"


@dataclass
class Credit:
    id: str
    name: str
    roles: List[str]


@dataclass
class Change:
    id: Optional[str]
    status: str
    who: Optional[str]  # a person's id
    when: Optional[str]  # ISO 8601
    page: object  # snapshot.Page
    label: str


@dataclass
class Division:
    """A div type="work": a run of consecutive pages of the same work."""
    work: Work
    layouts: list  # PageLayout


@dataclass
class Plan:
    record_id: str
    uri: Optional[str]
    language: str
    title: str
    authority: str
    transcription: str
    export_date: str
    settlement: Optional[str]
    repository: str
    shelfmark: str
    works: List[Work]
    divisions: List[Division]
    blocks: list
    people: List[Credit]
    models: List[Credit]
    changes: List[Change]
    page_change: Dict[int, str]  # page pk -> the id of its current status change
    stage: str  # the least advanced page status

    @property
    def pages(self):
        return [layout for division in self.divisions for layout in division.layouts]


def xml_id(prefix, name, taken):
    """An xml:id for name, made of lower case letters, digits, '.', '_' and '-', unique in taken."""
    base = prefix + re.sub(r"[^a-z0-9._-]", "-", name.lower())
    candidate, number = base, 1
    while candidate in taken:
        number += 1
        candidate = f"{base}-{number}"
    taken.add(candidate)
    return candidate


class Checker:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.report = Report()

    def characters(self, text, where):
        match = XML_FORBIDDEN.search(text or "")
        if match:
            self.report.error(OTHER, "%s: character U+%04X is not allowed in XML" % (where, ord(match.group())))

    def value(self, values, key, where, category):
        """The value of a metadata key, under its first name that has one; reports conflicting values."""
        for name in profile.key_names(key):
            distinct = list(dict.fromkeys(values.get(name, [])))
            if distinct:
                if len(distinct) > 1:
                    self.report.error(category, f'{where}: metadata "{name}" has {len(distinct)} different values')
                self.characters(distinct[0], f'{where}: metadata "{name}"')
                return distinct[0]
        return None

    def check(self):
        snapshot, report = self.snapshot, self.report
        if not snapshot.pages:
            report.error(OTHER, "Document: there are no pages to export")
            return None, report
        for text, where in ((snapshot.document_name, "Document name"),
                            (snapshot.project_name, "Project name"),
                            (snapshot.transcription_name, "Transcription layer name")):
            self.characters(text, where)

        metadata = {key: self.value(snapshot.metadata, key, "Document", METADATA)
                    for key in ("record_id", "repository", "shelfmark", "settlement", "tei_language")}
        defaults = {key: self.value(snapshot.metadata, key, "Document", WORK) for key in profile.PAGE_KEYS}
        for key in profile.REQUIRED_DOCUMENT_KEYS:
            if not metadata[key]:
                report.error(METADATA, f'Document: metadata "{key}" is missing')
        record_id = self.check_record_id(metadata["record_id"])
        language = self.check_language(metadata["tei_language"])
        uri = None
        if profile.uri_base():
            uri = profile.uri_base() + (record_id or "")
        else:
            report.warning(METADATA, "The record URI (idno type=\"URI\") is not written: "
                                     "the EPHREM_TEI_URI_BASE setting is not set on this instance")

        runs = self.works(defaults)
        self.check_pages()
        layout = Layout(snapshot, report)
        layout_runs = layout.lay_out([pages for _work, pages in runs])
        for layouts in layout_runs:
            for page_layout in layouts:
                for item in page_layout.flow:
                    self.characters(item.line.text, layout.where(page_layout, item))
                for item in page_layout.floats:
                    for line in item.lines:
                        self.characters(line.text, f"{page_label(page_layout.page)}, {layout.FLOAT_NAMES[item.role]}")
        people, models, changes, page_change = self.credits_and_changes()

        if not report.ok:
            return None, report
        works = list(dict.fromkeys(work for work, _pages in runs if work))
        return Plan(
            record_id=record_id,
            uri=uri,
            language=language,
            title=snapshot.document_name,
            authority=snapshot.project_name,
            transcription=snapshot.transcription_name,
            export_date=snapshot.export_date.isoformat(),
            settlement=metadata["settlement"],
            repository=metadata["repository"],
            shelfmark=metadata["shelfmark"],
            works=works,
            divisions=[Division(work, layouts) for (work, _pages), layouts in zip(runs, layout_runs)],
            blocks=layout.blocks,
            people=people,
            models=models,
            changes=changes,
            page_change=page_change,
            stage=min((page.status for page in snapshot.pages), key=profile.STATUS_ORDER.index),
        ), report

    def check_record_id(self, record_id):
        if not record_id:
            return None
        if not profile.RECORD_ID.match(record_id):
            self.report.error(METADATA, 'Document: record_id "%s" may only contain letters, digits, ".", "_" '
                                        'and "-", and must start with a letter or "_"' % record_id)
        elif record_id.lower().startswith(profile.GENERATED_ID_PREFIXES):
            self.report.error(METADATA, 'Document: record_id "%s" starts like the ids the export gives to pages, '
                                        'zones, works, people and statuses; choose another' % record_id)
        if record_id.lower() in self.snapshot.record_ids_in_use:
            self.report.error(METADATA, f'Document: record_id "{record_id}" is already used by another document')
        return record_id

    def check_language(self, value):
        if not value:
            return profile.DEFAULT_LANGUAGE
        tag = profile.approved_language(value)
        if tag is None:
            self.report.error(METADATA, 'Document: tei_language "%s" is not one of the approved tags: %s'
                              % (value, ", ".join(profile.LANGUAGES)))
            return profile.DEFAULT_LANGUAGE
        return tag

    def works(self, defaults):
        """The runs of consecutive pages of the same work, as (Work, [pages]); Work is None for pages without one."""
        works, runs, values = {}, [], {}
        for page in self.snapshot.pages:
            label = page_label(page)
            page_values = {key: self.value(page.metadata, key, label, WORK) for key in profile.PAGE_KEYS}
            page_values["work"] = page_values["work"] or defaults["work"]
            if page_values["work"] == defaults["work"]:
                # the document's author and work URI belong to the document's work
                for key in ("author", "work_uri"):
                    page_values[key] = page_values[key] or defaults[key]
            title = page_values["work"]
            if not title:
                self.report.error(WORK, '%s: no work; set page metadata "work" or document metadata "work"' % label)
                # still laid out, so that the rest of the page is checked too
                if runs and runs[-1][0] is None:
                    runs[-1][1].append(page)
                else:
                    runs.append((None, [page]))
                continue
            if page_values["work_uri"] and not profile.is_web_address(page_values["work_uri"]):
                self.report.error(WORK, '%s: work_uri "%s" is not a web address (http:// or https://, '
                                        'without spaces)' % (label, page_values["work_uri"]))
            for key in ("author", "work_uri"):
                values.setdefault((title, key), set()).add(page_values[key])
            if title not in works:
                works[title] = Work(len(works) + 1, title, page_values["author"], page_values["work_uri"])
            work = works[title]
            if runs and runs[-1][0] is work:
                runs[-1][1].append(page)
                work.loci[-1][1] = page.name
            else:
                runs.append((work, [page]))
                work.loci.append([page.name, page.name])
        for work in works.values():
            for key, what in (("author", "authors"), ("work_uri", "work URIs")):
                if len(values[(work.title, key)]) > 1:
                    self.report.error(WORK, f'Work "{work.title}": pages give different {what}, or only some give one')
            if not work.uri:
                self.report.warning(WORK, 'Work "%s": no work_uri; set it to the work\'s Syriaca.org URI' % work.title)
        return runs

    def check_pages(self):
        pages = self.snapshot.pages
        for page in pages:
            label = page_label(page)
            if not page.name:
                self.report.error(FOLIO, "%s: no name; set the page Name to the folio, e.g. 23r" % label)
            elif len(page.name.split()) > 1:
                self.report.error(FOLIO, '%s: name "%s" contains a space; use the folio alone, e.g. 23r'
                                  % (label, page.name))
            self.characters(page.name, f"{label}: name")
        for key, category, problem in (("name", FOLIO, 'Pages {}: all are named "{}"'),
                                       ("filename", OTHER, 'Pages {}: all use the image file name "{}"')):
            seen = {}
            for page in pages:
                seen.setdefault(getattr(page, key), []).append(page)
            for value, same in seen.items():
                if value and len(same) > 1:
                    self.report.error(category, problem.format(", ".join(str(page.number) for page in same), value))

    def credits_and_changes(self):
        snapshot = self.snapshot
        roles, models = {}, []  # person key -> roles; model names
        for page in snapshot.pages:
            for line in page.lines:
                for source, author in line.versions:
                    if source.startswith("kraken:"):
                        if source[len("kraken:"):] not in models:
                            models.append(source[len("kraken:"):])
                    elif source in (settings.VERSIONING_DEFAULT_SOURCE, "import") and author:
                        roles.setdefault(author, set()).add(profile.TRANSCRIBED)
            for change in page.changes:
                if change.person and change.status in profile.STATUS_ROLES:
                    roles.setdefault(change.person, set()).add(profile.STATUS_ROLES[change.status])

        # people named in document metadata, who may not have an eScriptorium account
        by_name = {}
        for person in snapshot.people.values():
            by_name.setdefault(person.username.lower(), person.username)
            by_name.setdefault(person.name.lower(), person.username)
        named = {}  # name -> roles, for people without an account
        for key, role in profile.CREDIT_KEYS.items():
            for name in profile.key_names(key):
                for value in snapshot.metadata.get(name, []):
                    for person_name in (part.strip() for part in value.split(";")):
                        if not person_name:
                            continue
                        self.characters(person_name, f'Document: metadata "{name}"')
                        username = by_name.get(person_name.lower())
                        if username:
                            roles.setdefault(username, set()).add(role)
                        else:
                            named.setdefault(person_name, set()).add(role)

        taken, ids, people = set(), {}, []
        for username in roles:
            person = snapshot.people[username]
            if person.user_id is not None:
                ids[username] = f"pers-{person.user_id}"
                taken.add(ids[username])
        for username in sorted(roles):
            if username not in ids:
                ids[username] = xml_id("pers-x-", username, taken)
            person = snapshot.people[username]
            self.characters(person.name, f'User "{person.name}"')
            people.append(Credit(ids[username], person.name, [role for role in profile.ROLES if role in roles[username]]))
        for name in sorted(named):
            people.append(Credit(xml_id("pers-x-", name, taken), name,
                                 [role for role in profile.ROLES if role in named[name]]))
        people.sort(key=lambda credit: (credit.name.lower(), credit.id))
        if not people:
            self.report.warning(OTHER, "No one is credited: no line was typed or corrected in eScriptorium, no page "
                                       "status was set by a user, and the document has no transcribed_by, "
                                       "reviewed_by or edited_by metadata")
        models = [Credit(xml_id("htr-", model, taken), model, [profile.MODEL_ROLE]) for model in models]

        dated, undated, page_change = [], [], {}
        for page in snapshot.pages:
            history = page.changes or [None]
            for index, change in enumerate(history):
                change_id = f"status-{page.pk}" if index == 0 else f"status-{page.pk}-{index + 1}"
                if index == 0:
                    page_change[page.pk] = change_id
                status = change.status if change else page.status
                entry = Change(
                    id=change_id, status=status,
                    who=ids.get(change.person) if change and change.person else None,
                    when=change.when.isoformat() if change and change.when else None,
                    page=page, label=f"{page.name}: {profile.STATUS_LABELS.get(status, status)}",
                )
                if entry.when:
                    dated.append((change.when, entry))
                else:
                    undated.append(entry)
        dated.sort(key=lambda item: item[0], reverse=True)
        return people, models, [entry for _when, entry in dated] + undated, page_change


def check(snapshot):
    """(the Plan, or None if there are errors; the Report)"""
    return Checker(snapshot).check()
