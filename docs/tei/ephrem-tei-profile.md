# Ephrem TEI profile

**Version:** 1.0, for review ([#12](https://github.com/SimpleTreeDa/escriptorium-ui/issues/12)).
**Requirements:** the project brief *Syriac Project TEI File Requirements*, and its eleven items of required information.
**Used by:** the "TEI (Ephrem)" exporter, format key `ephremtei` ([#50](https://github.com/SimpleTreeDa/escriptorium-ui/issues/50), [#13](https://github.com/SimpleTreeDa/escriptorium-ui/issues/13)). Editors: see [How to export TEI](how-to-export.md).

This document defines the TEI that eScriptorium exports for the Ephrem Project website.
It is a profile of standard TEI P5, not a new schema: the files are validated against the official `tei_all` schema, and this document fixes which parts of TEI we use and how eScriptorium data fills them.

## Contents

1. [Version 1 decisions](#1-version-1-decisions)
2. [How the export is built](#2-how-the-export-is-built)
3. [The file at a glance](#3-the-file-at-a-glance)
4. [Required information: mapping table](#4-required-information-mapping-table)
5. [Header](#5-header)
6. [Text](#6-text)
7. [Facsimile and image links](#7-facsimile-and-image-links)
8. [Metadata editors must fill in](#8-metadata-editors-must-fill-in)
9. [Checks before export](#9-checks-before-export)
10. [Validation](#10-validation)
11. [Canonical sample](#11-canonical-sample)
12. [Relation to the Digital Syriac Corpus](#12-relation-to-the-digital-syriac-corpus)
13. [Not in version 1](#13-not-in-version-1)

## 1. Version 1 decisions

| Question | Version 1 |
|---|---|
| Sources | **Manuscripts only.** Printed editions are out of scope. |
| Export unit | **One TEI file per eScriptorium document**, not one per work. |
| Pages | **All pages** chosen in the export dialog, whatever their status. |
| Record identifier | **`ephrem-doc-{pk}`**, from the eScriptorium document id. |
| Folio label | **The page Name** in eScriptorium. There is no separate folio metadata key. |
| Licence and publisher wording | **Deferred** until the website's requirements are known. |
| Schema | **Official TEI P5 `tei_all.rng`, unchanged.** This profile defines the subset and conventions. |
| Validation | **RelaxNG**, plus the exporter's own checks and tests. No Schematron. |
| Image links | **Percent-encoded file names** that match the image files in the export exactly. |

## 2. How the export is built

The brief plans this workflow: eScriptorium → PAGE XML export → converter adds project metadata → minimal TEI generation → TEI validation → downloadable TEI file.

We build the same pipeline **without the intermediate PAGE XML file**.
A native exporter, made like the PAGE and ALTO exporters in `app/apps/imports/export.py`, reads the transcription and the project metadata straight from the database, writes TEI from a Django template, validates it, and offers it for download.
There are two reasons:

- PAGE XML doesn't carry the document and page metadata, the line authorship or the status history. A converter would have to read the database anyway.
- The other exporters already provide the export flow, error reporting and tests; a converter would duplicate them.

**The download is a zip**, like the other XML exports.
It contains `ephrem-doc-{pk}.xml` and, when "include images" is ticked, the page images.
The exporter writes one file per document. PAGE and ALTO write one file per page, so it can't reuse `XMLTemplateExporter.render()` unchanged.

## 3. The file at a glance

A shortened example with illustrative values. `…` stands for repeated content.
The real, complete example is the [canonical sample](#11-canonical-sample).

```xml
<?xml version="1.0" encoding="UTF-8"?>
<?xml-model href="https://www.tei-c.org/Vault/P5/4.12.0/xml/tei/custom/schema/relaxng/tei_all.rng" type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0" xml:id="ephrem-doc-123" xml:lang="en">
  <teiHeader>
    <fileDesc>
      <titleStmt>
        <title>Example Library, MS 1, ff. 23r–23v</title>
        <respStmt>
          <resp>Syriac text transcribed by</resp>
          <resp>Reviewed by</resp>
          <persName xml:id="pers-jdoe">Jane Doe</persName>
        </respStmt>
        <respStmt>
          <resp>Automatic text recognition by</resp>
          <name type="software" xml:id="htr-syrestr-02-34">kraken model SyrEstr_02_34</name>
        </respStmt>
      </titleStmt>
      <publicationStmt>
        <authority>Ephrem Project</authority>
        <idno type="ephrem">ephrem-doc-123</idno>
        <date when="2026-10-07"/>
      </publicationStmt>
      <sourceDesc>
        <msDesc>
          <msIdentifier>
            <settlement>Example City</settlement>
            <repository>Example Library</repository>
            <idno type="shelfmark">MS 1</idno>
          </msIdentifier>
          <msContents>
            <msItem xml:id="work-1" n="1">
              <locus from="23r" to="23v"/>
              <title>Hymns on Faith</title>
            </msItem>
          </msContents>
        </msDesc>
      </sourceDesc>
    </fileDesc>
    <encodingDesc>
      <editorialDecl>
        <p>Diplomatic transcription made in eScriptorium, from the transcription layer "manual". …</p>
      </editorialDecl>
    </encodingDesc>
    <profileDesc>
      <langUsage>
        <language ident="en">English</language>
        <language ident="syr">Syriac</language>
      </langUsage>
    </profileDesc>
    <revisionDesc status="transcribed">
      <change when="2026-10-03T14:12:09+00:00" who="#pers-jdoe" status="reviewed_1" target="#surface-901">23r: Reviewed by Editor 1</change>
      <change when="2026-10-02T09:30:00+00:00" who="#pers-jdoe" status="transcribed" target="#surface-902">23v: Initial transcription complete</change>
    </revisionDesc>
  </teiHeader>
  <facsimile>
    <surface xml:id="surface-901" n="23r" ulx="0" uly="0" lrx="2480" lry="3508">
      <graphic url="MS1%20f023r.jpg" width="2480px" height="3508px"/>
      <zone xml:id="zone-r4408" type="numberingzone" points="2200,120 2300,120 2300,180 2200,180">
        <zone xml:id="zone-l88117" type="line" points="2205,125 2295,125 2295,175 2205,175"/>
      </zone>
      <zone xml:id="zone-r4409" type="title" points="210,250 2270,250 2270,320 210,320">
        <zone xml:id="zone-l88118" type="line" points="215,255 2260,255 2260,315 215,315"/>
      </zone>
      <zone xml:id="zone-r4410" type="main" points="210,330 2270,330 2270,3190 210,3190">
        <zone xml:id="zone-l88119" type="line" points="215,340 2260,338 2262,402 217,405"/>
        <zone xml:id="zone-l88120" type="line" points="215,410 2260,408 2262,470 217,472"/>
      </zone>
      <zone xml:id="zone-r4411" type="margintextzone" points="2300,900 2450,900 2450,1100 2300,1100">
        <zone xml:id="zone-l88121" type="line" points="2305,905 2445,905 2445,960 2305,960"/>
      </zone>
    </surface>
    <surface xml:id="surface-902" n="23v" ulx="0" uly="0" lrx="2480" lry="3508">
      <graphic url="MS1%20f023v.jpg" width="2480px" height="3508px"/>
      …
    </surface>
  </facsimile>
  <text xml:lang="syr" type="ManuscriptTranscription">
    <body>
      <div type="work" n="1" corresp="#work-1">
        <pb n="23r" facs="#surface-901"/>
        <fw type="pageNum" facs="#zone-r4408"><lb n="1" facs="#zone-l88117"/>ܟܓ</fw>
        <head facs="#zone-r4409"><lb n="2" facs="#zone-l88118"/>ܡܕܪܫܐ</head>
        <ab type="main" facs="#zone-r4410">
          <lb n="3" facs="#zone-l88119"/>ܗܝܡܢܘܬܐ <unclear reason="faded">ܕܐܠܗܐ</unclear> …
          <lb n="4" facs="#zone-l88120"/>… <gap reason="illegible"/> … <add place="above">ܘ</add>…
        </ab>
        <note place="margin" facs="#zone-r4411"><lb n="5" facs="#zone-l88121"/>ܥܘܢܝܬܐ</note>
        <pb n="23v" facs="#surface-902"/>
        <div type="section" n="1">
          <head><lb n="1"/>…</head>
          <ab type="main"><lb n="2"/>…</ab>
        </div>
      </div>
    </body>
  </text>
</TEI>
```

## 4. Required information: mapping table

One row for each of the brief's eleven required items.
"Required data" means the exporter refuses to export without it ([section 9](#9-checks-before-export)).

| # | Brief item | TEI | eScriptorium source | Required data |
|---|---|---|---|---|
| 1 | Stable record ID | `TEI/@xml:id`, `publicationStmt/idno[@type="ephrem"]` | Document id: `ephrem-doc-{pk}` | — |
| 2 | Manuscript identification | `msDesc/msIdentifier`: `settlement`, `repository`, `idno[@type="shelfmark"]` | Document metadata `settlement`, `repository`, `shelfmark` | `repository`, `shelfmark` |
| 3 | Work / text identification, and its relationship to the manuscript | `msContents/msItem` (work `title` and optional `author`, with `locus` giving where it is in the manuscript); `div[@type="work"]/@corresp` pointing to the `msItem` | Page metadata `work` and `author`, with the document's values as defaults | `work` |
| 4 | Language declaration | `profileDesc/langUsage/language[@ident="syr"]`; `text/@xml:lang="syr"` | Fixed | — |
| 5 | Responsibility | `titleStmt/respStmt` | Line edit history; page status changes | — |
| 6 | Revision / review status | `revisionDesc/@status` (current stage); `revisionDesc/change` (history) | Page editorial statuses and their history | — |
| 7 | Textual divisions | `div[@type="work"]`, `div[@type="section"]`, `head`, `ab`, `note`, `fw` | `work` metadata; region types | — |
| 8 | Folio / page breaks | `pb/@n`, `pb/@facs` | Page Name; page order | Page Name |
| 9 | Transcription lines | `lb/@n`, `lb/@facs`, then the line text | Lines of the chosen transcription layer | — |
| 10 | Image links | `facsimile/surface/graphic/@url`; `zone` for regions and lines | Image file name and size; region and line polygons | — |
| 11 | Uncertain or illegible readings | `unclear`, `gap` (and `add` for additions) | Text annotations whose taxonomy is named `unclear`, `gap` or `add` | — |

## 5. Header

### 5.1 Record identifier

`TEI/@xml:id` and `publicationStmt/idno[@type="ephrem"]` are both `ephrem-doc-{pk}`, where `{pk}` is the eScriptorium document id.
The file is `ephrem-doc-{pk}.xml`.

The id is created with the document and never changes, so every export of a document has the same identifier, and editors enter nothing.
It changes only if the document is deleted and imported again.

The exporter builds the identifier in one place.
A website-assigned identifier or URI can be added later as another `idno` (e.g. `idno type="URI"`), without changing the rest of the file.

Other ids in the file:

| Thing | id |
|---|---|
| Page (`surface`) | `surface-{part pk}` |
| Region (`zone`) | `zone-r{block pk}` |
| Line (`zone`) | `zone-l{line pk}` |
| Work (`msItem`) | `work-{n}`, numbered in order of first appearance |
| Person (`persName`) | `pers-{username}` |
| HTR model (`name`) | `htr-{model name}` |

Usernames and model names are made safe for XML ids: lower case, with every character other than letters, digits, `.`, `_` and `-` replaced by `-`.
If two names end up the same, the second gets a number added.
We use database ids rather than region and line `external_id`, because imported `external_id` values repeat across pages.

### 5.2 Title

One `titleStmt/title`, the document name.

### 5.3 Responsibility

`titleStmt` has one `respStmt` per person: one `resp` for each role they had, then one `persName` with an `xml:id`.
`change/@who` points to that id.
The name is the user's full name, or their username if no full name is set. Email addresses are never exported.

| `resp` | Who |
|---|---|
| Syriac text transcribed by | Authors of any version of an exported line (current or in its history) whose source is `eScriptorium` (typed in the editor) or `import`; users who set a page to *In progress* or *Initial transcription complete* |
| Reviewed by | Users who set a page to *Reviewed by Editor 1* or *Reviewed by Editor 2* |
| Edited by | Users who set a page to *Ground truth*, *Final edited copy* or *Ready for TEI export* |

Line versions come from `LineTranscription.version_author` and `version_source`, and from the `versions` history (the last 20 edits of each line).
The history matters because a reviewer who corrects a line becomes its current author, which would otherwise hide who first transcribed it.

**Automatic text recognition.** A version whose source is `kraken:{model name}` was produced by a model.
Each model gets its own `respStmt`, with `resp` *Automatic text recognition by* and `name type="software"`.
The user who ran the model is not credited for those versions.

### 5.4 Publication

```xml
<publicationStmt>
  <authority>{eScriptorium project name}</authority>
  <idno type="ephrem">ephrem-doc-{pk}</idno>
  <date when="{export date, YYYY-MM-DD}"/>
</publicationStmt>
```

TEI requires a responsible body before an `idno`. Until the website's wording is agreed, `authority` is the name of the eScriptorium project that holds the document.
Version 1 has no licence (`availability`).

### 5.5 Manuscript and works

```xml
<sourceDesc>
  <msDesc>
    <msIdentifier>
      <settlement>{settlement}</settlement>            <!-- only if set -->
      <repository>{repository}</repository>
      <idno type="shelfmark">{shelfmark}</idno>
    </msIdentifier>
    <msContents>
      <msItem xml:id="work-{n}" n="{n}">                <!-- one per distinct work -->
        <locus from="{first page}" to="{last page}"/>   <!-- one per run of pages -->
        <author>{author}</author>                       <!-- only if set -->
        <title>{work}</title>
      </msItem>
    </msContents>
  </msDesc>
</sourceDesc>
```

`msContents` lists the works on the **exported** pages, not every work in the manuscript.
This is where the brief's "relationship between the manuscript witness and the work" is recorded. Each work appears once here, with the folios where the manuscript has it, and the text's `div`s point back to it.

### 5.6 Encoding

`encodingDesc/editorialDecl` is one fixed paragraph that names the transcription layer:
*"Diplomatic transcription made in eScriptorium, from the transcription layer "{name}". One lb element per manuscript line and one pb element per page. Line text is as entered: not normalised and not punctuated."*

### 5.7 Language

| | Value |
|---|---|
| `TEI/@xml:lang` | `en`: the header is in English |
| `profileDesc/langUsage` | `<language ident="en">English</language>` and `<language ident="syr">Syriac</language>` |
| `text/@xml:lang` | `syr` |

### 5.8 Revision and review status

The brief's status vocabulary is the one eScriptorium uses for pages, so its codes are used unchanged:

| Code | Label |
|---|---|
| `not_started` | Not started |
| `in_progress` | In progress |
| `transcribed` | Initial transcription complete |
| `reviewed_1` | Reviewed by Editor 1 |
| `reviewed_2` | Reviewed by Editor 2 |
| `ground_truth` | Ground truth |
| `final` | Final edited copy |
| `ready_for_tei` | Ready for TEI export |

```xml
<revisionDesc status="{current stage}">
  <change when="{changed_at}" who="#pers-{username}" status="{new status code}"
          target="#surface-{part pk}">{page name}: {label}</change>
  …
</revisionDesc>
```

- **Current stage:** `revisionDesc/@status` is the status of the **least advanced** exported page, in the order of the table. One page still *In progress* means the file is `in_progress`.
- **History:** one `change` for each status change of an exported page, **newest first**.
  - `@status` is the page's new status.
  - `@target` points to the page's `surface`.
  - `@when` is an ISO 8601 date-time with a `T` and a time zone, as Django's `date:"c"` writes it. Python's default `str()` (`2026-10-03 14:12:09+00:00`) is invalid TEI.
- **Source:** the status history from [#19](https://github.com/SimpleTreeDa/escriptorium-ui/issues/19) (`to_status`, `changed_by`, `changed_at`).
  Until #19 is merged, each page gives one `change` from `editorial_status`, `editorial_status_by` and `editorial_status_at`. That is the row #19's data migration creates, so the output keeps the same shape when #19 lands.
- **Every exported page appears at least once.** A page with no recorded change gets one `change` with its current status and no `@when` or `@who`, e.g. `<change status="in_progress" target="#surface-717">179r: In progress</change>`. This happens when the status was set before who-and-when was recorded, as on every page of the project's instance in October 2026.
  This rule also keeps the file valid: TEI does not allow an empty `revisionDesc`.

## 6. Text

```xml
<text xml:lang="syr" type="ManuscriptTranscription">
  <body>
    <div type="work" n="{n}" corresp="#work-{n}">
      <pb n="{page name}" facs="#surface-{part pk}"/>
      …regions, in reading order…
      <div type="section" n="{n}">
        <head>…</head>
        …regions…
      </div>
    </div>
  </body>
</text>
```

`text/@type="ManuscriptTranscription"` is the Digital Syriac Corpus's type for transcriptions made from a manuscript.

### 6.1 Works

Each run of consecutive exported pages with the same `work` value becomes one `div type="work"`.
Its `@n` and `@corresp` point to the work's `msItem`.
A page without its own `work` value uses the document's `work` value.

Works come from page metadata, not region types. Region types describe layout, which looks the same in every work. Which work a page belongs to is an editorial fact that editors can set in the page details without re-segmenting.

**Limitation:** a work that begins in the middle of a page can't be marked; the page belongs to one work.

### 6.2 Pages

One `pb` per exported page, in page order, before the page's regions.
`pb/@n` is the page Name (e.g. `95r`), and `pb/@facs` points to the page's `surface`.
A page with no lines still gets its `pb`.

### 6.3 Regions: headings, blocks, marginalia, page furniture

Each region with at least one line becomes one element, in the region order eScriptorium uses for PAGE and ALTO exports (by the average order of its lines).
The element depends on the region type's name, ignoring case:

| Region type | TEI |
|---|---|
| `Title`, `Heading`, `Rubric` | `head`: see sections below |
| `Margin`, `Marginalia`, `MarginTextZone` | `note place="margin"` |
| `Running Header`, `RunningTitleZone` | `fw type="header"` |
| `NumberingZone` | `fw type="pageNum"` |
| `QuireMarksZone` | `fw type="sig"` |
| any other type (`Main`, `MainZone`, `Commentary`, …), or no type | `ab`, with `@type` = the type name in lower case with spaces replaced by `-`; no `@type` if the region has none |

- Every one of these elements gets `@facs` pointing to the region's zone.
- Lines outside any region go in one untyped `ab` after the page's regions.
- Regions without lines (e.g. *Illustration*) are not exported.
- The region types ticked in the export dialog decide which regions are exported, as for the other formats.
- **Paragraphs:** a text region becomes an `ab`, TEI's neutral block, not a `p`. Regions are layout blocks: one paragraph of the text can run across columns and pages, so calling a region a paragraph would usually be wrong.
- The type list covers eScriptorium's default types, the SegmOnto zones used by segmentation models, and the types the project's documents use as of October 2026:
  - *Running Header* becomes `fw`.
  - *Left Column*, *Middle Column*, *Right Column*, *MainLeft* and *MainRight* become `ab`, each with its type.
  - *Footnotes* and *Foreign* are only used in printed editions, which are out of scope.

**Sections and headings.** TEI only allows `head` at the start of a division, so:

- A heading region that comes before any other text of its work becomes the work's `head`.
- A heading region anywhere else starts a new `div type="section"`, numbered from 1 within the work, with the heading as its `head`. The section runs until the next heading region or the end of the work.
- `pb`, `fw` and `note` can sit anywhere, including before a `head`.

### 6.4 Lines

- Each line is an empty `lb` followed by the line's text, inside its region's element.
- `lb/@n` counts the page's lines from 1, in export order. `lb/@facs` points to the line's zone.
- Lines with no text are still exported, as `lb` alone, so line numbers match the image.
- The text comes from the transcription layer chosen in the export dialog.

### 6.5 Uncertain, illegible and added text

Text annotations become TEI elements when their taxonomy's name, ignoring case, is one of these:

| Taxonomy | TEI | The annotated characters | Attributes, from the annotation's components |
|---|---|---|---|
| `unclear` | `<unclear>…</unclear>` | Kept, inside the element | `reason`, e.g. `faded` |
| `gap` | `<gap/>` | Dropped: they are a placeholder | `reason` (default `illegible`), `extent`, `unit` |
| `add` | `<add>…</add>` | Kept, inside the element | `place`, e.g. `above`, `below`, `margin` |

- **Gap convention:** type a placeholder for the illegible text (e.g. `…`) and annotate the placeholder with the `gap` taxonomy.
- A component's value is copied only if the taxonomy has that component and the annotation gives it a value.
- Only annotations on the exported transcription layer are used. Annotations with other taxonomies are not exported.
- An annotation may run across lines in the same region.
- The exporter refuses an annotation that runs into another region, and two annotations that overlap without one containing the other ([section 9](#9-checks-before-export)).

### 6.6 Characters

- Line text is exported exactly as stored. eScriptorium stores it in Unicode NFC ([#70](https://github.com/SimpleTreeDa/escriptorium-ui/pull/70)), and the exporter normalises nothing further.
  "Not normalised" in the `editorialDecl` means no editorial normalisation of spelling, vocalisation or punctuation.
- Right-to-left marks and zero-width characters are kept.
- `&`, `<` and `>` are escaped. Text is never read as markup.
- Characters that XML 1.0 forbids (control characters other than tab and newline) are reported as errors, because the file would be unreadable.

## 7. Facsimile and image links

`facsimile` comes between `teiHeader` and `text`, with one `surface` per exported page.

```xml
<surface xml:id="surface-{part pk}" n="{page name}" ulx="0" uly="0" lrx="{image width}" lry="{image height}">
  <graphic url="{percent-encoded image file name}" width="{width}px" height="{height}px"/>
  <graphic type="source" url="{source URL}"/>   <!-- only for pages imported from a web address (IIIF) -->
  <zone xml:id="zone-r{block pk}" type="{region type}" points="x,y x,y …">
    <zone xml:id="zone-l{line pk}" type="line" points="x,y x,y …"/>
  </zone>
</surface>
```

**The image link** (`graphic/@url`):

- It is the name of the page's image file in the export (`DocumentPart.filename`: the original file name, or the stored one if there is none), relative to the TEI file. With "include images" ticked, the zip contains that file next to the TEI file.
- The exporter works out this name **once per page**. It uses the same string as the zip entry name in `zip.write()` and, percent-encoded, as `graphic/@url`. The link and the file can't drift apart.
- **Percent-encoding** is Django's `urlencode` filter in the template (Python's `quote()`): `MS1 f023r.jpg` becomes `MS1%20f023r.jpg`. Decoding the URL gives back the exact file name, including Syriac and accented names.
- Encoding is needed for correctness, not just for validation:
  - A space, `%`, `(` or `[` makes the file invalid TEI.
  - `#` and `?` are valid but change the meaning: `f#23r.jpg` would be read as the file `f` with a fragment `23r.jpg`.
- Two exported pages with the same image file name are an error ([section 9](#9-checks-before-export)); both would point to the same file.

**The source link:** pages imported from a IIIF manifest also get `graphic type="source"` with the URL eScriptorium downloaded the image from (`DocumentPart.source`).
It is written only when `source` starts with `http://` or `https://`; PDF and zip imports store values like `pdf//…` and `zip//…`.
It is already a URL, so it is written as it is, without encoding it again.

**Zones:**

- Coordinates are pixels of the image stored in eScriptorium.
- Region zones use the region polygon; line zones use the line mask and sit inside their region's zone.
- Lines outside any region sit directly in the `surface`.
- A line without a mask has no zone and no `lb/@facs`. Baselines are not exported.
- Zones hold no text.

## 8. Metadata editors must fill in

| What | Where | Required | Example |
|---|---|---|---|
| `repository` | Document metadata | **Yes** | `Staatsbibliothek zu Berlin` |
| `shelfmark` | Document metadata | **Yes** | `Sachau 176` |
| `work` | Page metadata, or Document metadata as the default for every page | **Yes**, for every page directly or through the default | `Memra for Holy Thursday` |
| Page **Name** | Page details ("Name") | **Yes**, for every page: the folio, as one word, unique in the document | `179r` |
| `settlement` | Document metadata | No, written if present | `Berlin` |
| `author` | Page metadata, or Document metadata as the default, like `work` | No, written if present | `Narsai` |

- Metadata keys are lower case and spelled exactly as above. Values are free text.
- `author` belongs to the work: every page with the same `work` must have the same `author`, or none.
- Nothing else is needed. The title is the document name, and the transcription layer, statuses and credits come from eScriptorium.

## 9. Checks before export

The exporter checks the data before it writes anything.
It collects **every** problem and fails once, with one plain-language message per problem:

- `Document: metadata "repository" is missing`
- `Document: metadata "shelfmark" has two different values`
- `Page 12 (MS1_f023r.jpg): no name; set the page Name to the folio, e.g. 23r`
- `Page 12 (MS1_f023r.jpg): name "f. 23r" contains a space; use the folio alone, e.g. 23r`
- `Pages 12 and 15: both are named "23r"`
- `Page 12 (MS1_f023r.jpg): no work; set page metadata "work" or document metadata "work"`
- `Work "Memra for Holy Thursday": pages give two different authors`
- `Pages 12 and 15: both use the image file name "scan.jpg"`
- `Page 12, line 7: the "unclear" annotation runs into another region`
- `Page 12, line 7: two annotations overlap`
- `Page 12, line 7: character U+0007 is not allowed in XML`

A work whose pages have no text is not an error. TEI allows a `div` that holds only `pb`s.

After rendering, the exporter validates the file ([section 10](#10-validation)) and reports the first few errors with their line numbers.

## 10. Validation

### 10.1 Schema

**`tei_all.rng` from TEI P5 4.12.0**, committed unchanged at `app/escriptorium/static/tei_all.rng`, next to `alto-4-1-baselines.xsd`.

- **Source:** the TEI Vault, which keeps every release at a fixed address: <https://www.tei-c.org/Vault/P5/4.12.0/xml/tei/custom/schema/relaxng/tei_all.rng>.
- **Licence:** TEI publishes it under CC BY and BSD-2.
- **Declared in every file** with the `<?xml-model?>` line shown in [section 3](#3-the-file-at-a-glance), so TEI editors such as Oxygen validate exports automatically.
- **No custom schema:** everything this profile adds is either a fixed value the template writes or a data check the exporter runs, and neither needs a schema. A project ODD would only pay off if people wrote Ephrem TEI by hand.
- **Syriaca.org's schema doesn't fit:** it removes `surface` and `zone`.

### 10.2 What checks what

| Check | Done by |
|---|---|
| Well-formed XML; `xml:id` values are valid names and unique | XML parser |
| Element order and nesting; required elements and attributes; value formats (URIs, date-times, `px` sizes, zone `points`, no spaces in `@type`) | RelaxNG validation with `lxml` |
| Required metadata present; page names present, one word, unique; work values; image file names unique; annotations well nested; XML-safe characters | Exporter checks ([section 9](#9-checks-before-export)) |
| Every `#…` link (`@facs`, `@who`, `@target`, `@corresp`) points to an `xml:id` in the file | Tests |
| Profile conventions (e.g. `revisionDesc/@status` is a known code, every `pb` points to a `surface`, zones hold no text) | Tests |

**RelaxNG with `lxml`** (lxml 6.1.0 and libxml2 2.14.6, as in the eScriptorium image):

- Compiling the schema takes 8–10 seconds, so the exporter compiles it once per worker process, not once per export.
- Validating a file takes milliseconds.

**No Schematron in version 1.** `tei_all.rng` also embeds TEI's Schematron rules (98 rules in 93 patterns). We don't run them:

- Only two apply to the elements this profile uses, and the exporter guarantees both:
  - `msIdentifier` must contain a `repository`, which is required metadata.
  - Facsimile zones must not contain text, and the template never writes any.
- None of them checks that `#…` links point to existing ids, so running them wouldn't close that gap. The tests do.
- They need XPath 2, which `lxml` can't run, so running them would mean adding Saxon.

## 11. Canonical sample

**Files** (next to the expected outputs of the other exporters' tests):

- `app/apps/imports/tests/samples/ephrem_tei_sample.xml`: the canonical sample, from real data.
- `app/apps/imports/tests/samples/ephrem_tei_features.xml`: a synthetic document that uses every construct in the profile.

**Test:** `app/apps/imports/tests/test_tei_profile.py`.

- It validates both files against `tei_all.rng`.
- It checks the profile rules RelaxNG can't: every `#…` link resolves, page names, line numbering, zones, image URLs, and the current stage.
- It checks that those rule checks catch broken files.
- It needs no database.
- The exporter's tests (#13) can run the same `profile_errors()` on real export output.

**Source: Sachau 176, ff. 179r–179v** (eScriptorium document 15, "Sachau 176 - Training Data"), from the transcription layer `kraken:syr_41transcribathon_docs_d_3`, which is where the corrections were made. The `manual` layer is empty.

**The work** is Narsai's *Memra for Holy Thursday*. The Berlin catalogue places it at ff. 175v–182v of Sachau 176 (Staatsbibliothek zu Berlin, catalogue no. 57), and ff. 179r–179v fall inside that range.

**Why not Vat. sir. 111.** It was the first choice: dated about 522, one of the earliest witnesses to Ephrem, written in three columns.
In October 2026 it is not usable on the project's instance:

- f. 94v is segmented but has no text in any layer.
- ff. 95r and 95v are not segmented.
- None of its 11 pages has any transcription.

No other Ephrem manuscript on the instance is transcribed either.

**Why Sachau 176.** It is the only manuscript on the instance with real, hand-corrected transcription:

- f. 179r has 27 lines, all corrected by hand after automatic recognition.
- f. 179v has 28 lines: the first 2 are corrected and the other 26 are still automatic recognition output.

That mixture is realistic, and it exercises both kinds of credit (*transcribed by*, and *automatic text recognition by*).

**What it exercises:**

- A single-column West Syriac verse manuscript.
- Two pages, two surfaces and two page breaks.
- A *Main* region on each page, and on f. 179v one line outside any region.
- Line zones from real masks.
- Image file names with spaces (`Sachau 176 - 179r.tif` → `Sachau%20176%20-%20179r.tif`).
- Page statuses with no recorded who or when.
- Responsibility drawn from real edit history.

**What it doesn't exercise** (the instance has no data for these): headings and sections, margin notes, page furniture, columns, and `unclear`/`gap`/`add`, because the document has no annotation taxonomies.
`ephrem_tei_features.xml` covers them.

**Values not yet in eScriptorium.** The document has no metadata and its pages have no names.
The sample uses the values editors will enter: page names `179r` and `179v`, and document metadata `repository`, `shelfmark`, `settlement` and `work`.
Until they are entered, an export of this document will stop with the errors in [section 9](#9-checks-before-export).

## 12. Relation to the Digital Syriac Corpus

The brief asks for a model informed by the [Digital Syriac Corpus](https://github.com/srophe/syriac-corpus) but not copied from it, and more manuscript-centred.

**Taken from the Corpus**

- `msIdentifier` with `settlement`, `repository` and `idno type="shelfmark"`.
- Fixed `resp` wording ("Syriac text transcribed by").
- `change` with `@when` and `@who`, newest first.
- `text/@type="ManuscriptTranscription"`.
- `TEI/@xml:lang="en"`, with Syriac tagged as plain `syr` (no script subtags).
- `pb/@n` as the folio.
- Sections as `div type="section"` with a `head`.

**Not taken**

- The Corpus's project boilerplate (sponsors, editorial board, distributor, series title, copyright notes).
- Empty placeholder elements.
- One `respStmt` per role: we use one per person, so `change/@who` can point to a single id.
- `biblStruct` sources.
- Literal `[…]` for lacunae.
- The Syriaca.org schema.

**New, because the Corpus has no precedent:**

- `facsimile`, `surface` and `zone` with `@facs` links.
- `lb` for manuscript lines.
- `unclear`, `gap` and `add`.
- Margin notes and page furniture (`note`, `fw`).
- Responsibility and status taken from eScriptorium's edit history and page statuses.

## 13. Not in version 1

**Deferred by decision**

- Licence and publisher wording.
- A website identifier or URI.
- Exporting only pages that are *Ready for TEI export*.
- Printed editions.

**The brief's "can be added later" list**

- Deletions and corrections.
- Abbreviations and expansions.
- Supplied or reconstructed text.
- Quotations.
- Named entities.
- A richer manuscript description.

**Also not in version 1**

- Links to Syriaca.org work and manuscript records.
- Script names (Estrangela, Serto, East Syriac).
- Date of composition.
- Line types (e.g. SegmOnto `HeadingLine`); headings are recognised by region type only.
- Columns (`cb`): columns are separate regions.
- Words broken across lines (`lb break="no"`).
- Hands.
- Baselines.
- Glyph positions and recognition confidence.
- Schematron validation.
