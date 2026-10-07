"""
The problems the "TEI (Ephrem)" export finds, as errors (the export stops) and warnings
(the export goes ahead), each in a category the readiness check reports on.
"""
from dataclasses import dataclass

METADATA = "metadata"        # document metadata: record id, manuscript, language, credits
WORK = "work"                # page and document work, work URI, author
FOLIO = "folio"              # page names
ANNOTATIONS = "annotations"  # unclear, gap and add
TYPES = "types"              # region and line types the profile doesn't know
LINKS = "links"              # the generated file: schema, internal links, required content
OTHER = "other"
CATEGORIES = (METADATA, WORK, FOLIO, ANNOTATIONS, TYPES, LINKS, OTHER)


@dataclass
class Problem:
    category: str
    message: str


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, category, message):
        self.errors.append(Problem(category, message))

    def warning(self, category, message):
        self.warnings.append(Problem(category, message))

    @property
    def ok(self):
        return not self.errors

    def as_dict(self):
        def problems(items):
            return [{"category": problem.category, "message": problem.message} for problem in items]

        return {
            "ready": self.ok,
            "errors": problems(self.errors),
            "warnings": problems(self.warnings),
            "summary": {category: {"errors": sum(p.category == category for p in self.errors),
                                   "warnings": sum(p.category == category for p in self.warnings)}
                        for category in CATEGORIES},
        }


class EphremTEIError(Exception):
    """The export can't go ahead; the message lists every problem, one per line."""

    def __init__(self, problems, intro="The TEI export was stopped. Fix these problems and export again:"):
        self.problems = problems
        super().__init__("\n".join([intro] + ["- " + problem for problem in problems]))
