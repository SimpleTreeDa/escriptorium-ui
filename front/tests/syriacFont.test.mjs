// Run with `npm test` (Node 22 or later, no other dependency).
import assert from "node:assert/strict";
import { describe, test } from "node:test";
import {
    DEFAULT_SYRIAC_FONT,
    SYRIAC_FONTS,
    applySyriacFont,
    loadSyriacFont,
    saveSyriacFont,
    syriacFont,
    syriacFontKey,
} from "../src/editor/syriacFont.js";

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

/** Enough of an element to set CSS variables on */
function fakeRoot() {
    const properties = {};
    return { properties, style: { setProperty: (name, value) => { properties[name] = value; } } };
}

describe("SYRIAC_FONTS", () => {
    test("are the three variants of Noto Sans Syriac, Estrangela by default", () => {
        assert.deepEqual(SYRIAC_FONTS.map((font) => font.family), [
            "Noto Sans Syriac", "Noto Sans Syriac Western", "Noto Sans Syriac Eastern",
        ]);
        assert.equal(DEFAULT_SYRIAC_FONT, "estrangela");
    });

    test("have distinct values", () => {
        assert.equal(new Set(SYRIAC_FONTS.map((font) => font.value)).size, SYRIAC_FONTS.length);
    });
});

describe("syriacFont", () => {
    test("finds a font by its value", () => {
        assert.equal(syriacFont("serto").family, "Noto Sans Syriac Western");
        assert.equal(syriacFont("east").family, "Noto Sans Syriac Eastern");
    });

    test("is Estrangela for an unknown value", () => {
        assert.equal(syriacFont("unknown").value, "estrangela");
        assert.equal(syriacFont(undefined).value, "estrangela");
    });
});

describe("loadSyriacFont and saveSyriacFont", () => {
    test("keep the font of each document", () => {
        const profile = fakeProfile();
        saveSyriacFont(profile, 12, "serto");
        saveSyriacFont(profile, 13, "east");
        assert.equal(profile.settings[syriacFontKey(12)], "serto");
        assert.equal(loadSyriacFont(profile, 12), "serto");
        assert.equal(loadSyriacFont(profile, 13), "east");
        assert.equal(loadSyriacFont(profile, 14), "estrangela");
    });

    test("save and load only known fonts", () => {
        const profile = fakeProfile({ "syriac-font-1": "comic" });
        assert.equal(loadSyriacFont(profile, 1), "estrangela");
        saveSyriacFont(profile, 2, "comic");
        assert.equal(profile.settings["syriac-font-2"], "estrangela");
    });
});

describe("applySyriacFont", () => {
    test("sets the CSS variable read by the font lists", () => {
        const root = fakeRoot();
        applySyriacFont("east", root);
        assert.deepEqual(root.properties, { "--escr-syriac-font": "\"Noto Sans Syriac Eastern\"" });
        applySyriacFont("unknown", root);
        assert.equal(root.properties["--escr-syriac-font"], "\"Noto Sans Syriac\"");
    });
});
