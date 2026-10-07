// Run with `npm test` (Node 22 or later, no other dependency).
import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { normalizeText, sameText } from "../src/editor/text.js";

describe("normalizeText", () => {
    test("composes decomposed Latin", () => {
        assert.equal(normalizeText("Café"), "Café");
    });

    test("keeps Syriac with vowel points as it is", () => {
        // malkā: mim with pthaha, lamadh, kaph with zqapha, alaph
        const syriac = "ܡܰܠܟܳܐ";
        assert.equal(normalizeText(syriac), syriac);
    });

    test("returns anything else than a string as it is", () => {
        assert.equal(normalizeText(null), null);
        assert.equal(normalizeText(undefined), undefined);
        assert.equal(normalizeText(""), "");
    });
});

describe("sameText", () => {
    test("is true for the same text decomposed and composed", () => {
        assert.ok(sameText("Café", "Café"));
        assert.ok(sameText("Café", "Café"));
    });

    test("is false for different text", () => {
        assert.ok(!sameText("Cafe", "Café"));
    });

    test("takes no text for the empty text", () => {
        assert.ok(sameText(null, ""));
        assert.ok(sameText(undefined, null));
        assert.ok(!sameText(null, "a"));
    });
});
