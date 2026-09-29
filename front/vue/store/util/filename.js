/**
 * Shorten a filename in the middle, keeping its beginning and its end, where
 * folio numbers and the extension usually are:
 * "BL_Add_14572_f023r_high_resolution_master.tif" -> "BL_Add_14572_f023r_h…olution_master.tif"
 */
export function middleTruncate(name, maxLength) {
    if (!name || name.length <= maxLength) return name;
    const tail = Math.floor((maxLength - 1) * 0.45);
    const head = maxLength - 1 - tail;
    return `${name.slice(0, head)}…${name.slice(-tail)}`;
}
