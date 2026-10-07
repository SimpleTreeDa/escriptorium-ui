// Run with `npm test` (Node 22 or later, needs `npm ci` for paper).
// Selecting, dragging and adding control points in the segmentation editor,
// driven headless on real paper.js paths.
/* global globalThis */
import assert from "node:assert/strict";
import { before, describe, test } from "node:test";
import paper from "paper";

let Segmenter, SegmenterLine, SegmenterRegion;

before(async () => {
    paper.install(globalThis);
    paper.setup(new paper.Size(1000, 1000));
    paper.settings.handleSize = 10;
    globalThis.paper = paper;
    globalThis.window = globalThis.window || {};
    // the headless view has no item event bookkeeping, and no canvas to
    // measure the region labels
    if (!paper.View.prototype._countItemEvent) {
        paper.View.prototype._countItemEvent = function () {};
    }
    globalThis.PointText = function () {
        return new paper.Path.Rectangle({ point: [0, 0], size: [1, 1], visible: false });
    };
    ({ Segmenter, SegmenterLine, SegmenterRegion } = await import("../src/baseline.editor.js"));
    SegmenterLine.prototype.showOrdering = () => {};
    SegmenterLine.prototype.showDirection = () => {};
});

const P = (x, y) => new paper.Point(x, y);
const mouse = { ctrlKey: false, shiftKey: false, which: 1, button: 0 };

function makeSegmenter(mode) {
    // just the state the selection code uses, without the canvas/DOM setup
    const seg = Object.create(Segmenter.prototype);
    Object.assign(seg, {
        mode,
        newUiEnabled: true,
        activeTool: "select",
        lines: [],
        regions: [],
        selection: { lines: [], segments: [], regions: [] },
        selecting: null,
        hoveringPoint: false,
        showMasks: mode === "masks",
        wideLineStrokes: false,
        baselinesColor: "#0000ff",
        evenMasksColor: "#00ff00",
        oddMasksColor: "#ff0000",
        directionHintColors: {},
        regionColors: { None: "#ff8800" },
        scale: 1,
        img: { naturalWidth: 1000, naturalHeight: 1000 },
        canvas: { style: {} },
        tool: {},
        regionsLayer: new paper.Group(),
        updates: [],
    });
    seg.getRatio = () => 1;
    seg.attachTooltip = () => {};
    seg.trigger = () => {};
    seg.addToUpdateQueue = (update) => seg.updates.push(update);
    seg.resetToolEvents();
    return seg;
}

function twoLines(seg) {
    // A's mask is drawn below B's, they overlap between y=55 and y=60
    const A = new SegmenterLine(0, [[10, 50], [200, 50]],
        [[10, 30], [200, 30], [200, 60], [10, 60]], null, "lr", null, {}, seg);
    const B = new SegmenterLine(1, [[10, 80], [200, 80]],
        [[10, 55], [200, 55], [200, 90], [10, 90]], null, "lr", null, {}, seg);
    seg.lines.push(A, B);
    for (const line of [A, B]) {
        seg.bindLineEvents(line);
        seg.bindMaskEvents(line);
    }
    return { A, B };
}

function twoRegions(seg) {
    const R1 = new SegmenterRegion(0, [[0, 0], [100, 0], [100, 100], [0, 100]], null, {}, seg);
    const R2 = new SegmenterRegion(1, [[50, 50], [150, 50], [150, 150], [50, 150]], null, {}, seg);
    seg.regions.push(R1, R2);
    seg.bindRegionEvents(R1);
    seg.bindRegionEvents(R2);
    return { R1, R2 };
}

// like paperjs: the handler of the item hit (if any), then the tool's
function press(seg, item, x, y) {
    const event = { point: P(x, y), event: mouse };
    if (item) item.emit("mousedown", event);
    seg.tool.onMouseDown(event);
}

function drag(seg, dx, dy) {
    seg.tool.onMouseDrag({ event: mouse, delta: P(dx, dy) });
}

