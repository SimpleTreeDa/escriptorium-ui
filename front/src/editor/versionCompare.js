/*
 * Versions of a page's text to compare side by side (new UI editor), rebuilt
 * from the history the server keeps for the text of each line in a
 * transcription (Versioned, app/apps/versioning/models.py).
 *
 * A line keeps its current text and up to MAX_KEPT_VERSIONS earlier ones, each
 * with its source ("kraken:<model>" for model output, "import" for imported
 * text, anything else for edits made in the editor), its author and the time
 * it was written. The versions of a page offered for comparison are:
 * - "model:<name>": the output of a model, line by line
 * - "import": the imported text
 * - "author:<name>": the page as someone left it, at their last edit
 * - "current": the current text
 */
import { diffChars } from "diff";

/** Earlier versions kept for each line (Versioned.version_history_max_length) */
export const MAX_KEPT_VERSIONS = 20;

/** Most columns compared at once */
export const MAX_COLUMNS = 3;

const MODEL_PREFIX = "kraken:";
const IMPORT_SOURCE = "import";

/** The text of a line in a version: it had this text, none, or it is too old to know */
const textCell = (text) => ({ status: "text", text });
const NO_TEXT = Object.freeze({ status: "none", text: "" });
const UNKNOWN = Object.freeze({ status: "unknown", text: "" });

/**
 * "model", "import" or "edit": where the text of a line state comes from.
 */
export function stateKind(state) {
    if (state.source.startsWith(MODEL_PREFIX)) return "model";
    if (state.source === IMPORT_SOURCE) return "import";
    return "edit";
}

/**
 * The states of the text of a line, oldest first, from its transcription as the
 * API returns it (line.currentTrans): { content, source, author, at } with `at`
 * in ms. `truncated` is true when older states may have been dropped.
 */
export function lineHistory(trans) {
    if (!trans) return { states: [], truncated: false };
    const versions = Array.isArray(trans.versions) ? trans.versions : [];
    const states = versions
        .slice()
        .reverse()
        .map((version) => ({
            content: (version.data && version.data.content) || "",
            source: version.source || "",
            author: version.author || "",
            at: Date.parse(version.created_at) || 0,
        }));
    // the current text, unless the line has no text in this transcription yet
    if (trans.pk || trans.content) {
        states.push({
            content: trans.content || "",
            source: trans.version_source || "",
            author: trans.version_author || "",
            // when it was last saved; unknown for text not saved yet
            at: Date.parse(trans.version_updated_at) || Infinity,
        });
    }
    return { states, truncated: versions.length >= MAX_KEPT_VERSIONS };
}

const byTime = ([, a], [, b]) => a - b;

/**
 * The versions of the page that can be compared, given the history of each of
 * its lines, in this order: model outputs, imported text, the page as each
 * person left it (by time), then the current text. Each one is
 * { id, kind, label, at }, plus `model` or `author`.
 *
 * The page as someone left it is offered only if someone else changed it
 * since: otherwise it is the current text.
 */
export function pageVersions(histories) {
    const models = new Map(); // model name -> time of its first output
    const authors = new Map(); // author -> time of their last edit
    let importedAt = null;
    let lastChange = -Infinity;
    histories.forEach(({ states }) => {
        states.forEach((state) => {
            lastChange = Math.max(lastChange, state.at);
            const kind = stateKind(state);
            if (kind === "model") {
                const model = state.source.slice(MODEL_PREFIX.length);
                models.set(model, Math.min(models.get(model) ?? Infinity, state.at));
            } else if (kind === "import") {
                importedAt = Math.min(importedAt ?? Infinity, state.at);
            } else if (state.author) {
                const last = authors.get(state.author) ?? -Infinity;
                authors.set(state.author, Math.max(last, state.at));
            }
        });
    });
    const versions = [...models].sort(byTime).map(([model, at]) => ({
        id: `model:${model}`,
        kind: "model",
        model,
        label: `Model output (${model})`,
        at,
    }));
    if (importedAt !== null) {
        versions.push({ id: "import", kind: "import", label: "Imported text", at: importedAt });
    }
    [...authors].sort(byTime).forEach(([author, at]) => {
        if (at < lastChange) {
            versions.push({
                id: `author:${author}`,
                kind: "author",
                author,
                label: `As ${author} left it`,
                at,
            });
        }
    });
    versions.push({ id: "current", kind: "current", label: "Current text", at: lastChange });
    return versions;
}

function findLast(states, predicate) {
    for (let i = states.length - 1; i >= 0; i--) {
        if (predicate(states[i])) return states[i];
    }
    return null;
}

/**
 * The text of a line in a version of the page, from the line's history:
 * { status: "text", text }, or { status: "none" } if the line had no text in
 * that version, or { status: "unknown" } if that version is older than the
 * history kept for the line.
 */
