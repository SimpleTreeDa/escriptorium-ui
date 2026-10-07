/*
 * Keyboard shortcuts that change the page in the editor: PageUp and PageDown,
 * Ctrl+Left and Ctrl+Right (which follow the reading direction), and Home and
 * End for the first and last pages.
 */

const TEXT_INPUT_TAGS = ["INPUT", "TEXTAREA", "SELECT"];

/**
 * True when the key was pressed while typing: in a form field, or in an
 * editable element such as a transcription line. Home and End move the caret
 * there, so they must not change the page.
 */
export function isTypingTarget(target) {
    if (!target) return false;
    if (TEXT_INPUT_TAGS.includes(target.tagName)) return true;
    return target.isContentEditable === true;
}

/**
 * The page a key event asks for: "previous", "next", "first" or "last", or
 * null when the event is not a page shortcut, another modifier is held, the
 * user is typing, or shortcuts are blocked (an open dialog, a focused field).
 *
 * @param {object} event `key`, `ctrlKey`, `altKey`, `metaKey`, `shiftKey`, `target`
 * @param {object} options `readDirection` ("ltr" or "rtl") and `blockShortcuts`
 */
export function pageShortcut(event, { readDirection = "ltr", blockShortcuts = false } = {}) {
    if (!event || blockShortcuts || isTypingTarget(event.target)) return null;
    const { key, ctrlKey, altKey, metaKey, shiftKey } = event;
    if (altKey || metaKey || shiftKey) return null;
    if (key === "ArrowLeft" || key === "ArrowRight") {
        // Ctrl+arrow: left is the previous page when reading left to right,
        // the next one when reading right to left
        if (!ctrlKey) return null;
        const towardsStart = (key === "ArrowLeft") !== (readDirection === "rtl");
        return towardsStart ? "previous" : "next";
    }
    if (ctrlKey) return null;
    switch (key) {
        case "PageUp":
            return "previous";
        case "PageDown":
            return "next";
        case "Home":
            return "first";
        case "End":
            return "last";
        default:
            return null;
    }
}

/**
 * The position (0-based) to load for "first" or "last", or null when the
 * document has no pages, the current page is already there, or the count
 * is unknown.
 */
export function targetOrder(action, { order, partsCount }) {
    if (!Number.isInteger(partsCount) || partsCount <= 0) return null;
    let target;
    if (action === "first") target = 0;
    else if (action === "last") target = partsCount - 1;
    else return null;
    return target === order ? null : target;
}
