/*
 * The thumbnail strip of the editor (new UI): every page of the document in
 * a row under the navigation bar, from /api/documents/<pk>/parts/navigation/.
 * Whether it is collapsed is saved in the user profile. Its height is set in
 * Editor.css (--escr-thumbnail-strip-height), which the panels subtract.
 */

/** Key of the saved state in the user profile */
export const PROFILE_KEY = "editor-thumbnail-strip";

/**
 * Whether the strip is collapsed, from what was saved in the user profile.
 * Nothing saved, or anything unexpected, means expanded.
 */
export function loadCollapsed(saved) {
    return Boolean(saved && typeof saved === "object" && saved.collapsed === true);
}

/**
 * The state to save in the user profile.
 */
export function savedState(collapsed) {
    return { collapsed: Boolean(collapsed) };
}

/**
 * The pages to show, in reading order: those with a pk and a position, sorted
 * by position. The API returns them in order already, this keeps it so.
 */
export function sortedPages(pages) {
    if (!Array.isArray(pages)) return [];
    return pages
        .filter((page) => page && Number.isInteger(page.order) && page.pk != null)
        .sort((a, b) => a.order - b.order);
}

/**
 * The index of the current page in the strip, or -1.
 */
export function currentIndex(pages, pk) {
    if (pk == null) return -1;
    return pages.findIndex((page) => page.pk === pk);
}

/**
 * The pages with one of them renamed, when the current page's name changed in
 * the editor and the list should not be fetched again.
 */
export function withPageName(pages, pk, name) {
    const index = currentIndex(pages, pk);
    if (index === -1 || pages[index].name === name) return pages;
    const updated = pages.slice();
    updated[index] = { ...pages[index], name };
    return updated;
}