export function lineTextIn(history, version) {
    const { states, truncated } = history;
    let found;
    switch (version.kind) {
        case "current":
            found = states[states.length - 1];
            return found ? textCell(found.content) : NO_TEXT;
        case "model":
            found = findLast(states, (state) => state.source === MODEL_PREFIX + version.model);
            break;
        case "import":
            found = findLast(states, (state) => stateKind(state) === "import");
            break;
        case "author":
            // the latest text before the end of that person's last edit
            found = findLast(states, (state) => state.at <= version.at);
            break;
        default:
            return UNKNOWN;
    }
    if (found) return textCell(found.content);
    // the older states that were dropped might have had it
    return truncated ? UNKNOWN : NO_TEXT;
}

/**
 * The text of `after` compared to `before`, character by character:
 * [{ type: "same" | "added" | "removed", text }].
 */
export function diffText(before, after) {
    return diffChars(before, after).filter((part) => part.value).map((part) => {
        let type = "same";
        if (part.added) type = "added";
        else if (part.removed) type = "removed";
        return { type, text: part.value };
    });
}

/**
 * Levenshtein distance between two texts, in characters (code points): the
 * fewest insertions, deletions and substitutions turning one into the other.
 */
export function editDistance(a, b) {
    const s = Array.from(a);
    const t = Array.from(b);
    if (!s.length) return t.length;
    if (!t.length) return s.length;
    let previous = Array.from({ length: t.length + 1 }, (_, j) => j);
    for (let i = 1; i <= s.length; i++) {
        const row = [i];
        for (let j = 1; j <= t.length; j++) {
            row[j] = Math.min(
                previous[j] + 1,
                row[j - 1] + 1,
                previous[j - 1] + (s[i - 1] === t[j - 1] ? 0 : 1),
            );
        }
        previous = row;
    }
    return previous[t.length];
}

/**
 * Whether two cells of a row can be compared: both lines had text.
 */
const comparable = (a, b) => a.status === "text" && b.status === "text";

/**
 * Whether the text of a line differs between two versions. A line that has text
 * in one and none in the other differs; one older than the kept history does
 * not, as its text is not known.
 */
function differs(a, b) {
    if (a.status === "unknown" || b.status === "unknown") return false;
    return a.status !== b.status || a.text !== b.text;
}

/**
 * The rows of the comparison of `versions` (from pageVersions), one per line
 * in reading order: { pk, number, cells, changed }. `lines` are
 * { pk, order, history }. From the second one on, each cell has the diff of
 * its text with the cell on its left in `parts`, when both have text.
 */
export function compareRows(lines, versions) {
    return [...lines]
        .sort((a, b) => a.order - b.order)
        .map((line) => {
            const cells = versions.map((version) => ({ ...lineTextIn(line.history, version) }));
            let changed = false;
            cells.forEach((cell, i) => {
                if (i === 0) return;
                const left = cells[i - 1];
                cell.parts = comparable(left, cell) ? diffText(left.text, cell.text) : null;
                changed = changed || differs(left, cell);
            });
            return { pk: line.pk, number: line.order + 1, cells, changed };
        });
}

/**
 * Compare the columns `left` and `right` (indexes in the cells) over the rows:
 * - `compared`: lines with text in both
 * - `changed`: lines among them whose text differs
 * - `skipped`: lines without text in one of them, or too old to know
 * - `edits`: characters to insert, delete or substitute to turn the left text
 *   of these lines into the right one
 * - `referenceLength`: characters of the right text of these lines
 * - `cer`: the character error rate of the left column taking the right one as
 *   the reference: edits / referenceLength, or null without reference text
 */
export function compareColumns(rows, left, right) {
    let compared = 0;
    let changed = 0;
    let edits = 0;
    let referenceLength = 0;
    rows.forEach((row) => {
        const a = row.cells[left];
        const b = row.cells[right];
        if (!comparable(a, b)) return;
        compared += 1;
        if (a.text !== b.text) {
            changed += 1;
            edits += editDistance(a.text, b.text);
        }
        referenceLength += Array.from(b.text).length;
    });
    return {
        compared,
        changed,
        skipped: rows.length - compared,
        edits,
        referenceLength,
        cer: referenceLength ? edits / referenceLength : null,
    };
}

/**
 * The versions shown in the columns, from the ids chosen before, possibly on
 * another page: an id not available on this page is replaced by the default of
 * its column. The default is the oldest version on the left, the current text
 * on the right, and a version not shown yet in between.
 */
export function chooseColumns(ids, versions) {
    const byId = new Map(versions.map((version) => [version.id, version]));
    const current = versions[versions.length - 1];
    const wanted = ids.length >= 2 ? ids.slice(0, MAX_COLUMNS) : [versions[0].id, current.id];
    const columns = wanted.map((id) => byId.get(id) || null);
    columns.forEach((column, i) => {
        if (column) return;
        if (i === 0) columns[i] = versions[0];
        else if (i === columns.length - 1) columns[i] = current;
        else columns[i] = versions.find((version) => !columns.includes(version)) || current;
    });
    return columns;
}

/**
 * The version to show in a column added before the last one: the latest one
 * older than the version of the last column and not shown yet, else the
 * current text.
 */
export function versionToAdd(columns, versions) {
    const last = columns[columns.length - 1];
    const candidates = versions.filter(
        (version) => !columns.includes(version) && version.at <= last.at,
    );
    return candidates.length ? candidates[candidates.length - 1] : versions[versions.length - 1];
}
