# How to export TEI for the Ephrem Project

The "TEI (Ephrem)" export writes one TEI file per document, following the [Ephrem TEI profile](ephrem-tei-profile.md).
This page covers what to prepare, how to export, and what to do if the export stops.

## 1. Prepare the document

You do this once per document, then keep it up to date as the work goes on.

**Document metadata** (document settings):

| Key | Required | Example |
|---|---|---|
| `repository` | Yes | `Staatsbibliothek zu Berlin` |
| `shelfmark` | Yes | `Sachau 176` |
| `work` | Yes, unless every page has its own | `Memra for Holy Thursday` |
| `settlement` | No | `Berlin` |
| `author` | No | `Narsai` |

**Pages** (page details):

- Set each page's **Name** to its folio, as one word: `179r`, `179v`. Names must be unique in the document.
- If a page belongs to a different work than the document's `work`, give the page its own `work` (and `author`) metadata.

**Regions.** These region types have a special meaning in the export:

| Region type | Becomes |
|---|---|
| *Title*, *Heading* or *Rubric* | a heading |
| *Margin*, *Marginalia* or *MarginTextZone* | a margin note |
| *Running Header* | a running title |
| *NumberingZone* | a page number |
| *QuireMarksZone* | a quire mark |

Every other region becomes a block of text.
A heading after some text starts a new section of the work.

**Uncertain, illegible and added text.** Create text annotation taxonomies with these exact names:

| Taxonomy | Components it can have | Use it for |
|---|---|---|
| `unclear` | `reason` | Text you can read but are unsure of. Annotate the text. |
| `gap` | `reason`, `extent`, `unit` | Text you can't read. Type a placeholder such as `…` and annotate the placeholder: it is replaced by a gap in the TEI. |
| `add` | `place` | Text the scribe added, e.g. above the line (`place` = `above`). |

An annotation must stay within one region, and two annotations can't partly overlap.

**Statuses.** Set each page's editorial status as the work progresses. The export records each page's status, and the least advanced one becomes the status of the file.

## 2. Export

1. Open the document's export.
2. Choose the format **TEI (Ephrem)**.
3. Choose the pages and the transcription layer. Leave all region types selected, including *Orphan lines*, unless you mean to leave some out.
4. Tick **Include images** if you want the page images in the download.

Until the new export dialog offers the format ([#28](https://github.com/SimpleTreeDa/escriptorium-ui/issues/28)), use the API instead: `POST /api/documents/{pk}/export/` with `file_format=ephremtei`.

You get a zip file that contains `ephrem-doc-{pk}.xml` and, if you asked for them, the images.
The TEI file has already been validated against TEI P5 (`tei_all.rng`).
TEI editors such as Oxygen validate it again automatically when you open it.

## 3. If the export stops

The export checks the whole document first, and stops if anything the profile requires is missing.
The notification links to a report that lists **every** problem, one per line, for example:

```
The TEI export was stopped. Fix these problems and export again:
- Document: metadata "shelfmark" is missing
- Page 12 (MS1_f023r.jpg): name "f. 23r" contains a space; use the folio alone, e.g. 23r
- Page 12 (MS1_f023r.jpg), line 7: the "unclear" annotation runs into another region
```

Fix them all, then export again.
Page numbers count from 1 in the order of the Images page, and line numbers count the page's lines in export order.

A report that says *"The TEI file made by the exporter is not valid TEI"* is a bug in the exporter, not a problem with your document. Please report it, with the report's text.
