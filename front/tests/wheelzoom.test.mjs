// Run with `npm test` (Node 22 or later, no other dependency).
/* global globalThis */
import assert from "node:assert/strict";
import { before, describe, test } from "node:test";
import { PAN_SPEED, WheelZoom, validPanSpeed, zoomedPosition } from "../src/wheelzoom.js";

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

// event times, far enough apart not to be taken as one touchpad gesture
let clock = 0;

/**
 * Wheel event at (x, y) pixels in a panel whose top left is at (0, 0): the
 * event target is the zoomed page, whose top left is at the zoom position.
 * By default a notch of a mouse wheel (in Chromium), up (zooming in) for a
 * positive delta.
 */
const wheel = (zoom, panel, x, y, delta = 1, fields = {}) => ({
    preventDefault() {},
    deltaX: 0,
    deltaY: -100 * delta,
    deltaMode: 0,
    wheelDeltaY: 120 * delta,
    ctrlKey: false,
    timeStamp: (clock += 1000),
    pageX: x,
    pageY: y,
    target: { getBoundingClientRect: () => zoom.pixelPos(panel) },
    ...fields,
});

// what browsers send when scrolling with two fingers on a touchpad
const touchpad = (deltaX, deltaY, fields = {}) => ({
    deltaX,
    deltaY,
    wheelDeltaY: -3 * deltaY,
    ...fields,
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

describe("WheelZoom resize observer (new UI)", () => {
    test("redraws when a panel changes size, not when it leaves the page", () => {
        let callback = null;
        globalThis.ResizeObserver = class {
            constructor(fn) {
                callback = fn;
            }
            observe() {}
        };
        try {
            const zoom = new WheelZoom({ legacyModeEnabled: false });
            let refreshed = 0;
            zoom.refresh = () => { refreshed += 1; };
            const entry = (isConnected, width) => ({
                target: { isConnected }, contentRect: { width, height: width },
            });

            // closed, or removed while the next page loads: a redraw at 0x0
            // would break the segmentation view
            callback([entry(false, 0)]);
            callback([entry(true, 0)]);
            assert.equal(refreshed, 0);

            callback([entry(true, 500)]);
            callback([entry(false, 0), entry(true, 300)]);
            assert.equal(refreshed, 2);
        } finally {
            delete globalThis.ResizeObserver;
        }
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

describe("WheelZoom wheel events: mouse wheel, touchpad scrolling and pinching", () => {
    const zoom = new WheelZoom({ legacyModeEnabled: false });
    const event = (fields) => ({ deltaX: 0, deltaY: 0, deltaMode: 0, ...fields });

    test("tells mouse wheels from touchpads", () => {
        // Chromium mouse wheel notches (Windows, Linux)
        assert.ok(zoom.isMouseWheel(event({ deltaY: 100, wheelDeltaY: -120 })));
        assert.ok(zoom.isMouseWheel(event({ deltaY: 53.33, wheelDeltaY: -120 })));
        // Firefox mouse wheel, in lines
        assert.ok(zoom.isMouseWheel(event({ deltaY: 3, deltaMode: 1 })));
        // Chromium touchpad, also with a big delta when swiping fast
        assert.ok(!zoom.isMouseWheel(event({ deltaY: 4, wheelDeltaY: -12 })));
        assert.ok(!zoom.isMouseWheel(event({ deltaY: 40, wheelDeltaY: -120 })));
        // sideways
        assert.ok(!zoom.isMouseWheel(event({ deltaX: 3, deltaY: 100, wheelDeltaY: -120 })));
        // Firefox touchpad, in pixels
        assert.ok(!zoom.isMouseWheel(event({ deltaY: 2.5 })));
        assert.ok(!zoom.isMouseWheel(event({ deltaY: 12 })));
    });

    test("scrolling with two fingers pans every panel, without zooming", () => {
        const zoom = new WheelZoom({ legacyModeEnabled: false });
        const wide = fakePanel(800);
        const narrow = fakePanel(400);
        zoom.targets.push(wide, narrow);
        zoom.scrolling = narrow;
        zoom.scrolled(wheel(zoom, narrow, 100, 100, 1, touchpad(20, 40)));
        assert.equal(zoom.scale, 1);
        // by 3/4 of the distance scrolled
        assert.deepEqual(narrow.pos, { x: -15, y: -30 });
        assert.deepEqual(wide.pos, { x: -30, y: -60 });
    });

    test("pinching zooms by as much as the fingers moved, around the cursor", () => {
        const zoom = new WheelZoom({ legacyModeEnabled: false });
        const panel = fakePanel(800);
        zoom.targets.push(panel);
        const before = pageFractionAt(zoom, panel, 300, 200);
        zoom.scrolling = panel;
        zoom.scrolled(wheel(zoom, panel, 300, 200, 1, touchpad(0, -5, { ctrlKey: true })));
        assertClose(zoom.scale, Math.exp(0.05), 1e-9, "scale");
        const after = pageFractionAt(zoom, panel, 300, 200);
        assertClose(after.x, before.x, 1 / 800, "cursor x");
        assertClose(after.y, before.y, 1 / 800, "cursor y");
    });

    test("a mouse wheel zooms a step for each notch, also with ctrl", () => {
        const zoom = new WheelZoom({ legacyModeEnabled: false });
        const panel = fakePanel(800);
        zoom.targets.push(panel);
        zoom.scrolling = panel;
        zoom.scrolled(wheel(zoom, panel, 300, 200, 1));
        assertClose(zoom.scale, Math.exp(0.1), 1e-9, "zoomed in");
        zoom.scrolled(wheel(zoom, panel, 300, 200, -1, { ctrlKey: true }));
        assertClose(zoom.scale, 1, 1e-9, "zoomed back out");
    });

    test("the events of a touchpad gesture all pan, even ones that look like a mouse", () => {
        const zoom = new WheelZoom({ legacyModeEnabled: false });
        const panel = fakePanel(800);
        zoom.targets.push(panel);
        zoom.scrolling = panel;
        const start = clock;
        zoom.scrolled(wheel(zoom, panel, 0, 0, 1, { ...touchpad(0, 4), timeStamp: start + 1 }));
        // a fast swipe, 16ms later
        zoom.scrolled(wheel(zoom, panel, 0, 0, 1, {
            deltaY: 100, wheelDeltaY: -120, timeStamp: start + 17,
        }));
        assert.equal(zoom.scale, 1);
        assert.deepEqual(panel.pos, { x: 0, y: -78 });
        // after a pause, a mouse wheel zooms again
        zoom.scrolled(wheel(zoom, panel, 0, 0, 1, { timeStamp: start + 600 }));
        assert.ok(zoom.scale > 1);
    });

    test("in the legacy UI, panning keeps the page in view", () => {
        const zoom = new WheelZoom({ legacyModeEnabled: true });
        const panel = fakePanel(600);
        zoom.targets.push(panel);
        zoom.scrolling = panel;
        // the page fits in the panel at this scale: nowhere to pan to
        zoom.scrolled(wheel(zoom, panel, 0, 0, 1, touchpad(-30, -30)));
        assert.deepEqual(zoom.pos, { x: 0, y: 0 });
    });
});

describe("touchpad pan speed setting", () => {
    test("keeps a saved or picked speed within the range", () => {
        assert.equal(validPanSpeed(1.5), 1.5);
        // from a range input
        assert.equal(validPanSpeed("0.8"), 0.8);
        assert.equal(validPanSpeed(10), PAN_SPEED.max);
        assert.equal(validPanSpeed(0), PAN_SPEED.min);
    });

    test("falls back to the default when nothing usable was saved", () => {
        for (const value of [undefined, null, "", "fast", NaN, {}]) {
            assert.equal(validPanSpeed(value), PAN_SPEED.default, String(value));
        }
    });

    test("panning follows a speed changed after creating the zoom", () => {
        const zoom = new WheelZoom({ legacyModeEnabled: false, panSpeed: 1 });
        const panel = fakePanel(400);
        zoom.targets.push(panel);
        zoom.scrolling = panel;
        zoom.scrolled(wheel(zoom, panel, 0, 0, 1, touchpad(0, 40)));
        assert.deepEqual(panel.pos, { x: 0, y: -40 });
        zoom.panSpeed = 0.5;
        zoom.scrolled(wheel(zoom, panel, 0, 0, 1, touchpad(0, 40)));
        assert.deepEqual(panel.pos, { x: 0, y: -60 });
    });
});
