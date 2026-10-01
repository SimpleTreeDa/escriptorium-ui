// Run with `npm test` (Node 22 or later, no other dependency).
import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
    equalSizes,
    loadLayout,
    resizeAt,
    withEqualSizes,
    withOrientation,
    withPanelAdded,
    withPanelRemoved,
    withSizes,
} from "../src/editor/panelLayout.js";

const sum = (sizes) => sizes.reduce((total, size) => total + size, 0);

/** Compare sizes to the expected values, ignoring rounding errors */
function assertSizes(actual, expected) {
    assert.equal(actual.length, expected.length, `${actual} vs ${expected}`);
    actual.forEach((size, i) => {
        assert.ok(Math.abs(size - expected[i]) < 1e-9, `${actual} vs ${expected}`);
    });
}

describe("loadLayout", () => {
    test("nothing saved: side by side, equal sizes", () => {
        assert.deepEqual(loadLayout(undefined, 2), {
            orientation: "row",
            sizes: { row: [0.5, 0.5], column: [0.5, 0.5] },
        });
        assert.deepEqual(loadLayout(null, 3).sizes.row, equalSizes(3));
    });

    test("keeps a valid saved layout", () => {
        const saved = { orientation: "column", sizes: { row: [0.7, 0.3], column: [0.25, 0.75] } };
        assert.deepEqual(loadLayout(saved, 2), saved);
    });

    test("an unknown orientation falls back to side by side", () => {
        assert.equal(loadLayout({ orientation: "diagonal" }, 2).orientation, "row");
        assert.equal(loadLayout({ orientation: 3 }, 2).orientation, "row");
    });

    test("unusable sizes fall back to equal sizes, for each orientation separately", () => {
        const count = 2;
        for (const bad of [
            [0.5], // wrong number of panels
            [0.2, 0.3, 0.5],
            [0.5, NaN],
            [0.5, Infinity],
            [1, 0], // a panel must have some space
            [1.5, -0.5],
            ["0.5", "0.5"],
            "0.5,0.5",
            {},
        ]) {
            const saved = { orientation: "row", sizes: { row: bad, column: [0.4, 0.6] } };
            const layout = loadLayout(saved, count);
            assert.deepEqual(layout.sizes.row, [0.5, 0.5], JSON.stringify(bad));
            assert.deepEqual(layout.sizes.column, [0.4, 0.6]);
        }
    });

    test("sizes that don't add up to 1 are scaled", () => {
        assertSizes(loadLayout({ sizes: { row: [2, 1, 1] } }, 3).sizes.row, [0.5, 0.25, 0.25]);
    });
});

describe("adding, closing and switching panels", () => {
    const layout = { orientation: "row", sizes: { row: [0.7, 0.3], column: [0.2, 0.8] } };

    test("adding a panel makes all panels the same size, in both orientations", () => {
        const added = withPanelAdded(layout, 3);
        assertSizes(added.sizes.row, [1 / 3, 1 / 3, 1 / 3]);
        assertSizes(added.sizes.column, [1 / 3, 1 / 3, 1 / 3]);
        assert.equal(added.orientation, "row");
    });

    test("closing a panel keeps the proportions of the others", () => {
        const three = {
            orientation: "column",
            sizes: { row: [0.5, 0.2, 0.3], column: [0.1, 0.6, 0.3] },
        };
        const closed = withPanelRemoved(three, 1);
        assertSizes(closed.sizes.row, [0.625, 0.375]);
        assertSizes(closed.sizes.column, [0.25, 0.75]);
        assert.equal(closed.orientation, "column");
        assertSizes(withPanelRemoved(closed, 0).sizes.row, [1]);
        assert.deepEqual(withPanelRemoved(withPanelRemoved(closed, 0), 0).sizes.row, []);
    });

    test("orientations keep their own sizes", () => {
        const stacked = withOrientation(layout, "column");
        assert.equal(stacked.orientation, "column");
        assert.deepEqual(stacked.sizes, layout.sizes);
        assert.equal(withOrientation(layout, "sideways"), layout);

        const resized = withSizes(stacked, [0.6, 0.4]);
        assert.deepEqual(resized.sizes, { row: [0.7, 0.3], column: [0.6, 0.4] });
        assert.deepEqual(withEqualSizes(resized).sizes, { row: [0.7, 0.3], column: [0.5, 0.5] });
    });

    test("does not change the layout it is given", () => {
        const copy = structuredClone(layout);
        withPanelAdded(layout, 3);
        withPanelRemoved(layout, 0);
        withSizes(layout, [0.1, 0.9]);
        withEqualSizes(layout);
        assert.deepEqual(layout, copy);
    });
});

describe("resizeAt", () => {
    test("only the two panels next to the handle change", () => {
        const sizes = [0.3, 0.3, 0.4];
        assertSizes(resizeAt(sizes, 0, 0.1), [0.4, 0.2, 0.4]);
        assertSizes(resizeAt(sizes, 1, -0.1), [0.3, 0.2, 0.5]);
        assert.deepEqual(sizes, [0.3, 0.3, 0.4]);
    });

    test("the total stays 1", () => {
        for (const delta of [-1, -0.25, -0.01, 0, 0.01, 0.25, 1]) {
            const sizes = resizeAt([0.2, 0.5, 0.3], 1, delta, 0.1);
            assert.ok(Math.abs(sum(sizes) - 1) < 1e-9, `${delta}: ${sizes}`);
        }
    });

    test("no panel gets smaller than the minimum", () => {
        assertSizes(resizeAt([0.5, 0.5], 0, -0.9, 0.2), [0.2, 0.8]);
        assertSizes(resizeAt([0.5, 0.5], 0, 0.9, 0.2), [0.8, 0.2]);
        // a panel already below the minimum is brought back up
        assertSizes(resizeAt([0.1, 0.9], 0, 0, 0.2), [0.2, 0.8]);
    });

    test("when both minimums don't fit, the two panels share the space", () => {
        assertSizes(resizeAt([0.2, 0.2, 0.6], 0, 0.1, 0.3), [0.2, 0.2, 0.6]);
    });

    test("a handle that doesn't exist changes nothing", () => {
        assert.deepEqual(resizeAt([0.5, 0.5], 1, 0.1), [0.5, 0.5]);
        assert.deepEqual(resizeAt([0.5, 0.5], -1, 0.1), [0.5, 0.5]);
        assert.deepEqual(resizeAt([1], 0, 0.1), [1]);
    });
});
