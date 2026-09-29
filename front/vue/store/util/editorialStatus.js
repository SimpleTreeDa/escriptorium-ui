/**
 * The editorial statuses of pages, in workflow order; the values are those of
 * DocumentPart.EDITORIAL_STATUS_CHOICES on the server.
 */
export const EDITORIAL_STATUSES = [
    { value: "not_started", label: "Not started" },
    { value: "in_progress", label: "In progress" },
    { value: "transcribed", label: "Initial transcription complete" },
    { value: "reviewed_1", label: "Reviewed by Editor 1" },
    { value: "reviewed_2", label: "Reviewed by Editor 2" },
    { value: "ground_truth", label: "Ground truth" },
    { value: "final", label: "Final edited copy" },
    { value: "ready_for_tei", label: "Ready for TEI export" },
];

export function editorialStatusLabel(value) {
    const status = EDITORIAL_STATUSES.find((s) => s.value === value);
    return status ? status.label : "";
}

/**
 * Who set the status of a part ({ editorial_status_by, editorial_status_at }) and
 * when, e.g. "Set by maria on 29/09/2026, 14:05", or "" if nobody did.
 */
export function editorialStatusChange(part) {
    if (!part || !part.editorial_status_at) return "";
    const when = new Date(part.editorial_status_at).toLocaleString();
    return part.editorial_status_by
        ? `Set by ${part.editorial_status_by} on ${when}`
        : `Set on ${when}`;
}
