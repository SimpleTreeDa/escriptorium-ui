/*
 * The server stores the text of lines in Unicode NFC (normalize_text in
 * app/apps/core/utils.py). Compare and send it in that form: text that only
 * differs by its normalization, typed or pasted decomposed, looks the same and
 * is not a change to save.
 */

/**
 * The text in NFC; anything else than a string is returned as it is.
 */
export function normalizeText(text) {
    return typeof text === "string" ? text.normalize("NFC") : text;
}

/**
 * Whether two texts are the same once normalized; no text is the empty text.
 */
export function sameText(a, b) {
    return normalizeText(a || "") === normalizeText(b || "");
}
