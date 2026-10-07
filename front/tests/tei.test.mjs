// Run with `npm test` (Node 22 or later, no other dependency).
import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { PAGE_ACTIONS, isFolio, isWebAddress, summarizeReadiness } from "../src/tei.js";

describe("page actions", () => {
    test("folios are a number and r or v", () => {
        for (const value of ["1r", "23v", " 94V ", "100 r"]) {
            assert.equal(isFolio(value), true, value);
        }
        for (const value of ["", "r1", "0r", "f. 1r", "12", "1rv"]) {
            assert.equal(isFolio(value), false, value);
        }
    });

    test("work URIs are web addresses", () => {
        assert.equal(isWebAddress("http://syriaca.org/work/1505"), true);
        assert.equal(isWebAddress(" https://syriaca.org/work/1505 "), true);
        assert.equal(isWebAddress("syriaca.org/work/1505"), false);
        assert.equal(isWebAddress("http://syriaca.org/work 1505"), false);
    });

    test("an empty work or work URI removes it, an empty folio is refused", () => {
        assert.equal(PAGE_ACTIONS.work.valid(""), true);
        assert.equal(PAGE_ACTIONS.work_uri.valid(""), true);
        assert.equal(PAGE_ACTIONS.work_uri.valid("syriaca"), false);
        assert.equal(PAGE_ACTIONS.folios.valid(""), false);
    });
});

describe("readiness report", () => {
    const report = {
        ready: false,
        errors: [
            { category: "metadata", message: 'Document: metadata "record_id" is missing' },
            { category: "folio", message: "Page 2 (b.png): no name" },
        ],
        warnings: [
            { category: "types", message: 'Region type "Footnotes" is not in the Ephrem profile' },
        ],
        summary: {
            metadata: { errors: 1, warnings: 0 },
            work: { errors: 0, warnings: 0 },
            folio: { errors: 1, warnings: 0 },
            types: { errors: 0, warnings: 1 },
        },
    };

    test("not ready", () => {
        const summary = summarizeReadiness(report);
        assert.equal(summary.ready, false);
        assert.equal(summary.title, "Not ready: 2 problems to fix (1 warning)");
        assert.deepEqual(
            summary.counts.map((count) => count.label),
            ["Metadata", "Folios", "Region and line types"],
        );
        assert.deepEqual(
            summary.messages.map((message) => message.level),
            ["error", "error", "warning"],
        );
        assert.equal(summary.more, 0);
    });

    test("only the first messages", () => {
        const summary = summarizeReadiness(report, 1);
        assert.equal(summary.messages.length, 1);
        assert.equal(summary.more, 2);
    });

    test("ready", () => {
        const summary = summarizeReadiness({ ready: true, errors: [], warnings: [], summary: {} });
        assert.equal(summary.ready, true);
        assert.equal(summary.title, "Ready for TEI export");
        assert.deepEqual(summary.counts, []);
    });
});
