/**
 * Normalize a label or filename for searching: lowercase, without spaces or
 * punctuation, and without leading zeros in numbers, so that "f. 23r", "23r"
 * and "f023r" all match "BL_Add_14572_f023r.tif".
 */
export function normalizeForSearch(text) {
    return (text || "")
        .toLowerCase()
        .replace(/[\s._\-,;:()[\]]+/g, "")
        .replace(/(^|\D)0+(?=\d)/g, "$1");
}

/**
 * Filter elements ({ order, name, filename }) by a query matching their label
 * or filename. A plain number also finds the element with that position, first.
 */
export function searchPages(pages, query) {
    const normalized = normalizeForSearch(query);
    if (!normalized) return pages;
    const matches = pages.filter(
        (page) =>
            normalizeForSearch(page.name).includes(normalized) ||
            normalizeForSearch(page.filename).includes(normalized),
    );
    if (!/^\d+$/.test(query.trim())) return matches;
    const position = parseInt(query, 10);
    const exact = pages.find((page) => page.order + 1 === position);
    return exact ? [exact, ...matches.filter((page) => page !== exact)] : matches;
}
