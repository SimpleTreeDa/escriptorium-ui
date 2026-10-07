// Run with `npm test` (Node 22 or later, with the dependencies of front/ installed).
import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
    MAX_COLUMNS,
    MAX_KEPT_VERSIONS,
    chooseColumns,
    compareColumns,
    compareRows,
    diffText,
    editDistance,
    lineHistory,
    lineTextIn,
    pageVersions,
    stateKind,
    versionToAdd,
} from "../src/editor/versionCompare.js";

const at = (time) => `2026-10-07T${time}:00.000000+00:00`;
const ms = (time) => Date.parse(at(time));

/** An earlier version of a line, as the API returns it in `versions` */
const version = (content, source, author, time) => ({
    revision: `${content}-${time}`,
    source,
    author,
    created_at: at(time),
    updated_at: at(time),
    data: { content, graphs: null, avg_confidence: null },
});

/** A line transcription as the API returns it; `versions` newest first */
const trans = (content, source, author, time, versions = []) => ({
    pk: 1,
    line: 1,
    transcription: 1,
    content,
    versions,
    version_source: source,
    version_author: author,
    version_updated_at: at(time),
});

const MODEL = "kraken:syr_print_seg03";
const EDIT = "eScriptorium";

/**
 * A page transcribed by a model at 09:00, corrected by maria (the transcriber)
 * until 10:30, then revised by john (the editor) at 12:00.
 */
function samplePage() {
    const transcriptions = [
        // corrected by maria, then john
        trans("Hello, world", EDIT, "john", "12:00", [
            version("Hello world", EDIT, "maria", "10:00"),
            version("Hello wrld", MODEL, "maria", "09:00"),
        ]),
        // corrected by maria
        trans("Second lines", EDIT, "maria", "10:30", [
            version("Second line", MODEL, "maria", "09:00"),
        ]),
        // drawn and transcribed by maria after the model ran
        trans("Added line", EDIT, "maria", "10:15"),
        // the model output, never corrected
        trans("Fourth", MODEL, "maria", "09:00"),
    ];
    // in the store, lines are not necessarily in reading order
    const orders = [0, 1, 2, 3];
    return transcriptions
        .map((t, i) => ({ pk: 100 + i, order: orders[i], history: lineHistory(t) }))
        .reverse();
}

const byId = (versions) => Object.fromEntries(versions.map((v) => [v.id, v]));

describe("stateKind", () => {
    test("tells model output, imported text and edits apart", () => {
        assert.equal(stateKind({ source: "kraken:catmus" }), "model");
        assert.equal(stateKind({ source: "import" }), "import");
        assert.equal(stateKind({ source: "eScriptorium" }), "edit");
        assert.equal(stateKind({ source: "" }), "edit");
    });
});

describe("lineHistory", () => {
    test("lists the states oldest first, the current text last", () => {
        const { states, truncated } = lineHistory(trans("c", EDIT, "john", "12:00", [
            version("b", EDIT, "maria", "10:00"),
            version("a", MODEL, "maria", "09:00"),
        ]));
        assert.deepEqual(states, [
            { content: "a", source: MODEL, author: "maria", at: ms("09:00") },
            { content: "b", source: EDIT, author: "maria", at: ms("10:00") },
            { content: "c", source: EDIT, author: "john", at: ms("12:00") },
        ]);
        assert.equal(truncated, false);
    });

    test("is truncated when the server kept the most versions it keeps", () => {
        const versions = Array.from({ length: MAX_KEPT_VERSIONS }, (_, i) => (
            version(`v${i}`, EDIT, "maria", "10:00")
        ));
        assert.equal(lineHistory(trans("c", EDIT, "maria", "11:00", versions)).truncated, true);
        assert.equal(
            lineHistory(trans("c", EDIT, "maria", "11:00", versions.slice(1))).truncated,
            false,
        );
    });

    test("is empty for a line without text in the transcription", () => {
        // the default the editor sets before loading the text, see fetchContent
        const none = {
            line: 1, transcription: 1, content: "",
            version_author: null, version_source: null, version_updated_at: null,
        };
        assert.deepEqual(lineHistory(none), { states: [], truncated: false });
        assert.deepEqual(lineHistory(undefined), { states: [], truncated: false });
    });

    test("puts text not saved yet after everything else", () => {
        const unsaved = { content: "typed", version_source: null, version_author: null };
        assert.deepEqual(lineHistory(unsaved).states, [
            { content: "typed", source: "", author: "", at: Infinity },
        ]);
    });

    test("reads a version without content as empty", () => {
        const broken = { ...version("x", EDIT, "maria", "10:00"), data: {} };
        const { states } = lineHistory(trans("y", EDIT, "maria", "11:00", [broken]));
        assert.equal(states[0].content, "");
    });
});

