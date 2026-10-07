# Ephrem TEI profile

**Version:** 1.1, for review ([#12](https://github.com/SimpleTreeDa/escriptorium-ui/issues/12)). What changed from 1.0 is in [section 14](#14-changes-from-version-10).
**Requirements:** the project brief *Syriac Project TEI File Requirements*, and its eleven items of required information.
**Used by:** the "TEI (Ephrem)" exporter, format key `ephremtei` ([#50](https://github.com/SimpleTreeDa/escriptorium-ui/issues/50), [#13](https://github.com/SimpleTreeDa/escriptorium-ui/issues/13), [#28](https://github.com/SimpleTreeDa/escriptorium-ui/issues/28)). Editors: see [How to export TEI](how-to-export.md).

This document defines the TEI that eScriptorium exports for the Ephrem Project website.
It is a profile of standard TEI P5, not a new schema: the files are validated against the official `tei_all` schema, and this document fixes which parts of TEI we use and how eScriptorium data fills them.

## Contents

1. [Version 1.1 decisions](#1-version-11-decisions)
2. [How the export is built](#2-how-the-export-is-built)
3. [The file at a glance](#3-the-file-at-a-glance)
4. [Required information: mapping table](#4-required-information-mapping-table)
5. [Header](#5-header)
6. [Text](#6-text)
7. [Facsimile and image links](#7-facsimile-and-image-links)
8. [What editors fill in](#8-what-editors-fill-in)
9. [Checks before export, and the readiness check](#9-checks-before-export-and-the-readiness-check)
10. [Validation](#10-validation)
11. [Reference files](#11-reference-files)
12. [Relation to the Digital Syriac Corpus](#12-relation-to-the-digital-syriac-corpus)
13. [Not in version 1.1](#13-not-in-version-11)
14. [Changes from version 1.0](#14-changes-from-version-10)

## 1. Version 1.1 decisions

| Question | Version 1.1 |
|---|---|
| Sources | **Manuscripts only.** Printed editions are out of scope. |
| Export unit | **One TEI file per eScriptorium document**, not one per work. |
| Pages | **All pages** chosen in the export dialog, whatever their status. |
| Record identifier | **The document's `record_id` metadata**, assigned by the project, unique across documents. |
| Record URI | **`EPHREM_TEI_URI_BASE` followed by the record id**, when the instance sets it. |
| Folio label | **The page Name** in eScriptorium. |
| Text structure | **A text flow**: headings and paragraphs as elements, pages, columns and lines as milestones (`pb`, `cb`, `lb`). |
| Paragraphs | **Only where editors mark them** (line type *ParagraphStart*); other text is in neutral `ab` blocks. |
| Language | **`syr`**, or an approved Syriac tag set by the document's `tei_language` metadata; never derived from eScriptorium's script setting. |
| Licence and publisher wording | **Deferred** until the website's requirements are known. |
| Schema | **Official TEI P5 `tei_all.rng`, unchanged.** This profile defines the subset and conventions. |
| Validation | **RelaxNG**, plus checks of the internal links and of the eleven required items, run on every export. No Schematron. |
| Download | **A `.xml` file**, or a `.zip` with the images when they are included. |

## 2. How the export is built

The brief plans this workflow: eScriptorium → PAGE XML export → converter adds project metadata → minimal TEI generation → TEI validation → downloadable TEI file.

We build the same pipeline **without the intermediate PAGE XML file**, because PAGE XML doesn't carry what eight of the eleven required items need (the record id, the manuscript and work, the language, the people, the statuses, the folio names, the uncertain readings): a converter would have to read the database anyway.
The exporter is the package `app/apps/imports/tei/`, in five stages:

| Stage | Module | Does |
|---|---|---|
| 1. Collect | `snapshot.py` | Reads the document, its pages, regions, lines, annotations, statuses and metadata into plain data (a *snapshot*). The only stage that reads the database. |
| 2. Check | `checks.py`, `layout.py` | Checks the snapshot against this profile and plans the file: metadata, works, folios, the text flow, notes, annotations, credits. Reports **every** problem, as errors (the export stops) or warnings. |
| 3. Generate | `builder.py` | Writes the TEI with `lxml`. Text is set as text, never parsed as markup. |
| 4. Validate | `validation.py` | `tei_all.rng`; every internal link; the eleven required items ([section 10](#10-validation)). |
| 5. Package | `imports/export.py` | `EphremTEIExporter` writes the `.xml` file, or a `.zip` with the images. |

The stages after the first only see the snapshot. **A PAGE XML → TEI converter** can therefore be added later by building a snapshot from PAGE files and a metadata table, and reusing the checks, the generator and the validation.

The **readiness check** ([section 9](#9-checks-before-export-and-the-readiness-check)) runs stages 1 to 4 without writing a file.

## 3. The file at a glance

A shortened example. `…` stands for left-out content.
The complete example is the [features document](#11-reference-files).

```xml
<?xml version="1.0" encoding="UTF-8"?>
<?xml-model href="https://www.tei-c.org/Vault/P5/4.12.0/xml/tei/custom/schema/relaxng/tei_all.rng" type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0" xml:id="example-ms-1" xml:lang="en">
  <teiHeader>
    <fileDesc>
      <titleStmt>
        <title>Example MS 1</title>
        <respStmt>
          <resp>Syriac text transcribed by</resp>
          <resp>Reviewed by</resp>
          <persName xml:id="pers-2">Jane Doe</persName>
        </respStmt>
        <respStmt>
          <resp>Reviewed by</resp>
          <persName xml:id="pers-x-sebastian-brock">Sebastian Brock</persName>
        </respStmt>
        <respStmt>
          <resp>Automatic text recognition by</resp>
          <name type="software" xml:id="htr-syr_test">kraken model syr_test</name>
        </respStmt>
      </titleStmt>
      <publicationStmt>
        <authority>Example project</authority>
        <idno type="ephrem">example-ms-1</idno>
        <idno type="URI">https://ephrem.example.org/records/example-ms-1</idno>
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
              <author>Ephrem</author>
              <title ref="http://syriaca.org/work/1505">Hymns on Faith</title>
            </msItem>
          </msContents>
        </msDesc>
      </sourceDesc>
    </fileDesc>
    <encodingDesc>…</encodingDesc>
    <profileDesc>
      <langUsage>
        <language ident="en">English</language>
        <language ident="syr">Syriac</language>
      </langUsage>
    </profileDesc>
    <revisionDesc status="not_started">
      <change xml:id="status-901" when="2026-10-03T14:12:09+00:00" who="#pers-2" status="reviewed_1" target="#surface-901">23r: Reviewed by Editor 1</change>
      <change xml:id="status-902" status="not_started" target="#surface-902">23v: Not started</change>
    </revisionDesc>
  </teiHeader>
  <facsimile>
    <surface xml:id="surface-901" n="23r" ulx="0" uly="0" lrx="864" lry="206" change="#status-901">
      <graphic url="MS1%20f23r.png" width="864px" height="206px"/>
      <zone xml:id="zone-r3" type="mainzone:right" points="500,40 900,40 900,160 500,160">
        <zone xml:id="zone-l3" type="line" points="500,40 900,40 900,60 500,60"/>
        …
      </zone>
      …
    </surface>
    …
  </facsimile>
  <text xml:lang="syr" type="ManuscriptTranscription">
    <body>
      <div type="work" n="1" corresp="#work-1">
        <div type="section" n="1">
          <pb n="23r" facs="#surface-901"/>
          <fw type="header" facs="#zone-r1">
            <lb facs="#zone-l1"/>ܡܕܪܫܐ ܕܗܝܡܢܘܬܐ
          </fw>
          <cb n="a"/>
          <head>
            <lb n="1" facs="#zone-l3"/>ܡܕܪܫܐ
          </head>
          <p>
            <lb n="2" facs="#zone-l4"/>ܗܝܡܢܘܬܐ <unclear reason="faded">ܕܐܠ
            <lb n="3" facs="#zone-l6"/>ܗܐ</unclear> <add place="above">ܘ</add>ܗ<add place="above" facs="#zone-l5">ܘ</add>
            <note place="margin" facs="#zone-r5">
              <lb facs="#zone-l10"/>ܥܘܢܝܬܐ
            </note>
            <lb n="4" facs="#zone-l7"/>x &lt; y &amp; z
            <cb n="b"/>
            <lb n="1" facs="#zone-l8"/>ܐ
            <pb n="23v" facs="#surface-902"/>
            <lb n="1" facs="#zone-l13"/>ܓ <gap reason="illegible" extent="3" unit="chars"/> ܕ
          </p>
        </div>
      </div>
    </body>
  </text>
</TEI>
```

## 4. Required information: mapping table

One row for each of the brief's eleven required items.
"Required data" means the exporter refuses to export without it ([section 9](#9-checks-before-export-and-the-readiness-check)); the validation of every file checks each item again ([section 10](#10-validation)).

| # | Brief item | TEI | eScriptorium source | Required data |
|---|---|---|---|---|
| 1 | Stable record ID | `TEI/@xml:id`; `publicationStmt/idno[@type="ephrem"]`; `idno[@type="URI"]` | Document metadata `record_id`; the `EPHREM_TEI_URI_BASE` setting | `record_id` |
| 2 | Manuscript identification | `msDesc/msIdentifier`: `settlement`, `repository`, `idno[@type="shelfmark"]` | Document metadata `settlement`, `repository`, `shelfmark` (or their other names) | `repository`, `shelfmark` |
| 3 | Work / text identification, and its relationship to the manuscript | `msContents/msItem` (`locus`, optional `author`, `title` with `@ref` to the work's URI); `div[@type="work"]/@corresp` pointing to the `msItem` | Page metadata `work`, `work_uri`, `author`, with the document's values as defaults | `work` |
| 4 | Language declaration | `profileDesc/langUsage/language`; `text/@xml:lang` | `syr`, or document metadata `tei_language` | — |
| 5 | Responsibility | `titleStmt/respStmt`, one per person; `change/@who` | Line edit history; page status changes; document metadata `transcribed_by`, `reviewed_by`, `edited_by` | — |
| 6 | Revision / review status | `revisionDesc/@status` (current stage); `revisionDesc/change`; `surface/@change` | Page editorial statuses and their history | — |
| 7 | Textual divisions | `div[@type="work"]`, `div[@type="section"]`, `head`, `p`, `ab` | `work` metadata; heading lines and regions; paragraph-start lines | — |
| 8 | Folio / page breaks | `pb/@n`, `pb/@facs`; `surface/@n` | Page Name; page order | Page Name |
| 9 | Transcription lines | `lb/@n`, `lb/@facs`, then the line text; `cb` for columns | Lines of the chosen transcription layer, in reading order | — |
| 10 | Image links | `facsimile/surface/graphic/@url`; `zone` for regions and lines | Image file name and size; the IIIF source URL; region and line polygons | — |
| 11 | Uncertain or illegible readings | `unclear`, `gap` (and `add` for additions) | Text annotations whose taxonomy is named `unclear`, `gap` or `add` | — |

## 5. Header

### 5.1 Record identifier and the other ids

`TEI/@xml:id` and `publicationStmt/idno[@type="ephrem"]` are the document's **`record_id`** metadata.
It is assigned by the project and doesn't change when the document is re-imported or moved to another instance, which the eScriptorium document id would.

- It must start with a letter or `_` and contain only letters, digits, `.`, `_` and `-`, so that it is a valid `xml:id` and can end a URI and name a file.
- It must not start like the other ids in the file (`surface-`, `zone-`, `work-`, `pers-`, `htr-`, `status-`).
- No other document may have the same `record_id`, ignoring case.

When the instance sets `EPHREM_TEI_URI_BASE`, `publicationStmt` also has `<idno type="URI">` with that base followed by the record id.

Other ids in the file:

| Thing | id |
|---|---|
| Page (`surface`) | `surface-{part pk}` |
| Region (`zone`) | `zone-r{block pk}` |
| Line (`zone`) | `zone-l{line pk}` |
| Work (`msItem`) | `work-{n}`, numbered in order of first appearance |
| Person with an eScriptorium account (`persName`) | `pers-{user id}` |
| Person without one (`persName`) | `pers-x-{name}` |
| HTR model (`name`) | `htr-{model name}` |
| A page's current status (`change`) | `status-{part pk}`; older changes `status-{part pk}-2`, … |

Names in ids are made safe: lower case, with every character other than letters, digits, `.`, `_` and `-` replaced by `-`; if two end up the same, the second gets a number added.
We use database ids rather than region and line `external_id`, because imported `external_id` values repeat across pages.

### 5.2 Title

One `titleStmt/title`, the document name.

### 5.3 Responsibility

`titleStmt` has one `respStmt` per person: one `resp` for each role they had, then one `persName` with an `xml:id`.
`change/@who` points to that id.
The name is the user's full name, or their username if no full name is set. Email addresses are never exported.

| `resp` | Who |
|---|---|
| Syriac text transcribed by | Authors of any version of an exported line (current or in its history) whose source is `eScriptorium` (typed in the editor) or `import`; users who set a page to *In progress* or *Initial transcription complete*; names in `transcribed_by` |
| Reviewed by | Users who set a page to *Reviewed by Editor 1* or *Reviewed by Editor 2*; names in `reviewed_by` |
| Edited by | Users who set a page to *Ground truth*, *Final edited copy* or *Ready for TEI export*; names in `edited_by` |

- Line versions come from `LineTranscription.version_author` and `version_source`, and from the `versions` history (the last 20 edits of each line).
- `transcribed_by`, `reviewed_by` and `edited_by` credit people who did not work in eScriptorium. Several names are separated by `;`. A name that is the username or full name (ignoring case) of someone already credited from the document's lines or statuses adds the role to that person; any other name is a person of its own, `pers-x-{name}`.
- **Automatic text recognition.** A version whose source is `kraken:{model name}` was produced by a model. Each model gets its own `respStmt`, with `resp` *Automatic text recognition by* and `name type="software"`. The user who ran the model is not credited for those versions.

### 5.4 Publication

```xml
<publicationStmt>
  <authority>{eScriptorium project name}</authority>
  <idno type="ephrem">{record_id}</idno>
  <idno type="URI">{EPHREM_TEI_URI_BASE}{record_id}</idno>   <!-- only if the setting is set -->
  <date when="{export date, YYYY-MM-DD}"/>
</publicationStmt>
```

TEI requires a responsible body before an `idno`. Until the website's wording is agreed, `authority` is the name of the eScriptorium project that holds the document.
Version 1.1 has no licence (`availability`).

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
        <title ref="{work_uri}">{work}</title>          <!-- @ref only if set -->
      </msItem>
    </msContents>
  </msDesc>
</sourceDesc>
```

- `msContents` lists the works on the **exported** pages, not every work in the manuscript.
- This is where the brief's "relationship between the manuscript witness and the work" is recorded: each work appears once, with the folios where the manuscript has it and its Syriaca.org URI, and the text's work divisions point back to it.
- A page's `work`, `work_uri` and `author` come from its own metadata. A page without its own `work` takes the document's `work`, and then also the document's `work_uri` and `author`: those belong to the document's work, not to a page that names another.
- Every page of a work must give the same `author` and the same `work_uri`, or none. A work without `work_uri` is a warning.

### 5.6 Encoding

`encodingDesc/editorialDecl` is one fixed paragraph that names the transcription layer:
*"Diplomatic transcription made in eScriptorium, from the transcription layer "{name}". One lb element per manuscript line, one pb element per page and one cb element per column. Headings (head) and paragraphs (p) are those the editors marked; the rest of the text is in ab elements. Line text is as entered: not normalised and not punctuated."*

### 5.7 Language

| | Value |
|---|---|
| `TEI/@xml:lang` | `en`: the header is in English |
| `profileDesc/langUsage` | `<language ident="en">English</language>` and one `language` for the text |
| `text/@xml:lang` | `syr`, or the document's `tei_language` |

The language tags are Syriaca.org's:

| `tei_language` | `language` |
|---|---|
| `syr` (the default) | Syriac |
| `syr-Syre` | Syriac in Estrangela script |
| `syr-Syrj` | Syriac in vocalised West Syriac script |
| `syr-Syrn` | Syriac in vocalised East Syriac script |
| `syr-x-syrm` | Syriac in Melkite script |

`tei_language` is matched ignoring case; any other value is an error.
The script subtag is an editorial statement: Syriaca.org keeps `Syrj` and `Syrn` for vocalised text, so it is **never** derived from the document's script in eScriptorium, which only sets the editor's font and direction. Syriaca.org does not use `syc`.

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
  <change xml:id="status-{part pk}" when="{changed_at}" who="#pers-{user id}" status="{new status code}"
          target="#surface-{part pk}">{page name}: {label}</change>
  …
</revisionDesc>
```

- **Current stage:** `revisionDesc/@status` is the status of the **least advanced** exported page. One page still *In progress* means the file is `in_progress`.
- **History:** one `change` for each status change of an exported page, **newest first**. `@status` is the page's new status, `@target` its `surface`. `@when` is an ISO 8601 date-time with a `T` and a time zone.
- **Each page points to its current status:** its `surface/@change` points to the `change` with id `status-{part pk}`, its newest.
- **Every exported page appears at least once.** A page with no recorded change gets one `change` with its current status and no `@when` or `@who`, e.g. `<change xml:id="status-717" status="in_progress" target="#surface-717">179r: In progress</change>`. TEI does not allow an empty `revisionDesc`.
- **Source:** the status history from [#19](https://github.com/SimpleTreeDa/escriptorium-ui/issues/19), read in one place (`snapshot.status_changes()`). Until #19 is merged, each page gives one `change` from `editorial_status`, `editorial_status_by` and `editorial_status_at`, so the output keeps the same shape when #19 lands.

## 6. Text

### 6.1 A text flow

The brief asks to keep both the work's structure and the manuscript's lines.
The text is therefore one flow per work: its **logical structure** (works, sections, headings, paragraphs) is in elements, and its **physical structure** (pages, columns, lines) is in milestones that point into the facsimile:

```xml
<text xml:lang="syr" type="ManuscriptTranscription">
  <body>
    <div type="work" n="{n}" corresp="#work-{n}">
      …text before the first heading…
      <div type="section" n="1">
        <pb …/> <cb n="a"/>
        <head><lb n="1" …/>…</head>
        <p><lb n="2" …/>… <pb …/> <lb n="1" …/>…</p>
        <ab><lb …/>…</ab>
      </div>
    </div>
  </body>
</text>
```

- A paragraph or block of text runs on across page and column breaks; `pb`, `cb` and `lb` sit inside it.
- Lines are in eScriptorium's reading order.
- `text/@type="ManuscriptTranscription"` is the Digital Syriac Corpus's type for transcriptions made from a manuscript.

### 6.2 Works

Each run of consecutive exported pages with the same `work` becomes one `div type="work"`.
Its `@n` and `@corresp` point to the work's `msItem`.

**Limitation:** a work that begins in the middle of a page can't be marked; the page belongs to one work.

### 6.3 Headings and sections

A heading is a line of type **HeadingLine**, or a line in a region of type **Title** (also *Heading*, *Rubric*).

- A heading opens a new `div type="section"`, numbered from 1 within the work division, with the heading as its `head`. TEI only allows `head` at the start of a division, so a heading can't stay inside the text before it.
- Consecutive heading lines are one `head`.
- The section runs until the next heading or the end of the work division.
- Text of a work before its first heading stays directly in the work's `div`.
- `pb`, `cb`, `fw` and `note` can come before a `head`.

### 6.4 Paragraphs and blocks

- A line of type **ParagraphStart** starts a new `p`. The paragraph runs until the next paragraph start, heading, block of another type, or the end of the work division.
- Text that no paragraph start precedes is in `ab`, TEI's neutral block. The export never guesses paragraphs: a region is a layout block, and one paragraph of the text often runs across columns and pages.
- A block never continues into another work division.

### 6.5 Pages

One `pb` per exported page, in page order.
`pb/@n` is the page Name (e.g. `95r`), and `pb/@facs` points to the page's `surface`.
A page with no text still gets its `pb`.

### 6.6 Columns and lines

- **Columns.** The main-text regions of a page that sit side by side are its columns. When the text moves to another column, a `cb` is written. Columns are lettered `a`, `b`, … in reading order: in a right-to-left manuscript the rightmost column is `a`. A page with one column has no `cb`.
- **Lines.** Each line of the text is an empty `lb` followed by its text. `lb/@n` counts the page's lines from 1, and restarts in each column. `lb/@facs` points to the line's zone.
- Lines with no text are still exported, as `lb` alone, so line numbers match the image.
- The text comes from the transcription layer chosen in the export dialog. The region types ticked in the export dialog decide which regions are exported, as for the other formats.

### 6.7 Notes, additions and page furniture

These are not part of the text flow. Each is placed **after the text line it belongs to**, by position on the page:

| Type | TEI | Placed after |
|---|---|---|
| Region *MarginTextZone* (also *Margin*, *Marginalia*) | `note place="margin"` | the text line whose vertical middle is nearest the note's |
| Region *Commentary* | `note type="commentary"` | the same |
| Line *InterlinearLine* or *Correction* | `add place="above"` | the nearest text line below it: the line it is written above |
| Region *RunningTitleZone* (also *Running Header*); region *NumberingZone* or line *Numbering*; region *QuireMarksZone* or line *Signature* | `fw type="header"`, `fw type="pageNum"`, `fw type="sig"` | the start of the page when it is above all the text; otherwise the nearest text line |

- A note or `fw` made from a region points to the region's zone (`@facs`), and its lines are `lb` with their own `@facs` but **no `@n`**: they are not counted with the text's lines.
- An addition or `fw` made from a single line points to the line's zone, without an `lb`.
- The position inside the line is not known: an interlinear addition comes at the end of the line it belongs to. To place an addition exactly, type it where it belongs in the line and use the `add` annotation ([6.9](#69-uncertain-illegible-and-added-text)).

### 6.8 Pictures, and types the profile doesn't know

- Regions of type *Illustration*, *GraphicZone* or *DecorationZone* hold no text: they are exported as zones only. Text typed in their lines is **not** exported, and the readiness check warns about it.
- A region or line of any other type is exported as a block of its own, `ab` with `@type` set to the type name (lower case, spaces replaced by `-`), e.g. `<ab type="dropcapitalline">`. Consecutive lines of the same unknown type share a block. The readiness check lists every such type, so that it can be retyped or added to the profile.
- Main text types: regions *MainZone* (with any subtype, e.g. *MainZone:left*), *Main*, *Left Column*, *Middle Column*, *Right Column*, *MainLeft*, *MainRight*, regions without a type, and lines outside any region; lines *DefaultLine* (with any subtype), *Main*, and lines without a type.
- The full type map is `REGION_ROLES` and `LINE_ROLES` in `app/apps/imports/tei/profile.py`, and the [Ephrem ontology](ephrem-ontology.json) holds these types.

### 6.9 Uncertain, illegible and added text

Text annotations become TEI elements when their taxonomy's name, ignoring case, is one of these:

| Taxonomy | TEI | The annotated characters | Attributes, from the annotation's components |
|---|---|---|---|
| `unclear` | `<unclear>…</unclear>` | Kept, inside the element | `reason`, e.g. `faded` |
| `gap` | `<gap/>` | Dropped: they are a placeholder | `reason` (default `illegible`), `extent`, `unit` (one word) |
| `add` | `<add>…</add>` | Kept, inside the element | `place`, e.g. `above`, `below`, `margin` |

- **Gap convention:** type a placeholder for the illegible text (e.g. `…`) and annotate the placeholder with the `gap` taxonomy.
- Only annotations on the exported transcription layer are used. Annotations with other taxonomies are not exported.
- An annotation may run across lines of the same block, including across a column break. The export refuses an annotation that **crosses a heading, a note or a paragraph boundary**, one that runs into text that is not exported, one that doesn't fit its lines' text, and two annotations that overlap without one containing the other.

### 6.10 Characters

- Line text is exported exactly as stored. eScriptorium stores it in Unicode NFC ([#70](https://github.com/SimpleTreeDa/escriptorium-ui/pull/70)), and the exporter normalises nothing further.
- Right-to-left marks and zero-width characters are kept.
- `&`, `<` and `>` are escaped. Text is never read as markup.
- Characters that XML 1.0 forbids (control characters other than tab and newline) are reported as errors.

## 7. Facsimile and image links

`facsimile` comes between `teiHeader` and `text`, with one `surface` per exported page.

```xml
<surface xml:id="surface-{part pk}" n="{page name}" ulx="0" uly="0" lrx="{image width}" lry="{image height}"
         change="#status-{part pk}">
  <graphic url="{percent-encoded image file name}" width="{width}px" height="{height}px"/>
  <graphic type="source" url="{source URL}"/>   <!-- only for pages imported from a web address (IIIF) -->
  <zone xml:id="zone-r{block pk}" type="{region type}" points="x,y x,y …">
    <zone xml:id="zone-l{line pk}" type="line" points="x,y x,y …"/>
  </zone>
</surface>
```

**The image link** (`graphic/@url`):

- It is the name of the page's image file (`DocumentPart.filename`), relative to the TEI file. With "include images" ticked, the zip contains that file next to the TEI file.
- The exporter works out this name **once per page**, and uses the same string as the file name in the zip and, percent-encoded, as `graphic/@url`. The link and the file can't drift apart.
- **Percent-encoding** (Python's `quote()`): `MS1 f023r.jpg` becomes `MS1%20f023r.jpg`. Decoding the URL gives back the exact file name, including Syriac and accented names. A space, `%`, `(` or `[` would make the file invalid TEI, and `#` or `?` would change the link's meaning.
- Two exported pages with the same image file name are an error; both would point to the same file.

**The source link:** pages imported from a IIIF manifest also get `graphic type="source"` with the URL eScriptorium downloaded the image from (`DocumentPart.source`).
It is written only when `source` is an `http://` or `https://` address without spaces; PDF and zip imports store values like `pdf//…` and `zip//…`.

**Zones:**

- Coordinates are pixels of the image stored in eScriptorium.
- Every exported region has a zone, including pictures, which have no text. Region zones use the region polygon; line zones use the line mask and sit inside their region's zone.
- Lines outside any region sit directly in the `surface`.
- A line without a mask has no zone and no `lb/@facs`. Baselines are not exported.
- Zones hold no text.

## 8. What editors fill in

**Document metadata.** Keys are matched ignoring case and surrounding spaces. The other names are for metadata copied from IIIF manifests; when a key appears under several names, the first in the list wins.

| Key | Other names | Required | Example |
|---|---|---|---|
| `record_id` | `record id` | **Yes** | `sachau-176` |
| `repository` | `holding institution`, `institution`, `library` | **Yes** | `Staatsbibliothek zu Berlin` |
| `shelfmark` | `shelf mark`, `shelf-mark`, `call number`, `classmark` | **Yes** | `Sachau 176` |
| `work` | | **Yes**, for every page directly or through the document | `Memra for Holy Thursday` |
| `work_uri` | `work uri` | Recommended (a warning without it) | `http://syriaca.org/work/…` |
| `settlement` | `location`, `city` | No | `Berlin` |
| `author` | | No | `Narsai` |
| `tei_language` | | No | `syr-Syre` |
| `transcribed_by`, `reviewed_by`, `edited_by` | `transcribed by`, … | No | `Sebastian Brock; Jane Doe` |

**Page metadata:** `work`, `work_uri` and `author`, for pages of another work than the document's. The Images page sets `work` and `work_uri` on several pages at once.

**Page Name:** the folio, as one word, unique in the document, e.g. `179r`. The Images page's *Number folios* names selected pages `1r`, `1v`, `2r`, … from a first folio. IIIF imports name pages after their canvas labels.

**Types and annotations:** the [Ephrem ontology](ephrem-ontology.json), added with `python manage.py apply_ephrem_ontology` or the ontology page's import. See [section 6](#6-text).

## 9. Checks before export, and the readiness check

The exporter checks the data before it writes anything.
It collects **every** problem and fails once, with one plain-language message per problem, through the export's error report:

- `Document: metadata "record_id" is missing`
- `Document: record_id "example-ms-1" is already used by another document`
- `Document: metadata "shelfmark" has 2 different values`
- `Document: tei_language "syc" is not one of the approved tags: syr, syr-Syre, syr-Syrj, syr-Syrn, syr-x-syrm`
- `Page 12 (MS1_f023r.jpg): no name; set the page Name to the folio, e.g. 23r`
- `Page 12 (MS1_f023r.jpg): name "f. 23r" contains a space; use the folio alone, e.g. 23r`
- `Pages 12, 15: all are named "23r"`
- `Page 12 (MS1_f023r.jpg): no work; set page metadata "work" or document metadata "work"`
- `Page 12 (MS1_f023r.jpg): work_uri "syriaca.org/work/1" is not a web address (http:// or https://, without spaces)`
- `Work "Memra for Holy Thursday": pages give different authors, or only some give one`
- `Pages 12, 15: all use the image file name "scan.jpg"`
- `Page 12 (MS1_f023r.jpg), column b, line 7: the "unclear" annotation crosses a note boundary`
- `Page 12 (MS1_f023r.jpg), line 7: the "add" annotation overlaps the "unclear" annotation`
- `Page 12 (MS1_f023r.jpg), line 7: character U+0007 is not allowed in XML`

Warnings don't stop the export; they are added to the export's report:

- a work without `work_uri`;
- a region or line type the profile doesn't know, or text in a picture region ([6.8](#68-pictures-and-types-the-profile-doesnt-know));
- no one credited;
- the record URI not written because `EPHREM_TEI_URI_BASE` is not set.

**The readiness check** (`POST /api/documents/{pk}/tei_check/`, the export dialog's *Check TEI readiness*) takes the export's choices (transcription layer, region types, pages) and returns the same errors and warnings without writing a file, each in a category: `metadata`, `work`, `folio`, `annotations`, `types`, `links` (the generated file) and `other`, with a count per category.
It runs the link and required-item checks of [section 10](#10-validation) on the file it would write. It runs the RelaxNG validation only when asked (`"schema": true`): compiling `tei_all.rng` takes about 10 seconds and 70 MB per web process, and once the data checks pass, a schema error can only be a bug in the exporter, which every export still catches.

## 10. Validation

Every exported file is validated before it is written. A problem here is a bug in the exporter, not in the document, and the export stops saying so.

### 10.1 Schema

**`tei_all.rng` from TEI P5 4.12.0**, committed unchanged at `app/escriptorium/static/tei_all.rng`, next to `alto-4-1-baselines.xsd`. The setting `EPHREM_TEI_SCHEMA_PATH` can point the exporter to another copy.

- **Source:** the TEI Vault, which keeps every release at a fixed address: <https://www.tei-c.org/Vault/P5/4.12.0/xml/tei/custom/schema/relaxng/tei_all.rng>.
- **Licence:** TEI publishes it under CC BY and BSD-2.
- **Declared in every file** with the `<?xml-model?>` line shown in [section 3](#3-the-file-at-a-glance), so TEI editors such as Oxygen validate exports automatically.
- **No custom schema:** everything this profile adds is either a fixed value the generator writes or a data check the exporter runs. A project ODD would only pay off if people wrote Ephrem TEI by hand.
- **Syriaca.org's schema doesn't fit:** it removes `surface` and `zone`.
- `lxml` 6.1.0 with libxml2 2.14.6, as in the eScriptorium image, compiles it in about 10 seconds, once per process, and validates a file in milliseconds.

### 10.2 What checks what

| Check | Done by |
|---|---|
| Well-formed XML; `xml:id` values are valid names and unique | XML parser |
| Element order and nesting; required elements and attributes; value formats (URIs, date-times, `px` sizes, zone `points`, no spaces in `@type`) | RelaxNG validation with `lxml` |
| Required metadata; record id; page names; works; image file names; annotations; XML-safe characters | The checks of stage 2 ([section 9](#9-checks-before-export-and-the-readiness-check)) |
| **Every internal link** (`@facs`, `@who`, `@target`, `@corresp`, `@change`) points to an `xml:id` in the file, and to the right kind of element: `pb` to a `surface`, `lb` to a line zone, `change/@target` to a `surface`, `change/@who` to a `persName`, a work `div` to an `msItem`, `surface/@change` to a `change` | `validation.link_errors()` |
| **The eleven required items** are present, with the profile's conventions: the record id; the manuscript; works and their divisions; the language; credits; the current stage and each page's status; sections starting with a heading; one `pb` per surface with the same folio; line numbering per page and column; image links and empty zones; empty gaps | `validation.requirement_errors()` |

RelaxNG can't check links: to the schema they are just URIs.

**No Schematron in version 1.1.** `tei_all.rng` also embeds TEI's Schematron rules (98 rules in 93 patterns). We don't run them: only two apply to the elements this profile uses, and the exporter guarantees both (`msIdentifier` has a `repository`; zones hold no text). They need XPath 2, which `lxml` can't run.

## 11. Reference files

Both are in `app/apps/imports/tests/samples/`, and `app/apps/imports/tests/test_tei_profile.py` checks them with the validation of section 10; it needs no database.

- **`ephrem_tei_features.xml`**: a synthetic document that uses every construct in this profile: two columns, running material, a heading and a section, a paragraph across a page break, `unclear`, `gap` and both kinds of `add`, margin and commentary notes, a quire signature, a picture, unknown types, several works, a work URI, credits from metadata, the record URI. It is the export of the fixture in `test_ephrem_tei_exporter.py`, with the database ids renumbered.
- **`ephrem_tei_sample.xml`**: the canonical sample, from real data.

**Source of the canonical sample: Sachau 176, ff. 179r–179v** (eScriptorium document 15, "Sachau 176 - Training Data"), from the transcription layer `kraken:syr_41transcribathon_docs_d_3`, which is where the corrections were made. The work is Narsai's *Memra for Holy Thursday*, which the Berlin catalogue places at ff. 175v–182v.

- f. 179r has 27 lines, all corrected by hand after automatic recognition; f. 179v has 28 lines, the first 2 corrected and the rest automatic recognition output. That exercises both kinds of credit.
- It has one column, a *Main* region on each page and one line outside any region on f. 179v, real line masks, image file names with spaces, and page statuses with no recorded who or when.
- Vat. sir. 111, the first choice (about 522, one of the earliest witnesses to Ephrem), has no transcription on the project's instance yet.
- **Values not yet in eScriptorium:** the record id (`sachau-176`), page names, and the document metadata `repository`, `shelfmark`, `settlement`, `work` and `author` are the values editors will enter. The person id depends on the instance's user ids.

## 12. Relation to the Digital Syriac Corpus

The brief asks for a model informed by the [Digital Syriac Corpus](https://github.com/srophe/syriac-corpus) but not copied from it, and more manuscript-centred.

**Taken from the Corpus and Syriaca.org**

- `msIdentifier` with `settlement`, `repository` and `idno type="shelfmark"`.
- Fixed `resp` wording ("Syriac text transcribed by").
- `change` with `@when` and `@who`, newest first.
- `text/@type="ManuscriptTranscription"`.
- `TEI/@xml:lang="en"`, with Syriac tagged as `syr`, and Syriaca.org's script tags only as an editorial choice.
- `title/@ref` with the Syriaca.org work URI.
- `pb/@n` as the folio.
- Sections as `div type="section"` with a `head`.

**Not taken**

- The Corpus's project boilerplate (sponsors, editorial board, distributor, series title, copyright notes).
- Empty placeholder elements.
- One `respStmt` per role: we use one per person, so `change/@who` can point to a single id.
- `biblStruct` sources.
- Literal `[…]` for lacunae.
- The Syriaca.org schema.

**New, because the Corpus has no precedent:** `facsimile`, `surface` and `zone` with `@facs` links; `lb` and `cb`; `unclear`, `gap` and `add`; margin notes and page furniture; responsibility and status from eScriptorium's edit history and page statuses; each page linked to its status.

## 13. Not in version 1.1

**Deferred by decision**

- Licence and publisher wording.
- Exporting only pages that are *Ready for TEI export*.
- Printed editions.
- Works that begin in the middle of a page.

**The brief's "can be added later" list**

- Deletions and corrections.
- Abbreviations and expansions.
- Supplied or reconstructed text.
- Quotations.
- Named entities.
- A richer manuscript description.

**Also not in version 1.1**

- Links to Syriaca.org manuscript and person records.
- Date of composition.
- Words broken across lines (`lb break="no"`).
- Hands.
- Verse (`lg`, `l`).
- Baselines.
- Glyph positions and recognition confidence.
- Schematron validation.

## 14. Changes from version 1.0

| | Version 1.0 | Version 1.1 |
|---|---|---|
| Record id | `ephrem-doc-{pk}`, from the document id | The document's `record_id` metadata, unique; `idno type="URI"` with `EPHREM_TEI_URI_BASE` |
| Generation | Django templates | `lxml`, in five stages (`app/apps/imports/tei/`) |
| Text structure | One element per region, in region order | A text flow: headings open sections, paragraphs only where marked, `pb`/`cb`/`lb` milestones |
| Headings | Region types only | Also line type *HeadingLine* |
| Paragraphs | Never (`ab` only) | Line type *ParagraphStart* gives `p` |
| Columns | Separate regions, no `cb` | `cb`, lettered in reading order; line numbers per column |
| Notes and additions | After the page's text, in region order | After the nearest text line; *InterlinearLine* and *Correction* lines become `add` |
| Commentary | `ab type="commentary"` | `note type="commentary"` |
| Pictures | Not exported | Zones, without text |
| Unknown types | `ab` with the type | The same, with a warning |
| Annotations | Within one region | Within one block: an error across a heading, a note or a paragraph |
| Metadata keys | Lower case, exact names | Any case, with other names for IIIF metadata |
| Language | `syr` only | `syr`, or an approved tag from `tei_language` |
| People | `pers-{username}` | `pers-{user id}`; names from `transcribed_by`, `reviewed_by`, `edited_by` as `pers-x-…` |
| Status | `change` per page | Also `change/@xml:id` and `surface/@change` |
| Work URI | Not in v1 | `msItem/title/@ref` from `work_uri` |
| Link and required-item checks | In the tests | On every export, and in the readiness check |
| Download | A zip | A `.xml` file, or a `.zip` with the images |
