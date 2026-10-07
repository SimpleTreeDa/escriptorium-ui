// Run with `npm test` (Node 22 or later, no other dependency).
import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
    TEXT_PANEL_TEXT_SIZE,
    TRANSCRIPTION_TEXT_SIZE,
    canBeLarger,
    canBeSmaller,
    larger,
    loadSize,
    saveSize,
    sizeKey,
    smaller,
} from "../src/editor/fontSize.js";

/** Enough of src/profile.js */
function fakeProfile(settings = {}) {
    return {
        settings,
        get(key, default_) {
            return this.settings[key] !== undefined ? this.settings[key] : default_;
        },
        set(key, value) {
            this.settings[key] = value;
        },
    };
}

const close = (actual, expected) => assert.ok(
    Math.abs(actual - expected) < 1e-12, `${actual} vs ${expected}`,
);

describe("smaller and larger", () => {
    test("change the size by a tenth, like the legacy buttons", () => {
        close(smaller(0.25, TRANSCRIPTION_TEXT_SIZE), 0.225);
        close(larger(0.25, TRANSCRIPTION_TEXT_SIZE), 0.275);
        close(larger(1, TEXT_PANEL_TEXT_SIZE), 1.1);
        close(smaller(1, TEXT_PANEL_TEXT_SIZE), 0.9);
    });

    test("stop at the minimum", () => {
        let size = TEXT_PANEL_TEXT_SIZE.initial;
        for (let i = 0; i < 100; i++) size = smaller(size, TEXT_PANEL_TEXT_SIZE);
        assert.equal(size, TEXT_PANEL_TEXT_SIZE.min);
        assert.equal(canBeSmaller(size, TEXT_PANEL_TEXT_SIZE), false);
        assert.equal(canBeLarger(size, TEXT_PANEL_TEXT_SIZE), true);
    });

    test("stop at the maximum", () => {
        let size = TRANSCRIPTION_TEXT_SIZE.initial;
        for (let i = 0; i < 100; i++) size = larger(size, TRANSCRIPTION_TEXT_SIZE);
        assert.equal(size, TRANSCRIPTION_TEXT_SIZE.max);
        assert.equal(canBeLarger(size, TRANSCRIPTION_TEXT_SIZE), false);
        assert.equal(canBeSmaller(size, TRANSCRIPTION_TEXT_SIZE), true);
    });

    test("can go both ways from the initial size", () => {
        for (const setting of [TRANSCRIPTION_TEXT_SIZE, TEXT_PANEL_TEXT_SIZE]) {
            assert.ok(setting.min < setting.initial && setting.initial < setting.max);
            assert.ok(canBeSmaller(setting.initial, setting));
            assert.ok(canBeLarger(setting.initial, setting));
        }
    });
});

describe("loadSize and saveSize", () => {
    test("keep the size of each document", () => {
        const profile = fakeProfile();
        saveSize(profile, TEXT_PANEL_TEXT_SIZE, 12, 1.21);
        saveSize(profile, TEXT_PANEL_TEXT_SIZE, 13, 0.9);
        assert.equal(loadSize(profile, TEXT_PANEL_TEXT_SIZE, 12), 1.21);
        assert.equal(loadSize(profile, TEXT_PANEL_TEXT_SIZE, 13), 0.9);
        assert.equal(loadSize(profile, TEXT_PANEL_TEXT_SIZE, 14), TEXT_PANEL_TEXT_SIZE.initial);
    });

    test("keep the panels apart", () => {
        const profile = fakeProfile();
        saveSize(profile, TEXT_PANEL_TEXT_SIZE, 12, 2);
        const transcriptionSize = loadSize(profile, TRANSCRIPTION_TEXT_SIZE, 12);
        assert.equal(transcriptionSize, TRANSCRIPTION_TEXT_SIZE.initial);
    });

    test("read the size saved by the legacy toolbar", () => {
        const profile = fakeProfile({ "visu-font-size-12": 0.3025 });
        assert.equal(sizeKey(TRANSCRIPTION_TEXT_SIZE, 12), "visu-font-size-12");
        assert.equal(loadSize(profile, TRANSCRIPTION_TEXT_SIZE, 12), 0.3025);
    });

    test("ignore what is not a size, and keep a saved size within the limits", () => {
        for (const saved of ["big", null, NaN, Infinity, 0, -1]) {
            const profile = fakeProfile({ "diplo-font-size-1": saved });
            const size = loadSize(profile, TEXT_PANEL_TEXT_SIZE, 1);
            assert.equal(size, TEXT_PANEL_TEXT_SIZE.initial, String(saved));
        }
        const profile = fakeProfile({ "diplo-font-size-1": 99, "diplo-font-size-2": 0.01 });
        assert.equal(loadSize(profile, TEXT_PANEL_TEXT_SIZE, 1), TEXT_PANEL_TEXT_SIZE.max);
        assert.equal(loadSize(profile, TEXT_PANEL_TEXT_SIZE, 2), TEXT_PANEL_TEXT_SIZE.min);
    });
});
