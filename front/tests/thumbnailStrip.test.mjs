// Run with `npm test` (Node 22 or later, no other dependency).
import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
    COLLAPSED_HEIGHT,
    EXPANDED_HEIGHT,
    PROFILE_KEY,
    currentIndex,
    loadCollapsed,
    savedState,
    sortedPages,
    stripHeight,
    withPageName,
} from "../src/editor/thumbnailStrip.js";

const page = (pk, order, extra = {}) => ({
    pk, order, name: `p${pk}`, filename: `${pk}.jpg`, ...extra,
});

describe("collapsed state", () => {
    test("expanded by default", () => {
        assert.equal(loadCollapsed(undefined), false);
        assert.equal(loadCollapsed(null), false);
        assert.equal(loadCollapsed({}), false);
    });

    test("what was saved", () => {
        assert.equal(loadCollapsed({ collapsed: true }), true);
        assert.equal(loadCollapsed({ collapsed: false }), false);
        assert.equal(loadCollapsed(savedState(true)), true);
        assert.equal(loadCollapsed(savedState(false)), false);
    });

    test("anything unexpected means expanded", () => {
        const unexpected = [
            true, "true", 1, "collapsed", [], { collapsed: "yes" }, { collapsed: 1 },
        ];
        for (const saved of unexpected) {
            assert.equal(loadCollapsed(saved), false, JSON.stringify(saved));
        }
    });

    test("the saved state is a plain object with a boolean", () => {
        assert.deepEqual(savedState(true), { collapsed: true });
        assert.deepEqual(savedState(false), { collapsed: false });
        assert.deepEqual(savedState(undefined), { collapsed: false });
        assert.deepEqual(savedState(1), { collapsed: true });
        assert.equal(PROFILE_KEY, "editor-thumbnail-strip");
    });
});

describe("toggling", () => {
    test("collapsing and opening again round-trip through the saved state", () => {
        let collapsed = loadCollapsed(undefined);
        assert.equal(collapsed, false);
        // collapse: saved, and read back as collapsed
        collapsed = loadCollapsed(savedState(!collapsed));
        assert.equal(collapsed, true);
        // open again: saved, and read back as expanded
        collapsed = loadCollapsed(savedState(!collapsed));
        assert.equal(collapsed, false);
    });
});

describe("stripHeight", () => {
    test("the thumbnails, or the bar with the toggle when collapsed", () => {
        assert.equal(stripHeight(false), `${EXPANDED_HEIGHT}px`);
        assert.equal(stripHeight(true), `${COLLAPSED_HEIGHT}px`);
    });

    test("the collapsed strip keeps room for the button that opens it", () => {
        assert.ok(COLLAPSED_HEIGHT >= 32, "a small button is 32px high");
        assert.ok(COLLAPSED_HEIGHT < EXPANDED_HEIGHT);
        assert.equal(EXPANDED_HEIGHT, 96);
    });

    test("nothing when the strip is not shown (legacy UI)", () => {
        assert.equal(stripHeight(false, false), "0px");
        assert.equal(stripHeight(true, false), "0px");
    });
});

describe("sortedPages", () => {
    test("pages in reading order", () => {
        const pages = [page(3, 2), page(1, 0), page(2, 1)];
        assert.deepEqual(sortedPages(pages).map((p) => p.pk), [1, 2, 3]);
        // the input is not changed
        assert.deepEqual(pages.map((p) => p.pk), [3, 1, 2]);
    });

    test("pages without a pk or a position are left out", () => {
        const pages = [page(1, 0), { pk: 2 }, { order: 3 }, null, page(4, 1, { order: "1" })];
        assert.deepEqual(sortedPages(pages).map((p) => p.pk), [1]);
    });

    test("nothing from nothing", () => {
        assert.deepEqual(sortedPages(undefined), []);
        assert.deepEqual(sortedPages(null), []);
        assert.deepEqual(sortedPages({}), []);
        assert.deepEqual(sortedPages([]), []);
    });
});

describe("currentIndex", () => {
    const pages = [page(10, 0), page(20, 1), page(30, 2)];

    test("the position of the current page in the strip", () => {
        assert.equal(currentIndex(pages, 10), 0);
        assert.equal(currentIndex(pages, 30), 2);
    });

    test("-1 without a current page, or for a page not in the strip", () => {
        assert.equal(currentIndex(pages, null), -1);
        assert.equal(currentIndex(pages, undefined), -1);
        assert.equal(currentIndex(pages, 40), -1);
        assert.equal(currentIndex([], 10), -1);
    });
});

describe("withPageName", () => {
    const pages = [page(10, 0), page(20, 1)];

    test("renames the page without fetching the list again", () => {
        const renamed = withPageName(pages, 20, "f. 2r");
        assert.equal(renamed[1].name, "f. 2r");
        assert.equal(renamed[1].pk, 20);
        assert.equal(renamed[0], pages[0]);
        // the input is not changed
        assert.equal(pages[1].name, "p20");
    });

    test("the same list when nothing changes", () => {
        assert.equal(withPageName(pages, 20, "p20"), pages);
        assert.equal(withPageName(pages, 30, "other"), pages);
        assert.equal(withPageName(pages, null, "other"), pages);
    });
});