function release(seg, dx = 0, dy = 0) {
    // on mouseup, paperjs gives the delta from the mousedown position
    if (seg.tool.onMouseUp) seg.tool.onMouseUp({ event: mouse, delta: P(dx, dy) });
}

// a whole press, drag and release, from one point to another
function dragFromTo(seg, item, [x1, y1], [x2, y2], modifiers = {}) {
    const event = { ...mouse, ...modifiers };
    const delta = P(x2 - x1, y2 - y1);
    if (item) item.emit("mousedown", { point: P(x1, y1), event });
    seg.tool.onMouseDown({ point: P(x1, y1), event });
    seg.tool.onMouseDrag({ point: P(x2, y2), event, delta });
    if (seg.tool.onMouseUp) seg.tool.onMouseUp({ point: P(x2, y2), event, delta });
}

const maskXs = (line) => line.maskPath.segments.map((s) => Math.round(s.point.x));
const maskYs = (line) => line.maskPath.segments.map((s) => Math.round(s.point.y));
const selectedPoints = (seg) =>
    seg.selection.segments.map((s) => [Math.round(s.point.x), Math.round(s.point.y)]);

describe("selecting control points", () => {
    test("a clicked mask point stays selected after release", () => {
        const seg = makeSegmenter("masks");
        const { A } = twoLines(seg);
        press(seg, A.maskPath, 199, 31);
        release(seg);
        assert.deepEqual(selectedPoints(seg), [[200, 30]]);
        assert.ok(A.selected && A.maskPath.segments[1].point.selected);
    });

    test("a handle sticking out of its mask can be grabbed", () => {
        const seg = makeSegmenter("masks");
        const { A } = twoLines(seg);
        A.select();
        // paperjs hits nothing here, outside the mask
        press(seg, null, 204, 26);
        release(seg);
        assert.deepEqual(selectedPoints(seg), [[200, 30]]);
    });

    test("clicking away from any handle clears the selection", () => {
        const seg = makeSegmenter("masks");
        const { A } = twoLines(seg);
        press(seg, A.maskPath, 199, 31);
        release(seg);
        press(seg, null, 400, 400);
        release(seg);
        assert.deepEqual(selectedPoints(seg), []);
        assert.equal(A.selected, false);
    });

    test("clicking a selected point unselects it, dragging it does not", () => {
        const seg = makeSegmenter("masks");
        const { A } = twoLines(seg);
        press(seg, A.maskPath, 199, 31);
        release(seg);
        press(seg, A.maskPath, 199, 31);
        drag(seg, 5, 0);
        release(seg, 5, 0);
        assert.deepEqual(selectedPoints(seg), [[205, 30]]);
        press(seg, A.maskPath, 204, 31);
        release(seg);
        assert.deepEqual(selectedPoints(seg), []);
    });

    test("unselecting a line also drops its selected points", () => {
        const seg = makeSegmenter("masks");
        const { A } = twoLines(seg);
        press(seg, A.maskPath, 199, 31);
        release(seg);
        A.unselect();
        assert.deepEqual(selectedPoints(seg), []);
    });

    test("a clicked baseline point stays selected", () => {
        const seg = makeSegmenter("lines");
        const { A } = twoLines(seg);
        press(seg, A.baselinePath, 11, 51);
        release(seg);
        assert.deepEqual(selectedPoints(seg), [[10, 50]]);
    });

    test("a clicked region point stays selected", () => {
        const seg = makeSegmenter("regions");
        const { R1 } = twoRegions(seg);
        press(seg, R1.polygonPath, 99, 1);
        release(seg);
        assert.deepEqual(selectedPoints(seg), [[100, 0]]);
    });

    test("hovering a handle outside its path shows the pointer cursor", () => {
        const seg = makeSegmenter("masks");
        const { A } = twoLines(seg);
        A.select();
        seg.tool.onMouseMove({ point: P(204, 26) });
        assert.equal(seg.canvas.style.cursor, "pointer");
        seg.tool.onMouseMove({ point: P(400, 400) });
        assert.equal(seg.canvas.style.cursor, "default");
    });
});

