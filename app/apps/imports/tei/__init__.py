"""
The "TEI (Ephrem)" export (docs/tei/ephrem-tei-profile.md), in five stages:

1. snapshot.collect(): read the document into a Snapshot. The only stage that reads the database.
2. checks.check(): check the snapshot against the profile and plan the file, reporting every problem.
3. builder.build(): write the TEI file with lxml.
4. validation: tei_all.rng, the internal links, and the brief's eleven required items.
5. imports.export.EphremTEIExporter: write the .xml file, or a .zip with the images.

check_document() runs stages 1 to 4 without writing anything: the "Check TEI readiness" report.
It skips the RelaxNG validation unless asked: compiling tei_all.rng takes about 10 seconds and 70 MB
per process, and with the data checks passed, a schema error can only be a bug in the exporter.
A PAGE XML → TEI converter would replace stage 1 and reuse the others.
"""
from dataclasses import dataclass

from lxml import etree

from . import builder, checks, snapshot, validation
from .report import LINKS, EphremTEIError, Report

__all__ = ["EphremTEIError", "Result", "check_document", "export_document", "file_errors"]

BUG = "The TEI file made by the exporter is not valid. This is a bug in the exporter, please report it:"


@dataclass
class Result:
    content: bytes
    plan: checks.Plan
    snapshot: snapshot.Snapshot
    report: Report


def file_errors(content, schema=True):
    """Stage 4: what is wrong with a TEI file (bytes), as messages; empty if nothing is."""
    try:
        tree = validation.parse(content)
    except etree.XMLSyntaxError as e:
        return [f"line {e.lineno}: {e.msg}"]
    errors = validation.schema_errors(tree) if schema else []
    return errors + validation.link_errors(tree) + validation.requirement_errors(tree)


def export_document(document, part_pks, transcription, region_types):
    """
    The TEI file of the given pages of the document, from the transcription layer, as a Result.
    Raises EphremTEIError, listing every problem, if the document lacks data the profile requires.
    """
    collected = snapshot.collect(document, part_pks, transcription, region_types)
    plan, report = checks.check(collected)
    if plan is None:
        raise EphremTEIError([problem.message for problem in report.errors])
    content = builder.build(plan)
    errors = file_errors(content)
    if errors:
        raise EphremTEIError(errors, intro=BUG)
    return Result(content, plan, collected, report)


def check_document(document, part_pks, transcription, region_types, schema=False):
    """What the export of these pages would find, as a dict for the readiness report. Writes no file."""
    collected = snapshot.collect(document, part_pks, transcription, region_types)
    plan, report = checks.check(collected)
    if plan is not None:
        for message in file_errors(builder.build(plan), schema=schema):
            report.error(LINKS, message)
    result = report.as_dict()
    result["pages"] = len(collected.pages)
    result["record_id"] = plan.record_id if plan else None
    return result
