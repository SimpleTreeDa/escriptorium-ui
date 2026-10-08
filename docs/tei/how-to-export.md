# How to export TEI for the Ephrem Project

The "TEI (Ephrem)" export writes one TEI file per document, following the [Ephrem TEI profile](ephrem-tei-profile.md).
This page covers what to prepare, how to check the document, how to export, and what to do if the export stops.

## 1. Add the Ephrem ontology to the document

The export recognises some region types, line types and annotation taxonomies ([section 4](#4-mark-headings-paragraphs-notes-and-additions)).
Add them to the document once, in either way:

- **On the server** (an administrator): `python manage.py apply_ephrem_ontology <document id> ...`, or `--project <project slug>` for every document of a project.
  Running it again changes nothing.
- **In Transcriptus:** in the document's ontology page, import [`ephrem-ontology.json`](ephrem-ontology.json).

## 2. Fill in the document metadata

In the document's settings. Keys are matched ignoring case: `Shelfmark` and `shelfmark` are the same key.

| Key | Required | Example | Also recognised as |
|---|---|---|---|
| `record_id` | **Yes** | `sachau-176` | `record id` |
| `repository` | **Yes** | `Staatsbibliothek zu Berlin` | `holding institution`, `institution`, `library` |
| `shelfmark` | **Yes** | `Sachau 176` | `shelf mark`, `call number`, `classmark` |
| `work` | **Yes**, unless every page has its own | `Memra for Holy Thursday` | |
| `work_uri` | Recommended | `http://syriaca.org/work/1505` | `work uri` |
| `settlement` | No | `Berlin` | `location`, `city` |
| `author` | No | `Narsai` | |
| `tei_language` | No (default `syr`) | `syr-Syre` | |
| `transcribed_by`, `reviewed_by`, `edited_by` | No | `Sebastian Brock; Jane Doe` | `transcribed by`, … |

- **`record_id`** is the record's persistent identifier, assigned by the project. It must start with a letter and contain only letters, digits, `.`, `_` and `-`, and no two documents may share it.
- When a key appears under several of its names, the first name in the table wins: an editor's `shelfmark` counts before a `Call number` copied from a IIIF manifest.
- **`tei_language`** is only needed for a script variant: `syr-Syre` (Estrangela), `syr-Syrj` (vocalised West Syriac), `syr-Syrn` (vocalised East Syriac) or `syr-x-syrm` (Melkite). The document's script setting is never used for this.
- **`transcribed_by`, `reviewed_by`, `edited_by`** credit people who did not work in Transcriptus. Separate several names with `;`. People who typed or corrected lines, or set page statuses, are credited automatically.

## 3. Name the pages and set their works

On the **Images page**, select the pages, then use the **TEI** menu of the selection toolbar:

- **Number folios…** names the selected pages by folio, in page order, from the first folio you give: `1r` gives `1r`, `1v`, `2r`, `2v`… The page **Name** is the folio in the TEI: one word, unique in the document.
- **Set work…** gives the selected pages a `work`, when they belong to a different work than the document's. Leave it empty to remove it.
- **Set work URI…** gives them the work's Syriaca.org URI.

One page at a time, the same can be done in the page details in the editor.
Pages imported from a IIIF manifest are already named after their canvas labels, such as `f. 1r`; number them again to get one-word folios.

## 4. Mark headings, paragraphs, notes and additions

The segmentation models give only the main text. Mark the rest in the editor's segmentation panel by giving regions and lines one of these types:

| Type | Becomes in the TEI |
|---|---|
| Region *MainZone* (or *MainZone:left*, *MainZone:right*), *Main*, no type, or a line outside any region | the text. Two main regions side by side are two columns. |
| Line *HeadingLine*, or region *Title* | a heading, which starts a new section of the work |
| Line *ParagraphStart* | the first line of a paragraph. Without any, the text is kept in neutral blocks: the export never guesses paragraphs. |
| Region *MarginTextZone* | a margin note, placed after the text line level with it |
| Region *Commentary* | a commentary note, placed the same way |
| Line *InterlinearLine* or *Correction* | an addition above the line, placed after the text line under it |
| Region *RunningTitleZone*, *NumberingZone*, *QuireMarksZone*; lines *Numbering*, *Signature* | a running title, a page number, a quire signature |
| Region *Illustration*, *GraphicZone*, *DecorationZone* | a picture: its outline only, no text |

A region or line of any other type is still exported, as a block of its own, and the readiness check warns about it.

**Uncertain, illegible and added text** are text annotations, with the taxonomies of the ontology:

| Taxonomy | Components | Use it for |
|---|---|---|
| `unclear` | `reason` | Text you can read but are unsure of. Annotate the text. |
| `gap` | `reason`, `extent`, `unit` | Text you can't read. Type a placeholder such as `…` and annotate the placeholder: it becomes a gap. |
| `add` | `place` | Text the scribe added, typed where it belongs, e.g. `place` = `above`. |

An annotation may run over several lines, but not out of a heading, a note or a paragraph, and two annotations can't partly overlap.

**Statuses.** Set each page's editorial status as the work progresses. The export records each page's status, and the least advanced one becomes the status of the file.

## 5. Check the document

In the export dialog, choose the format **TEI (Ephrem)**, the transcription layer and the region types, then click **Check TEI readiness**.
It runs all the export's checks without exporting, and shows whether the document is ready, how many problems each kind has (metadata, works, folios, annotations, region and line types, the TEI file), and the first messages.
Problems stop the export; warnings don't.

On the Images page, the check covers the selected images; on the document page, the whole document.

## 6. Export

1. Open the document's export, from the document page or with images selected on the Images page.
2. Choose the format **TEI (Ephrem)** and the transcription layer. Leave all region types selected, including *Orphan lines*, unless you mean to leave some out.
3. Tick **Include images** if you want the page images in the download.

You get the TEI file as a `.xml` file or, when you asked for the images, a `.zip` with the TEI file (`<record_id>.xml`) and the images.
The file has been validated against TEI P5 (`tei_all.rng`), and its internal links and the eleven required items have been checked.
TEI editors such as Oxygen validate it again when you open it.

## 7. If the export stops

The export checks the whole document first, and stops if anything the profile requires is missing.
The notification links to a report that lists **every** problem, one per line, for example:

```
The TEI export was stopped. Fix these problems and export again:
- Document: metadata "record_id" is missing
- Page 12 (MS1_f023r.jpg): name "f. 23r" contains a space; use the folio alone, e.g. 23r
- Page 12 (MS1_f023r.jpg), column b, line 7: the "unclear" annotation crosses a note boundary
```

Fix them all, then export again; **Check TEI readiness** shows the same problems without exporting.
Page numbers count from 1 in the order of the Images page. Line numbers count the lines of the text from 1 on each page, and in each column of the page.

A report that says *"The TEI file made by the exporter is not valid"* is a bug in the exporter, not a problem with your document. Please report it, with the report's text.

## For administrators

- **`EPHREM_TEI_URI_BASE`** (environment variable): the start of each record's URI. The file's `idno type="URI"` is this followed by the `record_id`, e.g. `https://example.org/records/` gives `https://example.org/records/sachau-176`. Without it, the URI is not written, and the readiness check says so.
- **`apply_ephrem_ontology`**: see [section 1](#1-add-the-ephrem-ontology-to-the-document).