describe("overlapping masks and regions", () => {
    test("the nearest point wins, not the mask on top", () => {
        const seg = makeSegmenter("masks");
        const { A, B } = twoLines(seg);
        // B is hit, but A's corner (200,60) is closer than B's (200,55)
        press(seg, B.maskPath, 199, 59);
        release(seg);
        assert.deepEqual(selectedPoints(seg), [[200, 60]]);
        assert.ok(A.selected && !B.selected);
    });

    test("clicks cycle through the masks under the cursor", () => {
        const seg = makeSegmenter("masks");
        const { A, B } = twoLines(seg);
        const selected = [];
        for (let i = 0; i < 3; i++) {
            press(seg, B.maskPath, 100, 57);
            release(seg);
            selected.push(A.selected ? "A" : B.selected ? "B" : null);
        }
        assert.deepEqual(selected, ["B", "A", "B"]);
    });

    test("dragging moves the selected mask, not the one on top", () => {
        const seg = makeSegmenter("masks");
        const { A, B } = twoLines(seg);
        A.select();
        press(seg, B.maskPath, 190, 58);
        drag(seg, 0, 3);
        release(seg, 0, 3);
        assert.ok(A.selected && !B.selected);
        assert.equal(A.maskPath.segments[2].point.y, 63);
        assert.deepEqual(B.maskPath.segments.map((s) => s.point.y), [55, 55, 90, 90]);
    });

    test("clicks cycle through the regions under the cursor", () => {
        const seg = makeSegmenter("regions");
        const { R1, R2 } = twoRegions(seg);
        const selected = [];
        for (let i = 0; i < 3; i++) {
            press(seg, R2.polygonPath, 75, 75);
            release(seg);
            selected.push(R1.selected ? "R1" : R2.selected ? "R2" : null);
        }
        assert.deepEqual(selected, ["R2", "R1", "R2"]);
    });
});

describe("adding and removing control points", () => {
    test("the add points tool adds on the nearest edge, even outside the mask", () => {
        const seg = makeSegmenter("masks");
        const { A } = twoLines(seg);
        seg.activeTool = "add-points";
        press(seg, null, 100, 27);
        release(seg);
        assert.deepEqual(
            A.maskPath.segments.map((s) => [Math.round(s.point.x), Math.round(s.point.y)]),
            [[10, 30], [100, 30], [200, 30], [200, 60], [10, 60]],
        );
        assert.deepEqual(selectedPoints(seg), [[100, 30]]);
        assert.equal(seg.updates.length, 1);
    });

    test("the add points tool does not duplicate the end of a baseline", () => {
        const seg = makeSegmenter("lines");
        const { A } = twoLines(seg);
        seg.activeTool = "add-points";
        press(seg, A.baselinePath, 204, 50);
        release(seg);
        assert.equal(A.baselinePath.segments.length, 2);
    });

    test("deleting points keeps at least 3 on a mask", () => {
        const seg = makeSegmenter("masks");
        const { A } = twoLines(seg);
        A.select();
        for (const segment of A.maskPath.segments) seg.addToSelection(segment);
        seg.deleteSelectedSegments();
        assert.equal(A.maskPath.segments.length, 3);
    });
});

