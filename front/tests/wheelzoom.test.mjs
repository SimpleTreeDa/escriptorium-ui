// Run with `npm test` (Node 22 or later, no other dependency).
/* global globalThis */
import assert from "node:assert/strict";
import { before, describe, test } from "node:test";
import { WheelZoom, zoomedPosition } from "../src/wheelzoom.js";

before(() => {
    // just enough DOM for the WheelZoom constructor and its events
    if (globalThis.document) return;
    globalThis.document = {
        createElement: () => ({
            classList: { add() {} },
            addEventListener() {},
            dispatchEvent() {},
        }),
        body: { appendChild() {} },
        documentElement: { scrollLeft: 0, scrollTop: 0 },
    };
});

/**
 * A panel showing the page fitted to its width (what register() would wrap).
 */
function fakePanel(width) {
    return {
        container: {
            clientWidth: width,
            isConnected: true,
            getBoundingClientRect: () => ({ x: 0, y: 0, width, height: width * 1.4 }),
        },
        element: { getBoundingClientRect: () => ({ width, height: width * 1.4 }) },
        update(pos, scale) {
            this.pos = pos;
            this.scale = scale;
        },
        showMap() {},
    };
}

/**
 * Wheel event at (x, y) pixels in a panel whose top left is at (0, 0): the
 * event target is the zoomed page, whose top left is at the zoom position.
 */
const wheel = (zoom, panel, x, y, delta = 1) => ({
    preventDefault() {},
    wheelDelta: delta,
    pageX: x,
    pageY: y,
    target: { getBoundingClientRect: () => zoom.pixelPos(panel) },
});

/**
 * The point of the page, as a fraction of its width, shown at (x, y) pixels
 * in this panel
 */
function pageFractionAt(zoom, panel, x, y) {
    const pos = zoom.pixelPos(panel);
    const width = panel.container.clientWidth;
    return {
        x: (x - pos.x) / (zoom.scale * width),
        y: (y - pos.y) / (zoom.scale * width),
    };
}

function assertClose(actual, expected, tolerance, message) {
    assert.ok(
        Math.abs(actual - expected) <= tolerance,
        `${message}: ${actual} vs ${expected}`,
    );
}

describe("zoomedPosition", () => {
    test("the point under the cursor stays where it is", () => {
        const pos = { x: -30, y: -12 };
        const point = { x: 140, y: 90 }; // from the zoomed element's top left
        const oldScale = 1.5;
        const newScale = 2.4;
        const next = zoomedPosition(pos, point, newScale / oldScale);
        // the page point under the cursor, before and after
        const cursor = { x: pos.x + point.x, y: pos.y + point.y };
        assertClose((cursor.x - next.x) / newScale, point.x / oldScale, 1e-9, "x");
        assertClose((cursor.y - next.y) / newScale, point.y / oldScale, 1e-9, "y");
    });

    test("rounds when asked to", () => {
        const next = zoomedPosition({ x: 0, y: 0 }, { x: 101, y: 33 }, 1.1, Math.round);
        assert.ok(Number.isInteger(next.x) && Number.isInteger(next.y));
    });
});

describe("WheelZoom in the new UI (panels of different widths)", () => {
    test("zooming in a panel shows the same part of the page in every panel", () => {
        const zoom = new WheelZoom({ legacyModeEnabled: false });
        const wide = fakePanel(800);
        const narrow = fakePanel(400);
        zoom.targets.push(wide, narrow);

        const before = pageFractionAt(zoom, wide, 300, 200);
        zoom.scrolling = wide;
        zoom.scrolled(wheel(zoom, zoom.scrolling, 300, 200));
        zoom.scrolling = wide;
        zoom.scrolled(wheel(zoom, zoom.scrolling, 300, 200));
        assert.ok(zoom.scale > 1);

        // the point under the cursor didn't move (within a rounded pixel)
        const after = pageFractionAt(zoom, wide, 300, 200);
        assertClose(after.x, before.x, 1 / 800, "cursor x");
        assertClose(after.y, before.y, 1 / 800, "cursor y");

        // the narrow panel shows that point at the same place, relative to its width
        const inNarrow = pageFractionAt(zoom, narrow, 150, 100);
        assertClose(inNarrow.x, after.x, 1 / 400, "narrow x");
        assertClose(inNarrow.y, after.y, 1 / 400, "narrow y");

        // and each panel received its own pixel position
        assert.deepEqual(wide.pos, zoom.pixelPos(wide));
        assert.deepEqual(narrow.pos, zoom.pixelPos(narrow));
    });

    test("dragging moves every panel by the same part of the page", () => {
        const zoom = new WheelZoom({ legacyModeEnabled: false, getActiveTool: () => "pan" });
        const wide = fakePanel(800);
        const narrow = fakePanel(400);
        zoom.targets.push(wide, narrow);

        zoom.dragging = narrow;
        zoom.previousEvent = { pageX: 0, pageY: 0 };
        zoom.drag({ preventDefault() {}, pageX: 40, pageY: 20 });

        assert.deepEqual(narrow.pos, { x: 40, y: 20 });
        assert.deepEqual(wide.pos, { x: 80, y: 40 });
    });

    test("resizing a panel keeps the same part of the page in view", () => {
        const zoom = new WheelZoom({ legacyModeEnabled: false });
        const panel = fakePanel(600);
        zoom.targets.push(panel);
        zoom.scrolling = panel;
        zoom.scrolled(wheel(zoom, zoom.scrolling, 200, 300));
        const before = pageFractionAt(zoom, panel, 0, 0);

        panel.container.clientWidth = 900;
        zoom.refresh();
        const after = pageFractionAt(zoom, panel, 0, 0);
        assertClose(after.x, before.x, 1 / 600, "x");
        assertClose(after.y, before.y, 1 / 600, "y");
        assert.deepEqual(panel.pos, zoom.pixelPos(panel));
    });
});

describe("WheelZoom in the legacy UI", () => {
    test("keeps the position in pixels, rounded, the same for every panel", () => {
        const zoom = new WheelZoom({ legacyModeEnabled: true });
        const a = fakePanel(800);
        const b = fakePanel(400);
        zoom.targets.push(a, b);

        zoom.scrolling = a;
        zoom.scrolled(wheel(zoom, zoom.scrolling, 300, 200));
        const ratio = zoom.scale;
        // same as before panels could have different widths
        assert.deepEqual(zoom.pos, {
            x: -Math.round((300 - 300 / ratio) * ratio),
            y: -Math.round((200 - 200 / ratio) * ratio),
        });
        assert.equal(zoom.pixelPos(a), zoom.pos);
        assert.deepEqual(a.pos, zoom.pos);
        assert.deepEqual(b.pos, zoom.pos);
    });
});