describe("pageVersions", () => {
    test("offers the model output, the page as maria left it, and the current text", () => {
        const versions = pageVersions(samplePage().map((line) => line.history));
        assert.deepEqual(versions, [
            {
                id: "model:syr_print_seg03", kind: "model", model: "syr_print_seg03",
                label: "Model output (syr_print_seg03)", at: ms("09:00"),
            },
            {
                id: "author:maria", kind: "author", author: "maria",
                label: "As maria left it", at: ms("10:30"),
            },
            { id: "current", kind: "current", label: "Current text", at: ms("12:00") },
        ]);
    });

    test("leaves out the page as the last person left it: it is the current text", () => {
        const ids = pageVersions(samplePage().map((line) => line.history)).map((v) => v.id);
        assert.ok(!ids.includes("author:john"));
    });

    test("offers each model, by time of its first output, and the imported text", () => {
        const histories = [
            lineHistory(trans("c", "kraken:second", "maria", "11:00", [
                version("b", "kraken:first", "maria", "10:00"),
                version("a", "import", "", "09:00"),
            ])),
        ];
        const ids = pageVersions(histories).map((v) => v.id);
        assert.deepEqual(ids, ["model:first", "model:second", "import", "current"]);
    });

    test("does not offer edits without an author", () => {
        const histories = [lineHistory(trans("b", EDIT, "maria", "11:00", [
            version("a", EDIT, "", "10:00"),
        ]))];
        assert.deepEqual(pageVersions(histories).map((v) => v.id), ["current"]);
    });

    test("offers only the current text for a page without text", () => {
        assert.deepEqual(pageVersions([]).map((v) => v.id), ["current"]);
    });
});

describe("lineTextIn", () => {
    const page = samplePage().sort((a, b) => a.order - b.order);
    const versions = byId(pageVersions(page.map((line) => line.history)));
    const texts = (id) => page.map((line) => lineTextIn(line.history, versions[id]));

    test("gives the model output of each line", () => {
        assert.deepEqual(texts("model:syr_print_seg03"), [
            { status: "text", text: "Hello wrld" },
            { status: "text", text: "Second line" },
            { status: "none", text: "" },
            { status: "text", text: "Fourth" },
        ]);
    });

    test("gives the page as someone left it", () => {
        assert.deepEqual(texts("author:maria").map((cell) => cell.text), [
            "Hello world", "Second lines", "Added line", "Fourth",
        ]);
    });

    test("gives the current text", () => {
        assert.deepEqual(texts("current").map((cell) => cell.text), [
            "Hello, world", "Second lines", "Added line", "Fourth",
        ]);
    });

    test("has no text for a line drawn after that version", () => {
        const history = lineHistory(trans("new", EDIT, "john", "12:00"));
        const before = { id: "author:maria", kind: "author", author: "maria", at: ms("10:30") };
        assert.deepEqual(lineTextIn(history, before), { status: "none", text: "" });
    });

    test("does not know a version older than the history kept", () => {
        const versions = Array.from({ length: MAX_KEPT_VERSIONS }, (_, i) => (
            version(`edit ${i}`, EDIT, "john", "11:00")
        ));
        const history = lineHistory(trans("last", EDIT, "john", "12:00", versions));
        const model = { id: "model:x", kind: "model", model: "x", at: ms("09:00") };
        const maria = { id: "author:maria", kind: "author", author: "maria", at: ms("10:30") };
        assert.deepEqual(lineTextIn(history, model), { status: "unknown", text: "" });
        assert.deepEqual(lineTextIn(history, maria), { status: "unknown", text: "" });
    });

    test("finds a version still in a truncated history", () => {
        const versions = [
            ...Array.from({ length: MAX_KEPT_VERSIONS - 1 }, (_, i) => (
                version(`edit ${i}`, EDIT, "john", "11:00")
            )),
            version("model text", MODEL, "maria", "09:00"),
        ];
        const history = lineHistory(trans("last", EDIT, "john", "12:00", versions));
        const model = { id: "model:m", kind: "model", model: "syr_print_seg03", at: ms("09:00") };
        assert.deepEqual(lineTextIn(history, model), { status: "text", text: "model text" });
    });

    test("gives the latest output of a model that ran twice", () => {
        const history = lineHistory(trans("edited", EDIT, "maria", "12:00", [
            version("second run", MODEL, "maria", "11:00"),
            version("first run", MODEL, "maria", "09:00"),
        ]));
        const model = { id: "model:m", kind: "model", model: "syr_print_seg03", at: ms("09:00") };
        assert.equal(lineTextIn(history, model).text, "second run");
    });

    test("has no text for a line without text at all", () => {
        const current = { id: "current", kind: "current", at: 0 };
        assert.deepEqual(lineTextIn({ states: [], truncated: false }, current), {
            status: "none", text: "",
        });
    });
});