describe("box select", () => {
    const selectedLines = (seg) =>
        seg.lines.filter((l) => l.selected).map((l) => (l.order ? "B" : "A"));

    test("selects the masks the box touches, not their points", () => {
        const seg = makeSegmenter("masks");
        twoLines(seg);
        seg.activeTool = "box-select";
        dragFromTo(seg, null, [300, 40], [150, 57]);
        assert.deepEqual(selectedLines(seg), ["A", "B"]);
        assert.deepEqual(selectedPoints(seg), []);
    });

    test("can be started on top of a mask, and replaces the selection", () => {
        const seg = makeSegmenter("masks");
        const { A, B } = twoLines(seg);
        seg.activeTool = "box-select";
        dragFromTo(seg, B.maskPath, [100, 85], [120, 88]);
        assert.deepEqual(selectedLines(seg), ["B"]);
        dragFromTo(seg, A.maskPath, [100, 35], [120, 40]);
        assert.deepEqual(selectedLines(seg), ["A"]);
    });

    test("dragging the single selected mask moves it whole", () => {
        const seg = makeSegmenter("masks");
        const { A, B } = twoLines(seg);
        seg.activeTool = "box-select";
        A.select();
        dragFromTo(seg, A.maskPath, [150, 40], [150, 45]);
        assert.deepEqual(maskYs(A), [35, 35, 65, 65]);
        assert.deepEqual(maskYs(B), [55, 55, 90, 90]);
        assert.deepEqual(selectedLines(seg), ["A"]);
    });

    test("ignores points: pressing a selected point moves the mask", () => {
        const seg = makeSegmenter("masks");
        const { A } = twoLines(seg);
        A.select();
        seg.addToSelection(A.maskPath.segments[1]);
        seg.activeTool = "box-select";
        dragFromTo(seg, A.maskPath, [199, 31], [199, 36]);
        assert.deepEqual(maskYs(A), [35, 35, 65, 65]);
        assert.deepEqual(selectedPoints(seg), []);
    });

    test("shift+drag started on the single selected mask selects its points", () => {
        const seg = makeSegmenter("masks");
        const { A } = twoLines(seg);
        A.select();
        dragFromTo(seg, A.maskPath, [150, 40], [210, 65], { shiftKey: true });
        // only A's points, not B's corner (200,55) also in the box
        assert.deepEqual(selectedPoints(seg), [[200, 60]]);
        assert.deepEqual(selectedLines(seg), ["A"]);
    });

    test("shift+drag adds masks, also with the select tool", () => {
        const seg = makeSegmenter("masks");
        const { A } = twoLines(seg);
        A.select();
        dragFromTo(seg, null, [300, 85], [150, 88], { shiftKey: true });
        assert.deepEqual(selectedLines(seg), ["A", "B"]);
        assert.deepEqual(selectedPoints(seg), []);
    });

    test("selects baselines in lines mode and regions in regions mode", () => {
        const lines = makeSegmenter("lines");
        twoLines(lines);
        lines.activeTool = "box-select";
        dragFromTo(lines, null, [50, 45], [60, 85]);
        assert.deepEqual(selectedLines(lines), ["A", "B"]);

        const regions = makeSegmenter("regions");
        const { R1, R2 } = twoRegions(regions);
        regions.activeTool = "box-select";
        dragFromTo(regions, null, [160, 160], [140, 140]);
        assert.ok(!R1.selected && R2.selected);
    });

    test("a click selects only what is under the cursor, or clears", () => {
        const seg = makeSegmenter("masks");
        const { A, B } = twoLines(seg);
        seg.activeTool = "box-select";
        A.select();
        B.select();
        press(seg, B.maskPath, 100, 85);
        release(seg);
        assert.deepEqual(selectedLines(seg), ["B"]);
        press(seg, null, 400, 400);
        release(seg);
        assert.deepEqual(selectedLines(seg), []);
    });

    test("escape cancels the box", () => {
        const seg = makeSegmenter("masks");
        const { A } = twoLines(seg);
        seg.activeTool = "box-select";
        press(seg, A.maskPath, 100, 35);
        seg.tool.onMouseDrag({ point: P(120, 40), event: mouse, delta: P(20, 5) });
        assert.ok(seg.activeBox);
        seg.activeBox.cancel();
        assert.equal(seg.activeBox, null);
        assert.equal(seg.selecting, null);
        assert.equal(seg.tool.onMouseUp, null);
    });
});

