/*
 * Layout of the editor panels (new UI): side by side ("row") or stacked
 * ("column"), and the share of the space each open panel takes.
 *
 * Sizes are fractions adding up to 1, one per open panel, in panel order. They
 * are kept for each orientation, so switching back restores the sizes you had.
 * A size belongs to a position, not to a panel: switching the panel shown in a
 * position keeps its size.
 */

export const ORIENTATIONS = ["row", "column"];
export const DEFAULT_ORIENTATION = "row";

/**
 * Equal sizes for `count` panels.
 */
export function equalSizes(count) {
    return count > 0 ? Array(count).fill(1 / count) : [];
}

/**
 * Scale positive sizes so that they add up to 1.
 */
function normalized(sizes) {
    const total = sizes.reduce((sum, size) => sum + size, 0);
    return sizes.map((size) => size / total);
}

function isUsable(sizes, count) {
    return (
        Array.isArray(sizes) &&
        sizes.length === count &&
        sizes.every((size) => typeof size === "number" && Number.isFinite(size) && size > 0)
    );
}

/**
 * A valid layout for `count` open panels, from what was saved in the user
 * profile. Anything missing or unusable falls back to the default: side by
 * side, equal sizes.
 */
export function loadLayout(saved, count) {
    const orientation = ORIENTATIONS.includes(saved?.orientation)
        ? saved.orientation
        : DEFAULT_ORIENTATION;
    const sizes = {};
    ORIENTATIONS.forEach((o) => {
        const savedSizes = saved?.sizes?.[o];
        sizes[o] = isUsable(savedSizes, count) ? normalized(savedSizes) : equalSizes(count);
    });
    return { orientation, sizes };
}

/**
 * Apply `update` to the sizes of every orientation.
 */
function mapSizes(layout, update) {
    const sizes = {};
    ORIENTATIONS.forEach((o) => {
        sizes[o] = update(layout.sizes[o] || []);
    });
    return { ...layout, sizes };
}

/**
 * A panel was added at the end: all panels get the same size.
 */
export function withPanelAdded(layout, count) {
    return mapSizes(layout, () => equalSizes(count));
}

/**
 * The panel at `index` was closed: the others keep their proportions.
 */
export function withPanelRemoved(layout, index) {
    return mapSizes(layout, (sizes) => {
        const rest = sizes.filter((_, i) => i !== index);
        return rest.length ? normalized(rest) : [];
    });
}

export function withOrientation(layout, orientation) {
    if (!ORIENTATIONS.includes(orientation)) return layout;
    return { ...layout, orientation };
}

/**
 * New sizes for the current orientation.
 */
export function withSizes(layout, sizes) {
    return { ...layout, sizes: { ...layout.sizes, [layout.orientation]: sizes } };
}

/**
 * Equal sizes for the current orientation.
 */
export function withEqualSizes(layout) {
    const count = layout.sizes[layout.orientation].length;
    return withSizes(layout, equalSizes(count));
}

/**
 * Move the divider between the panels at `index` and `index + 1` by `delta`, a
 * fraction of the whole space (positive grows the first panel). Only those two
 * panels change, and neither gets smaller than `min` (as a fraction too).
 */
export function resizeAt(sizes, index, delta, min = 0) {
    if (index < 0 || index >= sizes.length - 1) return sizes.slice();
    const pair = sizes[index] + sizes[index + 1];
    // when both minimums don't fit, share the space equally
    const lowest = Math.min(Math.max(min, 0), pair / 2);
    const first = Math.min(Math.max(sizes[index] + delta, lowest), pair - lowest);
    const result = sizes.slice();
    result[index] = first;
    result[index + 1] = pair - first;
    return result;
}