describe("diffText", () => {
    test("marks the characters added and removed", () => {
        assert.deepEqual(diffText("Hello wrld", "Hello, world"), [
            { type: "same", text: "Hello" },
            { type: "added", text: "," },
            { type: "same", text: " w" },
            { type: "added", text: "o" },
            { type: "same", text: "rld" },
        ]);
        assert.deepEqual(diffText("cat", "cut"), [
            { type: "same", text: "c" },
            { type: "removed", text: "a" },
            { type: "added", text: "u" },
            { type: "same", text: "t" },
        ]);
    });

    test("has one part for the same text", () => {
        assert.deepEqual(diffText("ܫܠܡܐ", "ܫܠܡܐ"), [{ type: "same", text: "ܫܠܡܐ" }]);
    });

    test("handles empty texts", () => {
        assert.deepEqual(diffText("", "new"), [{ type: "added", text: "new" }]);
        assert.deepEqual(diffText("old", ""), [{ type: "removed", text: "old" }]);
        assert.deepEqual(diffText("", ""), []);
    });

    test("keeps markup as text", () => {
        const parts = diffText("a", "a<img src=x onerror=alert(1)>");
        assert.deepEqual(parts, [
            { type: "same", text: "a" },
            { type: "added", text: "<img src=x onerror=alert(1)>" },
        ]);
    });
});

describe("editDistance", () => {
    test("counts insertions, deletions and substitutions", () => {
        assert.equal(editDistance("kitten", "sitting"), 3);
        assert.equal(editDistance("Hello wrld", "Hello, world"), 2);
        assert.equal(editDistance("abc", "abc"), 0);
    });

    test("is the length of the other text when one is empty", () => {
        assert.equal(editDistance("", "abc"), 3);
        assert.equal(editDistance("abc", ""), 3);
        assert.equal(editDistance("", ""), 0);
    });

    test("counts characters, not UTF-16 units", () => {
        assert.equal(editDistance("a𝔄b", "ab"), 1);
        assert.equal(editDistance("𝔄", "𝔅"), 1);
    });

    test("is symmetric", () => {
        assert.equal(editDistance("ܫܠܡܐ ܥܠܡܐ", "ܫܠܡ ܥܠܡܐ"), editDistance("ܫܠܡ ܥܠܡܐ", "ܫܠܡܐ ܥܠܡܐ"));
    });
});