describe("moving several at once", () => {
    for (const tool of ["select", "box-select"]) {
        test(`dragging one of several selected masks moves them all (${tool})`, () => {
            const seg = makeSegmenter("masks");
            const { A, B } = twoLines(seg);
            seg.activeTool = tool;
            A.select();
            B.select();
            dragFromTo(seg, A.maskPath, [100, 40], [105, 40]);
            assert.deepEqual(maskXs(A), [15, 205, 205, 15]);
            assert.deepEqual(maskXs(B), [15, 205, 205, 15]);
            assert.ok(A.selected && B.selected);
            assert.equal(seg.updates.length, 2);
        });
    }

    test("a selected mask under the one on top is the one moved", () => {
        const seg = makeSegmenter("masks");
        const { A, B } = twoLines(seg);
        A.select();
        seg.lines.push(new SegmenterLine(2, [[300, 50], [400, 50]],
            [[300, 30], [400, 30], [400, 60], [300, 60]], null, "lr", null, {}, seg));
        seg.lines[2].select();
        // B is on top, A (selected) is under it
        dragFromTo(seg, B.maskPath, [100, 57], [100, 60]);
        assert.deepEqual(maskYs(A), [33, 33, 63, 63]);
        assert.deepEqual(maskYs(B), [55, 55, 90, 90]);
        assert.deepEqual(maskYs(seg.lines[2]), [33, 33, 63, 63]);
    });

    test("dragging one of several selected points moves them all", () => {
        const seg = makeSegmenter("masks");
        const { A } = twoLines(seg);
        A.select();
        seg.addToSelection(A.maskPath.segments[1]);
        seg.addToSelection(A.maskPath.segments[2]);
        dragFromTo(seg, A.maskPath, [199, 31], [199, 26]);
        assert.deepEqual(maskYs(A), [30, 25, 55, 60]);
        assert.deepEqual(selectedPoints(seg), [[200, 25], [200, 55]]);
    });
});

describe("box select points", () => {
    const selectedLines = (seg) =>
        seg.lines.filter((l) => l.selected).map((l) => (l.order ? "B" : "A"));

    test("with nothing selected, selects the points of all masks in the box", () => {
        const seg = makeSegmenter("masks");
        const { A } = twoLines(seg);
        seg.activeTool = "box-select-points";
        dragFromTo(seg, A.maskPath, [190, 25], [210, 95]);
        assert.deepEqual(selectedPoints(seg).sort(),
            [[200, 30], [200, 55], [200, 60], [200, 90]]);
        assert.deepEqual(selectedLines(seg), ["A", "B"]);
    });

    test("with a mask selected, only selects its points", () => {
        const seg = makeSegmenter("masks");
        const { A } = twoLines(seg);
        A.select();
        seg.activeTool = "box-select-points";
        dragFromTo(seg, null, [210, 25], [190, 95]);
        assert.deepEqual(selectedPoints(seg).sort(), [[200, 30], [200, 60]]);
        assert.deepEqual(selectedLines(seg), ["A"]);
    });

    test("selects region points in regions mode", () => {
        const seg = makeSegmenter("regions");
        twoRegions(seg);
        seg.activeTool = "box-select-points";
        dragFromTo(seg, null, [-10, -10], [10, 10]);
        assert.deepEqual(selectedPoints(seg), [[0, 0]]);
    });

    test("dragging a selected point moves the points of all masks, keeping them selected", () => {
        const seg = makeSegmenter("masks");
        const { A, B } = twoLines(seg);
        seg.activeTool = "box-select-points";
        dragFromTo(seg, A.maskPath, [190, 25], [210, 95]);
        dragFromTo(seg, A.maskPath, [199, 31], [204, 31]);
        assert.deepEqual(maskXs(A), [10, 205, 205, 10]);
        assert.deepEqual(maskXs(B), [10, 205, 205, 10]);
        assert.equal(selectedPoints(seg).length, 4);
        assert.deepEqual(selectedLines(seg), ["A", "B"]);
    });

    test("a press away from points draws a box, it does not move the mask", () => {
        const seg = makeSegmenter("masks");
        const { A } = twoLines(seg);
        A.select();
        seg.activeTool = "box-select-points";
        dragFromTo(seg, A.maskPath, [100, 35], [120, 40]);
        assert.deepEqual(maskYs(A), [30, 30, 60, 60]);
        assert.deepEqual(selectedPoints(seg), []);
    });
});
