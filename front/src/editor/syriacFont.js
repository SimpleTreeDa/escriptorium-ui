/*
 * The font of Syriac text in the editor, chosen for each document: one of the
 * three variants of Noto Sans Syriac in front/fonts (see its README.md). It is
 * saved in the user profile (src/profile.js) and set as the CSS variable
 * --escr-syriac-font, which the font lists use after the Latin font
 * (vue/index.css).
 */

export const SYRIAC_FONTS = [
    { value: "estrangela", label: "Estrangela", family: "Noto Sans Syriac" },
    { value: "serto", label: "Serto (West Syriac)", family: "Noto Sans Syriac Western" },
    { value: "east", label: "East Syriac", family: "Noto Sans Syriac Eastern" },
];

export const DEFAULT_SYRIAC_FONT = SYRIAC_FONTS[0].value;

/** The user profile key of the font of a document, e.g. "syriac-font-12" */
export function syriacFontKey(documentId) {
    return `syriac-font-${documentId}`;
}

/** One of SYRIAC_FONTS by value, Estrangela if there is none */
export function syriacFont(value) {
    return SYRIAC_FONTS.find((font) => font.value === value) || SYRIAC_FONTS[0];
}

/** The value of the font chosen for the document, or of the default */
export function loadSyriacFont(profile, documentId) {
    return syriacFont(profile.get(syriacFontKey(documentId))).value;
}

export function saveSyriacFont(profile, documentId, value) {
    profile.set(syriacFontKey(documentId), syriacFont(value).value);
}

/**
 * Use the font for the Syriac text of the page, popovers included: on the
 * root element by default.
 */
export function applySyriacFont(value, root = document.documentElement) {
    root.style.setProperty("--escr-syriac-font", `"${syriacFont(value).family}"`);
}
