/*
 * Text size of the transcription and text panels of the editor. A− and A+
 * change it by a tenth, within limits; it is saved for each document in the
 * user profile (src/profile.js).
 */

/**
 * The transcription panel (VisuPanel): size of the text relative to the height
 * of each line, see VisuLine. Also set by the buttons of the legacy toolbar.
 */
export const TRANSCRIPTION_TEXT_SIZE = { key: "visu-font-size", initial: 0.25, min: 0.05, max: 2 };

/** The text panel (DiploPanel): size of the text relative to its normal size, in em */
export const TEXT_PANEL_TEXT_SIZE = { key: "diplo-font-size", initial: 1, min: 0.5, max: 4 };

const clamp = (size, { min, max }) => Math.min(max, Math.max(min, size));

/** The user profile key of a size for a document, e.g. "visu-font-size-12" */
export function sizeKey(setting, documentId) {
    return `${setting.key}-${documentId}`;
}

/** A tenth smaller, but not under the minimum */
export function smaller(size, setting) {
    return clamp(size - size / 10, setting);
}

/** A tenth larger, but not over the maximum */
export function larger(size, setting) {
    return clamp(size + size / 10, setting);
}

export function canBeSmaller(size, setting) {
    return size > setting.min;
}

export function canBeLarger(size, setting) {
    return size < setting.max;
}

/**
 * The size saved for the document, kept within the limits, or the initial size
 * if none is saved or it is not a size.
 */
export function loadSize(profile, setting, documentId) {
    const saved = profile.get(sizeKey(setting, documentId));
    if (typeof saved !== "number" || !Number.isFinite(saved) || saved <= 0) return setting.initial;
    return clamp(saved, setting);
}

export function saveSize(profile, setting, documentId, size) {
    profile.set(sizeKey(setting, documentId), size);
}
