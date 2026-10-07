// Helpers for the "TEI (Ephrem)" export (docs/tei/ephrem-tei-profile.md):
// the page actions of the Images page and the readiness report of the export dialog.

// the page Name is the folio: a number and r (recto) or v (verso), e.g. 23r
export const isFolio = (value) => /^\s*[1-9]\d*\s*[rv]\s*$/i.test(value || "");

// a Syriaca.org work URI, or any http(s) address without spaces
export const isWebAddress = (value) => /^https?:\/\/\S+$/.test((value || "").trim());

// the page actions: the metadata key they set, and how to ask for its value
export const PAGE_ACTIONS = {
    work: {
        menu: "Set work…",
        title: "Set work",
        label: "Work",
        placeholder: "e.g. Hymns on Faith",
        help: "The work these pages belong to. Leave it empty to remove it from them.",
        verb: "Set",
        valid: () => true,
    },
    work_uri: {
        menu: "Set work URI…",
        title: "Set work URI",
        label: "Work URI",
        placeholder: "e.g. http://syriaca.org/work/1505",
        help: "The work's Syriaca.org URI. Leave it empty to remove it from these pages.",
        verb: "Set",
        valid: (value) => !value.trim() || isWebAddress(value),
    },
    folios: {
        menu: "Number folios…",
        title: "Number folios",
        label: "First folio",
        placeholder: "e.g. 1r",
        help: "Names the selected pages in page order: 1r, 1v, 2r, 2v…, from the first folio.",
        verb: "Number",
        valid: isFolio,
    },
};

export const CATEGORY_LABELS = {
    metadata: "Metadata",
    work: "Works",
    folio: "Folios",
    annotations: "Annotations",
    types: "Region and line types",
    links: "TEI file",
    other: "Other",
};

/**
 * The readiness report of POST /api/documents/{pk}/tei_check/, made short for the export dialog:
 * a title, the categories with problems, and the first messages (errors first).
 */
export const summarizeReadiness = (report, limit = 6) => {
    const errors = report.errors || [];
    const warnings = report.warnings || [];
    const plural = (count, word) => `${count} ${word}${count === 1 ? "" : "s"}`;
    let title = "Ready for TEI export";
    if (errors.length) title = `Not ready: ${plural(errors.length, "problem")} to fix`;
    if (warnings.length) title += ` (${plural(warnings.length, "warning")})`;
    const counts = Object.entries(report.summary || {})
        .filter(([, count]) => count.errors || count.warnings)
        .map(([category, count]) => ({
            category,
            label: CATEGORY_LABELS[category] || category,
            errors: count.errors,
            warnings: count.warnings,
        }));
    const messages = [
        ...errors.map((problem) => ({ level: "error", text: problem.message })),
        ...warnings.map((problem) => ({ level: "warning", text: problem.message })),
    ];
    return {
        ready: !errors.length,
        title,
        counts,
        messages: messages.slice(0, limit),
        more: Math.max(messages.length - limit, 0),
    };
};