describe("compareRows", () => {
    const page = samplePage();
    const versions = byId(pageVersions(page.map((line) => line.history)));
    const columns = [versions["model:syr_print_seg03"], versions["author:maria"], versions.current];
    const rows = compareRows(page, columns);

    test("has a row per line, in reading order, numbered from 1", () => {
        assert.deepEqual(rows.map((row) => [row.pk, row.number]), [
            [100, 1], [101, 2], [102, 3], [103, 4],
        ]);
    });

    test("compares each column with the one on its left", () => {
        const [first, second, third] = rows[0].cells;
        assert.equal(first.parts, undefined);
        assert.deepEqual(second.parts, diffText("Hello wrld", "Hello world"));
        assert.deepEqual(third.parts, diffText("Hello world", "Hello, world"));
    });

    test("has no diff next to a line without text", () => {
        const [model, maria] = rows[2].cells;
        assert.equal(model.status, "none");
        assert.equal(maria.parts, null);
    });

    test("tells which lines changed", () => {
        assert.deepEqual(rows.map((row) => row.changed), [true, true, true, false]);
    });

    test("does not count a line older than the history kept as changed", () => {
        const versionsKept = Array.from({ length: MAX_KEPT_VERSIONS }, () => (
            version("same", EDIT, "john", "11:00")
        ));
        const line = {
            pk: 1, order: 0,
            history: lineHistory(trans("same", EDIT, "john", "12:00", versionsKept)),
        };
        const [row] = compareRows([line], [versions["model:syr_print_seg03"], versions.current]);
        assert.equal(row.cells[0].status, "unknown");
        assert.equal(row.changed, false);
    });

    test("does not change the cells of other rows", () => {
        const again = compareRows(page, columns);
        assert.deepEqual(again, rows);
    });
});

describe("compareColumns", () => {
    const page = samplePage();
    const versions = byId(pageVersions(page.map((line) => line.history)));
    const rows = compareRows(page, [
        versions["model:syr_print_seg03"], versions["author:maria"], versions.current,
    ]);

    test("counts the lines changed and the character error rate", () => {
        // model output against the current text: 2 + 1 + 0 edits for 12 + 12 + 6
        // characters, the line added later is not compared
        assert.deepEqual(compareColumns(rows, 0, 2), {
            compared: 3, changed: 2, skipped: 1, edits: 3, referenceLength: 30, cer: 3 / 30,
        });
    });

    test("compares any two columns", () => {
        // maria's text against the current text: john added a comma
        assert.deepEqual(compareColumns(rows, 1, 2), {
            compared: 4, changed: 1, skipped: 0, edits: 1, referenceLength: 40, cer: 1 / 40,
        });
    });

    test("has no error rate without reference text", () => {
        const empty = [{ cells: [{ status: "text", text: "abc" }, { status: "text", text: "" }] }];
        assert.equal(compareColumns(empty, 0, 1).cer, null);
        assert.deepEqual(compareColumns([], 0, 1), {
            compared: 0, changed: 0, skipped: 0, edits: 0, referenceLength: 0, cer: null,
        });
    });

    test("is zero for the same text", () => {
        const abc = { status: "text", text: "abc" };
        const same = [{ cells: [abc, abc] }];
        assert.equal(compareColumns(same, 0, 1).cer, 0);
    });
});

describe("chooseColumns", () => {
    const versions = pageVersions(samplePage().map((line) => line.history));
    const [model, maria, current] = versions;

    test("compares the oldest version with the current text by default", () => {
        assert.deepEqual(chooseColumns([], versions), [model, current]);
    });

    test("keeps the versions chosen", () => {
        assert.deepEqual(chooseColumns(["author:maria", "current"], versions), [maria, current]);
        assert.deepEqual(
            chooseColumns(["model:syr_print_seg03", "author:maria", "current"], versions),
            [model, maria, current],
        );
    });

    test("replaces a version missing on this page by the default of its column", () => {
        assert.deepEqual(chooseColumns(["author:paul", "current"], versions), [model, current]);
        assert.deepEqual(chooseColumns(["model:other", "author:paul"], versions), [model, current]);
        assert.deepEqual(
            chooseColumns(["model:syr_print_seg03", "author:paul", "current"], versions),
            [model, maria, current],
        );
    });

    test("shows at most MAX_COLUMNS columns", () => {
        const ids = ["current", "current", "current", "current"];
        assert.equal(chooseColumns(ids, versions).length, MAX_COLUMNS);
    });
});

describe("versionToAdd", () => {
    const versions = pageVersions(samplePage().map((line) => line.history));
    const [model, maria, current] = versions;

    test("adds the latest version older than the last column and not shown", () => {
        assert.equal(versionToAdd([model, current], versions), maria);
    });

    test("adds the current text when every older version is shown", () => {
        assert.equal(versionToAdd([model, maria], versions), current);
    });
});
