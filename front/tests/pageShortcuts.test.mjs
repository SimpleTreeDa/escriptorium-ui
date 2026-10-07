// Run with `npm test` (Node 22 or later, no other dependency).
import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { isTypingTarget, pageShortcut, targetOrder } from "../src/editor/pageShortcuts.js";

const key = (name, extra = {}) => ({ key: name, target: { tagName: "DIV" }, ...extra });

describe("pageShortcut", () => {
    test("PageUp and PageDown: previous and next page", () => {
        assert.equal(pageShortcut(key("PageUp")), "previous");
        assert.equal(pageShortcut(key("PageDown")), "next");
    });

    test("Home and End: first and last page", () => {
        assert.equal(pageShortcut(key("Home")), "first");
        assert.equal(pageShortcut(key("End")), "last");
    });

    test("Ctrl+arrows follow the reading direction", () => {
        assert.equal(pageShortcut(key("ArrowLeft", { ctrlKey: true })), "previous");
        assert.equal(pageShortcut(key("ArrowRight", { ctrlKey: true })), "next");
        const rtl = { readDirection: "rtl" };
        assert.equal(pageShortcut(key("ArrowLeft", { ctrlKey: true }), rtl), "next");
        assert.equal(pageShortcut(key("ArrowRight", { ctrlKey: true }), rtl), "previous");
        // the reading direction changes nothing for the other keys
        assert.equal(pageShortcut(key("PageUp"), rtl), "previous");
        assert.equal(pageShortcut(key("Home"), rtl), "first");
    });

    test("arrows without Ctrl are not page shortcuts", () => {
        assert.equal(pageShortcut(key("ArrowLeft")), null);
        assert.equal(pageShortcut(key("ArrowRight")), null);
    });

    test("other keys are not page shortcuts", () => {
        for (const name of ["a", "Enter", "Escape", "ArrowUp", "ArrowDown", " ", "Tab"]) {
            assert.equal(pageShortcut(key(name)), null, name);
        }
        assert.equal(pageShortcut(undefined), null);
        assert.equal(pageShortcut({}), null);
    });

    test("nothing with another modifier: Ctrl+Home, Shift+PageUp, Alt+End...", () => {
        assert.equal(pageShortcut(key("Home", { ctrlKey: true })), null);
        assert.equal(pageShortcut(key("End", { ctrlKey: true })), null);
        assert.equal(pageShortcut(key("PageUp", { ctrlKey: true })), null);
        assert.equal(pageShortcut(key("PageUp", { shiftKey: true })), null);
        assert.equal(pageShortcut(key("End", { altKey: true })), null);
        assert.equal(pageShortcut(key("Home", { metaKey: true })), null);
        assert.equal(pageShortcut(key("ArrowLeft", { ctrlKey: true, shiftKey: true })), null);
    });

    test("nothing while shortcuts are blocked (a dialog, a focused field)", () => {
        for (const name of ["PageUp", "PageDown", "Home", "End"]) {
            assert.equal(pageShortcut(key(name), { blockShortcuts: true }), null, name);
        }
        const ctrlLeft = key("ArrowLeft", { ctrlKey: true });
        assert.equal(pageShortcut(ctrlLeft, { blockShortcuts: true }), null);
    });

    test("nothing while typing in a field or an editable line", () => {
        for (const tagName of ["INPUT", "TEXTAREA", "SELECT"]) {
            assert.equal(pageShortcut(key("Home", { target: { tagName } })), null, tagName);
            assert.equal(pageShortcut(key("PageUp", { target: { tagName } })), null, tagName);
        }
        const line = { tagName: "DIV", isContentEditable: true };
        assert.equal(pageShortcut(key("Home", { target: line })), null);
        assert.equal(pageShortcut(key("End", { target: line })), null);
        assert.equal(pageShortcut(key("PageDown", { target: line })), null);
        assert.equal(pageShortcut(key("ArrowRight", { ctrlKey: true, target: line })), null);
    });

    test("the body and a button are not typing targets", () => {
        assert.equal(pageShortcut(key("End", { target: { tagName: "BODY" } })), "last");
        assert.equal(pageShortcut(key("Home", { target: { tagName: "BUTTON" } })), "first");
        assert.equal(pageShortcut(key("Home", { target: null })), "first");
        const plainDiv = { tagName: "DIV", isContentEditable: false };
        assert.equal(pageShortcut(key("Home", { target: plainDiv })), "first");
    });
});

describe("isTypingTarget", () => {
    test("fields and editable elements", () => {
        assert.equal(isTypingTarget({ tagName: "INPUT" }), true);
        assert.equal(isTypingTarget({ tagName: "TEXTAREA" }), true);
        assert.equal(isTypingTarget({ tagName: "SELECT" }), true);
        assert.equal(isTypingTarget({ tagName: "DIV", isContentEditable: true }), true);
        assert.equal(isTypingTarget({ tagName: "SPAN", isContentEditable: true }), true);
    });

    test("anything else", () => {
        assert.equal(isTypingTarget({ tagName: "DIV" }), false);
        assert.equal(isTypingTarget({ tagName: "BUTTON" }), false);
        assert.equal(isTypingTarget({ tagName: "DIV", isContentEditable: false }), false);
        // not a boolean true: inherit, "true" strings come from the attribute, not the property
        assert.equal(isTypingTarget({ tagName: "DIV", isContentEditable: "inherit" }), false);
        assert.equal(isTypingTarget(null), false);
        assert.equal(isTypingTarget(undefined), false);
    });
});

describe("targetOrder", () => {
    test("first and last page of a document", () => {
        assert.equal(targetOrder("first", { order: 5, partsCount: 10 }), 0);
        assert.equal(targetOrder("last", { order: 5, partsCount: 10 }), 9);
        assert.equal(targetOrder("first", { order: 0, partsCount: 1 }), null);
        assert.equal(targetOrder("last", { order: 3, partsCount: 10 }), 9);
    });

    test("nothing when already there", () => {
        assert.equal(targetOrder("first", { order: 0, partsCount: 10 }), null);
        assert.equal(targetOrder("last", { order: 9, partsCount: 10 }), null);
    });

    test("nothing without pages or a known count", () => {
        assert.equal(targetOrder("first", { order: -1, partsCount: 0 }), null);
        assert.equal(targetOrder("last", { order: -1, partsCount: 0 }), null);
        assert.equal(targetOrder("last", { order: 2, partsCount: undefined }), null);
        assert.equal(targetOrder("last", { order: 2, partsCount: NaN }), null);
        assert.equal(targetOrder("last", { order: 2, partsCount: "10" }), null);
    });

    test("nothing for the other actions", () => {
        assert.equal(targetOrder("previous", { order: 5, partsCount: 10 }), null);
        assert.equal(targetOrder("next", { order: 5, partsCount: 10 }), null);
        assert.equal(targetOrder(null, { order: 5, partsCount: 10 }), null);
    });
});
